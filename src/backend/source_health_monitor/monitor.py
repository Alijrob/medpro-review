"""
monitor.py — SourceHealthMonitor: alert threshold evaluation engine (C24).

The SourceHealthMonitor is stateless. It receives:
  - the current SourceHealthRecord for a source
  - the accumulated consecutive_failures count (from HealthStore, not base.py)
  - the source's IntegrationMethod (to choose the correct stale threshold)
  - whether alerts are currently suppressed for that source

...and returns a list of HealthAlert objects. No I/O, no side effects.

Separation: HealthStore (store.py) owns state accumulation + history.
            SourceHealthMonitor (this file) owns threshold logic + alert text.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from enum import Enum
from uuid import UUID

from pydantic import Field

from connectors.models import IntegrationMethod
from schema.v1.common import MedproBaseModel, new_uuid, utc_now
from schema.v1.source_health import SourceHealthRecord, SourceStatus


class AlertType(str, Enum):
    """Classification of a health alert."""

    CONSECUTIVE_FAILURES = "consecutive_failures"
    SCHEMA_DRIFT = "schema_drift"
    STALE_SOURCE = "stale_source"
    LOW_RECORD_COUNT = "low_record_count"
    AUTH_FAILURE = "auth_failure"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class HealthAlert(MedproBaseModel):
    """A single evaluated alert for a data source."""

    alert_id: UUID = Field(default_factory=new_uuid)
    source_id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    detected_at: datetime = Field(default_factory=utc_now)
    suppressed: bool = Field(
        default=False,
        description="True if the source's alert_suppressed_until is in the future.",
    )


class SourceHealthMonitor:
    """
    Stateless threshold evaluation engine. Instantiate once per service
    (singleton via the FastAPI app factory). Thread-safe: no mutable state.

    Thresholds (all configurable via MonitorSettings):
      - consecutive_failures >= failure_warning_threshold  -> WARNING
      - consecutive_failures >= failure_critical_threshold -> CRITICAL
      - schema_drift_detected                             -> WARNING
      - last_successful_at > stale_*_hours ago            -> WARNING
      - bulk_download_record_count < bulk_download_expected_min -> WARNING
      - status == AUTHENTICATION_FAILED                   -> CRITICAL
    """

    def __init__(
        self,
        *,
        failure_warning_threshold: int = 3,
        failure_critical_threshold: int = 5,
        stale_bulk_hours: float = 48.0,
        stale_api_hours: float = 4.0,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if failure_critical_threshold <= failure_warning_threshold:
            raise ValueError(
                "failure_critical_threshold must be strictly greater than "
                "failure_warning_threshold"
            )
        self._fail_warn = failure_warning_threshold
        self._fail_crit = failure_critical_threshold
        self._stale_bulk = stale_bulk_hours
        self._stale_api = stale_api_hours
        self._clock = clock

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        record: SourceHealthRecord,
        *,
        accumulated_failures: int,
        integration_method: IntegrationMethod,
        suppressed: bool = False,
    ) -> list[HealthAlert]:
        """
        Evaluate all thresholds for `record` and return the resulting alerts.

        Args:
            record:               Current SourceHealthRecord for the source.
            accumulated_failures: Consecutive failure count maintained by HealthStore.
            integration_method:   BULK_DOWNLOAD or REST_API (determines stale threshold).
            suppressed:           If True, all returned alerts have suppressed=True.
        """
        alerts: list[HealthAlert] = []

        # -- Auth failure (always CRITICAL; supersedes consecutive-failure count) --
        if record.status is SourceStatus.AUTHENTICATION_FAILED:
            alerts.append(
                HealthAlert(
                    source_id=record.source_id,
                    alert_type=AlertType.AUTH_FAILURE,
                    severity=AlertSeverity.CRITICAL,
                    message=(
                        f"{record.source_id}: authentication failed. "
                        "Check API key / credentials in Secrets Manager."
                    ),
                    suppressed=suppressed,
                )
            )

        # -- Consecutive failures --
        if accumulated_failures >= self._fail_crit:
            alerts.append(
                HealthAlert(
                    source_id=record.source_id,
                    alert_type=AlertType.CONSECUTIVE_FAILURES,
                    severity=AlertSeverity.CRITICAL,
                    message=(
                        f"{record.source_id}: {accumulated_failures} consecutive "
                        f"failures (critical threshold: {self._fail_crit})."
                    ),
                    suppressed=suppressed,
                )
            )
        elif accumulated_failures >= self._fail_warn:
            alerts.append(
                HealthAlert(
                    source_id=record.source_id,
                    alert_type=AlertType.CONSECUTIVE_FAILURES,
                    severity=AlertSeverity.WARNING,
                    message=(
                        f"{record.source_id}: {accumulated_failures} consecutive "
                        f"failures (warning threshold: {self._fail_warn})."
                    ),
                    suppressed=suppressed,
                )
            )

        # -- Schema drift --
        if record.schema_drift_detected:
            alerts.append(
                HealthAlert(
                    source_id=record.source_id,
                    alert_type=AlertType.SCHEMA_DRIFT,
                    severity=AlertSeverity.WARNING,
                    message=(
                        f"{record.source_id}: schema drift detected. "
                        f"Details: {record.schema_drift_details or 'see adapter logs'}. "
                        "Normalization may produce incomplete records until the "
                        "contract is updated."
                    ),
                    suppressed=suppressed,
                )
            )

        # -- Stale source --
        stale_alert = self._check_stale(record, integration_method, suppressed)
        if stale_alert is not None:
            alerts.append(stale_alert)

        # -- Low record count (bulk sources only) --
        if (
            integration_method is IntegrationMethod.BULK_DOWNLOAD
            and record.bulk_download_expected_min is not None
            and record.bulk_download_record_count is not None
            and record.bulk_download_record_count < record.bulk_download_expected_min
        ):
            alerts.append(
                HealthAlert(
                    source_id=record.source_id,
                    alert_type=AlertType.LOW_RECORD_COUNT,
                    severity=AlertSeverity.WARNING,
                    message=(
                        f"{record.source_id}: bulk download yielded "
                        f"{record.bulk_download_record_count} records, below "
                        f"expected minimum {record.bulk_download_expected_min}. "
                        "Source data may be truncated."
                    ),
                    suppressed=suppressed,
                )
            )

        return alerts

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_stale(
        self,
        record: SourceHealthRecord,
        integration_method: IntegrationMethod,
        suppressed: bool,
    ) -> HealthAlert | None:
        """Return a STALE_SOURCE alert if the last successful run is too old."""
        # Never-checked sources are UNKNOWN, not stale.
        if record.last_successful_at is None:
            return None

        threshold_hours = (
            self._stale_bulk
            if integration_method is IntegrationMethod.BULK_DOWNLOAD
            else self._stale_api
        )
        now = self._clock()
        age = now - record.last_successful_at
        if age > timedelta(hours=threshold_hours):
            hours_ago = age.total_seconds() / 3600
            return HealthAlert(
                source_id=record.source_id,
                alert_type=AlertType.STALE_SOURCE,
                severity=AlertSeverity.WARNING,
                message=(
                    f"{record.source_id}: last successful run was "
                    f"{hours_ago:.1f}h ago (threshold: {threshold_hours:.0f}h). "
                    "Source data may be out of date."
                ),
                suppressed=suppressed,
            )
        return None

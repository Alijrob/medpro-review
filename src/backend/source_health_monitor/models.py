"""
models.py — API request/response models for the Source Health Monitor (C24).

These are the shapes exposed by the REST API. They are distinct from the
domain types in monitor.py (HealthAlert, AlertType) and the canonical schema
type SourceHealthRecord -- though they compose them where appropriate.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from schema.v1.common import MedproBaseModel, utc_now
from schema.v1.source_health import SourceHealthRecord, SourceStatus

from .monitor import HealthAlert


class IngestRequest(MedproBaseModel):
    """
    Payload for POST /v1/sources/{source_id}/ingest.

    An adapter (or its orchestrating worker) POSTs the SourceHealthRecord
    emitted by a connector run. The monitor accumulates it and evaluates
    thresholds.
    """

    record: SourceHealthRecord


class SuppressRequest(MedproBaseModel):
    """Payload for POST /v1/sources/{source_id}/suppress."""

    suppress_until: datetime = Field(
        description="Suppress all alerts for this source until this UTC timestamp.",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional human-readable reason for suppression (e.g. 'planned maintenance').",
    )


class SourceHealthSummary(MedproBaseModel):
    """
    Rolled-up health status for a single source as returned by the API.

    Combines the current SourceHealthRecord with accumulated counters and
    active alerts evaluated by SourceHealthMonitor.
    """

    source_id: str
    source_name: str
    status: SourceStatus
    accumulated_failures: int = Field(
        ge=0,
        description="Consecutive failure count maintained by HealthStore (not base.py).",
    )
    accumulated_successes: int = Field(ge=0)
    last_checked_at: datetime | None = None
    last_successful_at: datetime | None = None
    schema_drift_detected: bool = False
    schema_drift_details: str | None = None
    bulk_download_record_count: int | None = None
    bulk_download_expected_min: int | None = None
    alert_suppressed: bool = False
    suppress_until: datetime | None = None
    alerts: list[HealthAlert] = Field(default_factory=list)
    recent_history: list[SourceHealthRecord] = Field(
        default_factory=list,
        description="Most recent adapter run snapshots (newest first, up to 10).",
    )


class FleetHealthSummary(MedproBaseModel):
    """
    Fleet-wide health summary for all monitored sources.
    Returned by GET /v1/sources.
    """

    checked_at: datetime = Field(default_factory=utc_now)
    total_sources: int
    healthy: int = 0
    degraded: int = 0
    down: int = 0
    schema_drift: int = 0
    unknown: int = 0
    active_alert_count: int = Field(
        default=0,
        description="Count of non-suppressed alerts across all sources.",
    )
    sources: list[SourceHealthSummary] = Field(default_factory=list)


class AlertsResponse(MedproBaseModel):
    """Response for GET /v1/alerts."""

    checked_at: datetime = Field(default_factory=utc_now)
    total: int
    active: int = Field(description="Non-suppressed alert count.")
    suppressed: int = Field(description="Suppressed alert count.")
    alerts: list[HealthAlert] = Field(default_factory=list)


class IngestResponse(MedproBaseModel):
    """Response for POST /v1/sources/{source_id}/ingest."""

    source_id: str
    status: SourceStatus
    accumulated_failures: int
    accumulated_successes: int
    alerts_raised: int = Field(
        description="Number of alerts the ingested record triggered."
    )

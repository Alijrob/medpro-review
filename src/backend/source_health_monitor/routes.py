"""
routes.py — Source Health Monitor API routes (C24).

Endpoints:
  GET  /healthz                              Service liveness probe
  GET  /readyz                               Readiness probe
  GET  /v1/sources                           Fleet-wide health summary
  GET  /v1/sources/{source_id}              Per-source summary + recent history
  GET  /v1/sources/{source_id}/history      Per-source full history (ring buffer)
  GET  /v1/alerts                            Active alerts across all sources
  POST /v1/sources/{source_id}/ingest       Accept a SourceHealthRecord from a run
  POST /v1/sources/{source_id}/suppress     Suppress alerts for a source
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from schema.v1.common import utc_now
from schema.v1.source_health import SourceStatus

from .config import MonitorSettings, get_settings
from .models import (
    AlertsResponse,
    FleetHealthSummary,
    IngestRequest,
    IngestResponse,
    SourceHealthSummary,
    SuppressRequest,
)
from .monitor import SourceHealthMonitor
from .store import HealthStore, get_source_meta

router = APIRouter()

# ---------------------------------------------------------------------------
# Dependency injectors
# ---------------------------------------------------------------------------

_store: HealthStore | None = None
_monitor: SourceHealthMonitor | None = None


def get_store() -> HealthStore:  # pragma: no cover
    """Return the singleton HealthStore. Set by the app factory."""
    assert _store is not None, "HealthStore not initialised"
    return _store


def get_monitor() -> SourceHealthMonitor:  # pragma: no cover
    """Return the singleton SourceHealthMonitor. Set by the app factory."""
    assert _monitor is not None, "SourceHealthMonitor not initialised"
    return _monitor


def _set_singletons(store: HealthStore, monitor: SourceHealthMonitor) -> None:
    """Called by app.py to wire the singletons before the first request."""
    global _store, _monitor
    _store = store
    _monitor = monitor


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _build_source_summary(
    source_id: str,
    store: HealthStore,
    monitor: SourceHealthMonitor,
    history_limit: int = 10,
) -> SourceHealthSummary | None:
    """Build a SourceHealthSummary for `source_id`. Returns None if unknown."""
    record = store.current(source_id)
    if record is None:
        return None

    accumulated = store.accumulated_failures(source_id)
    suppressed = store.is_suppressed(source_id)
    method = store.integration_method(source_id)
    alerts = monitor.evaluate(
        record,
        accumulated_failures=accumulated,
        integration_method=method,
        suppressed=suppressed,
    )

    suppress_until_dt = store._suppressed_until.get(source_id)

    return SourceHealthSummary(
        source_id=source_id,
        source_name=record.source_name,
        status=record.status,
        accumulated_failures=accumulated,
        accumulated_successes=store.accumulated_successes(source_id),
        last_checked_at=record.last_checked_at,
        last_successful_at=record.last_successful_at,
        schema_drift_detected=record.schema_drift_detected,
        schema_drift_details=record.schema_drift_details,
        bulk_download_record_count=record.bulk_download_record_count,
        bulk_download_expected_min=record.bulk_download_expected_min,
        alert_suppressed=suppressed,
        suppress_until=suppress_until_dt,
        alerts=alerts,
        recent_history=store.history(source_id, limit=history_limit),
    )


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

@router.get("/healthz", tags=["probes"])
def healthz() -> dict:
    return {"status": "ok", "service": "source-health-monitor"}


@router.get("/readyz", tags=["probes"])
def readyz(settings: MonitorSettings = Depends(get_settings)) -> dict:
    return {
        "status": "ready",
        "db_configured": settings.is_configured,
        "note": "in-memory shell" if not settings.is_configured else "aurora-backed",
    }


# ---------------------------------------------------------------------------
# Fleet summary
# ---------------------------------------------------------------------------

@router.get("/v1/sources", response_model=FleetHealthSummary, tags=["health"])
def fleet_summary(
    store: HealthStore = Depends(get_store),
    monitor: SourceHealthMonitor = Depends(get_monitor),
) -> FleetHealthSummary:
    """Return fleet-wide health status for all monitored sources."""
    summaries: list[SourceHealthSummary] = []
    active_alerts = 0

    for sid in store.source_ids():
        summary = _build_source_summary(sid, store, monitor)
        if summary is not None:
            summaries.append(summary)
            active_alerts += sum(1 for a in summary.alerts if not a.suppressed)

    status_counts: dict[str, int] = {
        "healthy": 0, "degraded": 0, "down": 0, "schema_drift": 0, "unknown": 0,
    }
    for s in summaries:
        key = s.status.value if s.status.value in status_counts else "unknown"
        status_counts[key] = status_counts.get(key, 0) + 1

    return FleetHealthSummary(
        checked_at=utc_now(),
        total_sources=len(summaries),
        healthy=status_counts["healthy"],
        degraded=status_counts["degraded"],
        down=status_counts["down"],
        schema_drift=status_counts["schema_drift"],
        unknown=status_counts["unknown"],
        active_alert_count=active_alerts,
        sources=summaries,
    )


# ---------------------------------------------------------------------------
# Per-source endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/v1/sources/{source_id}",
    response_model=SourceHealthSummary,
    tags=["health"],
)
def source_detail(
    source_id: str,
    store: HealthStore = Depends(get_store),
    monitor: SourceHealthMonitor = Depends(get_monitor),
) -> SourceHealthSummary:
    """Return current health status + recent history for a single source."""
    summary = _build_source_summary(source_id.upper(), store, monitor, history_limit=10)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found in health store.",
        )
    return summary


@router.get(
    "/v1/sources/{source_id}/history",
    response_model=list,
    tags=["health"],
)
def source_history(
    source_id: str,
    limit: int = 20,
    store: HealthStore = Depends(get_store),
) -> list:
    """Return recent adapter run history for a source (newest first)."""
    sid = source_id.upper()
    if store.current(sid) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found.",
        )
    return store.history(sid, limit=min(limit, 100))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/v1/alerts", response_model=AlertsResponse, tags=["alerts"])
def list_alerts(
    store: HealthStore = Depends(get_store),
    monitor: SourceHealthMonitor = Depends(get_monitor),
) -> AlertsResponse:
    """Return all active alerts across all monitored sources."""
    all_alerts = []
    for sid in store.source_ids():
        record = store.current(sid)
        if record is None:
            continue
        alerts = monitor.evaluate(
            record,
            accumulated_failures=store.accumulated_failures(sid),
            integration_method=store.integration_method(sid),
            suppressed=store.is_suppressed(sid),
        )
        all_alerts.extend(alerts)

    active = sum(1 for a in all_alerts if not a.suppressed)
    suppressed_count = len(all_alerts) - active

    return AlertsResponse(
        checked_at=utc_now(),
        total=len(all_alerts),
        active=active,
        suppressed=suppressed_count,
        alerts=all_alerts,
    )


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

@router.post(
    "/v1/sources/{source_id}/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_200_OK,
    tags=["ingest"],
)
def ingest(
    source_id: str,
    body: IngestRequest,
    store: HealthStore = Depends(get_store),
    monitor: SourceHealthMonitor = Depends(get_monitor),
) -> IngestResponse:
    """
    Accept a SourceHealthRecord from an adapter run.

    The record's source_id must match the path parameter (case-insensitive).
    The monitor accumulates the record, updates consecutive counters, and
    evaluates thresholds.
    """
    sid = source_id.upper()
    if body.record.source_id.upper() != sid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Path source_id '{source_id}' does not match "
                f"record.source_id '{body.record.source_id}'."
            ),
        )

    store.ingest(body.record)

    accumulated = store.accumulated_failures(sid)
    suppressed = store.is_suppressed(sid)
    method = store.integration_method(sid)
    alerts = monitor.evaluate(
        body.record,
        accumulated_failures=accumulated,
        integration_method=method,
        suppressed=suppressed,
    )

    return IngestResponse(
        source_id=sid,
        status=body.record.status,
        accumulated_failures=accumulated,
        accumulated_successes=store.accumulated_successes(sid),
        alerts_raised=len(alerts),
    )


# ---------------------------------------------------------------------------
# Suppress
# ---------------------------------------------------------------------------

@router.post(
    "/v1/sources/{source_id}/suppress",
    tags=["ops"],
)
def suppress_alerts(
    source_id: str,
    body: SuppressRequest,
    store: HealthStore = Depends(get_store),
) -> dict:
    """Suppress health alerts for a source until a given UTC timestamp."""
    sid = source_id.upper()
    if store.current(sid) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_id}' not found.",
        )
    store.suppress(sid, body.suppress_until)
    return {
        "source_id": sid,
        "suppressed_until": body.suppress_until.isoformat(),
        "reason": body.reason,
    }

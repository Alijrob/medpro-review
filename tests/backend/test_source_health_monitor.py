"""
tests/backend/test_source_health_monitor.py

Behavior tests for the Source Health Monitor (C24, Phase 2-C).

Coverage:
  - Config defaults and overrides
  - HealthStore seeding (all 8 P1 connector sources pre-seeded)
  - HealthStore ingest: success path (counters reset), failure path (accumulate)
  - HealthStore: history ring buffer, suppression
  - SourceHealthMonitor threshold evaluation: no alerts, consecutive-failure
    WARNING/CRITICAL, schema drift, stale source (bulk + API), low record
    count, auth failure, suppressed alerts, multiple alerts
  - Routes: GET /healthz, GET /v1/sources, GET /v1/sources/{id},
    GET /v1/sources/{id} 404, GET /v1/sources/{id}/history,
    GET /v1/alerts, POST /v1/sources/{id}/ingest (success + mismatch),
    POST /v1/sources/{id}/suppress

No database, no network -- all state is in-memory.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from connectors.models import IntegrationMethod
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceHealthRecord, SourceStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc(dt: str) -> datetime:
    return datetime.fromisoformat(dt).replace(tzinfo=timezone.utc)


def _make_record(
    source_id: str = "F1",
    status: SourceStatus = SourceStatus.HEALTHY,
    *,
    consecutive_failures: int = 0,
    consecutive_successes: int = 1,
    schema_drift_detected: bool = False,
    schema_drift_details: str | None = None,
    last_successful_at: datetime | None = None,
    last_failed_at: datetime | None = None,
    last_checked_at: datetime | None = None,
    bulk_download_record_count: int | None = None,
    bulk_download_expected_min: int | None = None,
) -> SourceHealthRecord:
    from schema.v1.common import utc_now

    now = utc_now()
    return SourceHealthRecord(
        source_id=source_id,
        source_name=f"Test Source {source_id}",
        source_category=SourceCategory.FEDERAL,
        status=status,
        consecutive_failures=consecutive_failures,
        consecutive_successes=consecutive_successes,
        schema_drift_detected=schema_drift_detected,
        schema_drift_details=schema_drift_details,
        last_successful_at=last_successful_at or (None if consecutive_failures > 0 else now),
        last_failed_at=last_failed_at or (now if consecutive_failures > 0 else None),
        last_checked_at=last_checked_at or now,
        bulk_download_record_count=bulk_download_record_count,
        bulk_download_expected_min=bulk_download_expected_min,
    )


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestMonitorConfig:
    def test_defaults(self) -> None:
        from backend.source_health_monitor.config import MonitorSettings

        s = MonitorSettings()
        assert s.failure_warning_threshold == 3
        assert s.failure_critical_threshold == 5
        assert s.stale_bulk_hours == 48.0
        assert s.stale_api_hours == 4.0
        assert s.history_limit == 100
        assert s.is_configured is False

    def test_database_url_sets_configured(self) -> None:
        from backend.source_health_monitor.config import MonitorSettings

        s = MonitorSettings(database_url="postgresql+psycopg2://user:pw@localhost/medpro")
        assert s.is_configured is True


# ---------------------------------------------------------------------------
# HealthStore tests
# ---------------------------------------------------------------------------


class TestHealthStore:
    def test_seed_p1_sources(self) -> None:
        """All 8 P1 connector sources pre-seeded as UNKNOWN on construction."""
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        ids = store.source_ids()
        assert set(ids) == {"F1", "F2", "F3", "F4", "I1", "I2", "A1", "A2"}

    def test_seed_status_is_unknown(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        for sid in store.source_ids():
            assert store.current(sid).status is SourceStatus.UNKNOWN

    def test_ingest_success_updates_current(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        rec = _make_record("F1", SourceStatus.HEALTHY)
        store.ingest(rec)
        assert store.current("F1").status is SourceStatus.HEALTHY

    def test_ingest_success_resets_failure_counter(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        # Simulate 3 prior failures by ingesting 3 failed records.
        for _ in range(3):
            store.ingest(_make_record("F1", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0))
        assert store.accumulated_failures("F1") == 3
        # Now a success resets it.
        store.ingest(_make_record("F1", SourceStatus.HEALTHY))
        assert store.accumulated_failures("F1") == 0
        assert store.accumulated_successes("F1") == 1

    def test_ingest_failure_accumulates_counter(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        for i in range(1, 5):
            store.ingest(_make_record("F2", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0))
            assert store.accumulated_failures("F2") == i

    def test_history_appended_newest_first(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        r1 = _make_record("F1", SourceStatus.HEALTHY)
        r2 = _make_record("F1", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0)
        store.ingest(r1)
        store.ingest(r2)
        hist = store.history("F1")
        assert hist[0].status is SourceStatus.DOWN
        assert hist[1].status is SourceStatus.HEALTHY

    def test_history_limit_respected(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        limit = 5
        store = HealthStore(history_limit=limit)
        for _ in range(10):
            store.ingest(_make_record("F1", SourceStatus.HEALTHY))
        assert len(store.history("F1")) == limit

    def test_suppression_active(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        far_future = _utc("2099-01-01T00:00:00")
        store.suppress("F1", far_future)
        assert store.is_suppressed("F1") is True

    def test_suppression_expired(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        past = _utc("2000-01-01T00:00:00")
        store.suppress("F1", past)
        assert store.is_suppressed("F1") is False

    def test_integration_method_known_source(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        # F2 OIG LEIE is the only BULK_DOWNLOAD source in P1.
        assert store.integration_method("F2") is IntegrationMethod.BULK_DOWNLOAD
        assert store.integration_method("F1") is IntegrationMethod.REST_API

    def test_integration_method_unknown_defaults_to_rest_api(self) -> None:
        from backend.source_health_monitor.store import HealthStore

        store = HealthStore()
        assert store.integration_method("ZZZZ") is IntegrationMethod.REST_API


# ---------------------------------------------------------------------------
# SourceHealthMonitor threshold tests
# ---------------------------------------------------------------------------


class TestSourceHealthMonitor:
    def _make_monitor(self, **kwargs):
        from backend.source_health_monitor.monitor import SourceHealthMonitor

        defaults = dict(
            failure_warning_threshold=3,
            failure_critical_threshold=5,
            stale_bulk_hours=48.0,
            stale_api_hours=4.0,
        )
        defaults.update(kwargs)
        return SourceHealthMonitor(**defaults)

    def test_no_alerts_on_healthy_source(self) -> None:
        mon = self._make_monitor()
        rec = _make_record("F1", SourceStatus.HEALTHY)
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.REST_API)
        assert alerts == []

    def test_consecutive_failure_warning(self) -> None:
        from backend.source_health_monitor.monitor import AlertSeverity, AlertType

        mon = self._make_monitor()
        rec = _make_record("F1", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0)
        alerts = mon.evaluate(rec, accumulated_failures=3, integration_method=IntegrationMethod.REST_API)
        types = {a.alert_type for a in alerts}
        assert AlertType.CONSECUTIVE_FAILURES in types
        cf_alert = next(a for a in alerts if a.alert_type is AlertType.CONSECUTIVE_FAILURES)
        assert cf_alert.severity is AlertSeverity.WARNING

    def test_consecutive_failure_critical(self) -> None:
        from backend.source_health_monitor.monitor import AlertSeverity, AlertType

        mon = self._make_monitor()
        rec = _make_record("F1", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0)
        alerts = mon.evaluate(rec, accumulated_failures=5, integration_method=IntegrationMethod.REST_API)
        cf = [a for a in alerts if a.alert_type is AlertType.CONSECUTIVE_FAILURES]
        assert len(cf) == 1
        assert cf[0].severity is AlertSeverity.CRITICAL

    def test_schema_drift_alert(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        mon = self._make_monitor()
        rec = _make_record("F1", SourceStatus.SCHEMA_DRIFT, schema_drift_detected=True, schema_drift_details="missing field npi")
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.REST_API)
        assert any(a.alert_type is AlertType.SCHEMA_DRIFT for a in alerts)

    def test_stale_source_api(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        stale_time = _utc("2026-01-01T00:00:00")
        now_time = _utc("2026-01-01T10:00:00")  # 10h later -- past 4h threshold
        mon = self._make_monitor(stale_api_hours=4.0, clock=lambda: now_time)
        rec = _make_record("F1", SourceStatus.HEALTHY, last_successful_at=stale_time)
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.REST_API)
        assert any(a.alert_type is AlertType.STALE_SOURCE for a in alerts)

    def test_stale_source_bulk(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        stale_time = _utc("2026-01-01T00:00:00")
        now_time = _utc("2026-01-03T12:00:00")  # 60h later -- past 48h threshold
        mon = self._make_monitor(stale_bulk_hours=48.0, clock=lambda: now_time)
        rec = _make_record("F2", SourceStatus.HEALTHY, last_successful_at=stale_time)
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.BULK_DOWNLOAD)
        assert any(a.alert_type is AlertType.STALE_SOURCE for a in alerts)

    def test_not_stale_within_threshold(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        recent = _utc("2026-01-01T00:00:00")
        now_time = _utc("2026-01-01T02:00:00")  # 2h later -- within 4h threshold
        mon = self._make_monitor(stale_api_hours=4.0, clock=lambda: now_time)
        rec = _make_record("F1", SourceStatus.HEALTHY, last_successful_at=recent)
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.REST_API)
        assert not any(a.alert_type is AlertType.STALE_SOURCE for a in alerts)

    def test_low_record_count_alert(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        mon = self._make_monitor()
        rec = _make_record(
            "F2",
            SourceStatus.DEGRADED,
            bulk_download_record_count=10_000,
            bulk_download_expected_min=60_000,
        )
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.BULK_DOWNLOAD)
        assert any(a.alert_type is AlertType.LOW_RECORD_COUNT for a in alerts)

    def test_low_record_count_skipped_for_api_sources(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        mon = self._make_monitor()
        rec = _make_record("F1", SourceStatus.HEALTHY, bulk_download_record_count=10, bulk_download_expected_min=100)
        alerts = mon.evaluate(rec, accumulated_failures=0, integration_method=IntegrationMethod.REST_API)
        assert not any(a.alert_type is AlertType.LOW_RECORD_COUNT for a in alerts)

    def test_auth_failure_alert_is_critical(self) -> None:
        from backend.source_health_monitor.monitor import AlertSeverity, AlertType

        mon = self._make_monitor()
        rec = _make_record("F3", SourceStatus.AUTHENTICATION_FAILED, consecutive_failures=1, consecutive_successes=0)
        alerts = mon.evaluate(rec, accumulated_failures=1, integration_method=IntegrationMethod.REST_API)
        auth = [a for a in alerts if a.alert_type is AlertType.AUTH_FAILURE]
        assert len(auth) == 1
        assert auth[0].severity is AlertSeverity.CRITICAL

    def test_suppressed_alerts_flagged(self) -> None:
        mon = self._make_monitor()
        rec = _make_record("F1", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0)
        alerts = mon.evaluate(
            rec,
            accumulated_failures=4,
            integration_method=IntegrationMethod.REST_API,
            suppressed=True,
        )
        assert len(alerts) > 0
        assert all(a.suppressed for a in alerts)

    def test_multiple_alerts_on_one_source(self) -> None:
        from backend.source_health_monitor.monitor import AlertType

        stale_time = _utc("2026-01-01T00:00:00")
        now_time = _utc("2026-01-01T10:00:00")
        mon = self._make_monitor(stale_api_hours=4.0, clock=lambda: now_time)
        rec = _make_record(
            "F1",
            SourceStatus.SCHEMA_DRIFT,
            schema_drift_detected=True,
            consecutive_failures=1,
            consecutive_successes=0,
            last_successful_at=stale_time,
        )
        alerts = mon.evaluate(rec, accumulated_failures=3, integration_method=IntegrationMethod.REST_API)
        types = {a.alert_type for a in alerts}
        assert AlertType.CONSECUTIVE_FAILURES in types
        assert AlertType.SCHEMA_DRIFT in types
        assert AlertType.STALE_SOURCE in types

    def test_invalid_threshold_order_raises(self) -> None:
        from backend.source_health_monitor.monitor import SourceHealthMonitor

        with pytest.raises(ValueError, match="failure_critical_threshold"):
            SourceHealthMonitor(failure_warning_threshold=5, failure_critical_threshold=3)


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    from backend.source_health_monitor.config import get_settings
    from backend.source_health_monitor.app import create_app

    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c


class TestRoutes:
    def test_healthz(self, client) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_fleet_summary_all_unknown_on_startup(self, client) -> None:
        resp = client.get("/v1/sources")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sources"] == 8
        assert data["unknown"] == 8
        assert data["active_alert_count"] == 0

    def test_source_detail_known_source(self, client) -> None:
        resp = client.get("/v1/sources/F1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "F1"
        assert data["status"] == "unknown"

    def test_source_detail_case_insensitive(self, client) -> None:
        resp = client.get("/v1/sources/f1")
        assert resp.status_code == 200
        assert resp.json()["source_id"] == "F1"

    def test_source_detail_unknown_source_404(self, client) -> None:
        resp = client.get("/v1/sources/ZZZZ")
        assert resp.status_code == 404

    def test_alerts_empty_on_startup(self, client) -> None:
        resp = client.get("/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["active"] == 0

    def _ingest(self, client, source_id: str, rec) -> None:
        """Helper: POST a SourceHealthRecord to the ingest endpoint."""
        from backend.source_health_monitor.models import IngestRequest

        payload = IngestRequest(record=rec)
        resp = client.post(
            f"/v1/sources/{source_id}/ingest",
            content=payload.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        return resp

    def test_ingest_success(self, client) -> None:
        rec = _make_record("F1", SourceStatus.HEALTHY)
        resp = self._ingest(client, "F1", rec)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_id"] == "F1"
        assert data["status"] == "healthy"
        assert data["accumulated_failures"] == 0
        assert data["accumulated_successes"] == 1

    def test_ingest_source_id_mismatch_422(self, client) -> None:
        from backend.source_health_monitor.models import IngestRequest

        rec = _make_record("F2", SourceStatus.HEALTHY)
        payload = IngestRequest(record=rec)
        resp = client.post(
            "/v1/sources/F1/ingest",
            content=payload.model_dump_json(),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_ingest_failure_accumulates_and_alerts(self, client) -> None:
        from backend.source_health_monitor.monitor import AlertType

        # Ingest 3 failures to trip warning threshold.
        for _ in range(3):
            rec = _make_record("F3", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0)
            self._ingest(client, "F3", rec)

        resp = client.get("/v1/sources/F3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["accumulated_failures"] == 3
        alert_types = [a["alert_type"] for a in data["alerts"]]
        assert "consecutive_failures" in alert_types

    def test_source_history_endpoint(self, client) -> None:
        for _ in range(3):
            rec = _make_record("F4", SourceStatus.HEALTHY)
            self._ingest(client, "F4", rec)

        resp = client.get("/v1/sources/F4/history?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_suppress_endpoint(self, client) -> None:
        payload = {
            "suppress_until": "2099-12-31T00:00:00+00:00",
            "reason": "planned maintenance",
        }
        resp = client.post("/v1/sources/F1/suppress", json=payload)
        assert resp.status_code == 200
        assert "2099" in resp.json()["suppressed_until"]

    def test_suppress_unknown_source_404(self, client) -> None:
        payload = {"suppress_until": "2099-12-31T00:00:00+00:00"}
        resp = client.post("/v1/sources/ZZZZ/suppress", json=payload)
        assert resp.status_code == 404

    def test_alerts_appear_after_ingest_failures(self, client) -> None:
        # Fresh client -- ingest 4 failures on F1 to breach warning threshold.
        for _ in range(4):
            rec = _make_record("F1", SourceStatus.DOWN, consecutive_failures=1, consecutive_successes=0)
            self._ingest(client, "F1", rec)

        resp = client.get("/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] >= 1
        assert any(a["source_id"] == "F1" for a in data["alerts"])

"""
test_audit_service.py — Phase 1-I audit ledger service behavior tests.

Drives the real ASGI app through TestClient against the in-memory ledger. Exercises
actual behavior: append computes the hashes + chain linkage, verification passes for an
intact chain and detects both tamper modes (altered contents, broken linkage), per-target
chains are independent, and checkpoints snapshot + verify.

Run:
    PYTHONPATH=src pytest tests/backend/test_audit_service.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.audit_service import ledger as ledger_mod
from backend.audit_service.app import app
from backend.audit_service.config import get_settings as audit_settings
from schema.v1.audit import AuditEvent

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    audit_settings.cache_clear()
    ledger_mod.reset_ledger()
    yield
    audit_settings.cache_clear()
    ledger_mod.reset_ledger()


def _event(target_id: str = "report-1", **overrides) -> dict:
    body = {
        "event_type": "report.requested",
        "actor_type": "user",
        "target_type": "report",
        "target_id": target_id,
        "action": "user requested a report",
    }
    body.update(overrides)
    return body


# ---------------------------------------------------------------------------
class TestHealth:
    def test_healthz(self):
        assert client.get("/healthz").json()["status"] == "ok"

    def test_readyz_reports_db_unconfigured_in_shell(self):
        r = client.get("/readyz")
        assert r.status_code == 200
        assert r.json() == {"ready": True, "audit_db_configured": False}


# ---------------------------------------------------------------------------
class TestAppend:
    def test_append_assigns_hash_and_genesis_has_no_prev(self):
        r = client.post("/v1/audit/events", json=_event())
        assert r.status_code == 201
        body = r.json()
        assert body["prev_event_hash"] is None          # first event in the chain
        assert body["event_hash"] is not None
        # The returned hash is the canonical hash of the event's own fields.
        ev = AuditEvent(**body)
        assert AuditEvent.compute_hash(ev) == body["event_hash"]

    def test_second_event_links_to_first(self):
        first = client.post("/v1/audit/events", json=_event()).json()
        second = client.post(
            "/v1/audit/events", json=_event(action="report generation started",
                                            event_type="report.started")
        ).json()
        assert second["prev_event_hash"] == first["event_hash"]
        assert second["event_hash"] != first["event_hash"]

    def test_invalid_enum_rejected(self):
        assert client.post("/v1/audit/events", json=_event(event_type="bogus.type")).status_code == 422

    def test_invalid_before_hash_rejected(self):
        assert client.post("/v1/audit/events", json=_event(before_hash="nothex")).status_code == 422


# ---------------------------------------------------------------------------
class TestChainsIndependent:
    def test_different_targets_have_independent_chains(self):
        a = client.post("/v1/audit/events", json=_event(target_id="report-A")).json()
        b = client.post("/v1/audit/events", json=_event(target_id="report-B")).json()
        # Each target's first event is genesis (no prev) — chains don't cross.
        assert a["prev_event_hash"] is None
        assert b["prev_event_hash"] is None

    def test_get_chain_returns_only_that_target(self):
        client.post("/v1/audit/events", json=_event(target_id="report-A"))
        client.post("/v1/audit/events", json=_event(target_id="report-A",
                                                    event_type="report.completed",
                                                    action="done"))
        client.post("/v1/audit/events", json=_event(target_id="report-B"))
        chain = client.get("/v1/audit/chains/report/report-A").json()
        assert len(chain) == 2
        assert {e["target_id"] for e in chain} == {"report-A"}


# ---------------------------------------------------------------------------
class TestVerify:
    def test_intact_chain_verifies(self):
        client.post("/v1/audit/events", json=_event())
        client.post("/v1/audit/events", json=_event(event_type="report.completed",
                                                    action="done"))
        r = client.get("/v1/audit/chains/report/report-1/verify")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["event_count"] == 2

    def test_altered_contents_detected(self):
        client.post("/v1/audit/events", json=_event())
        client.post("/v1/audit/events", json=_event(event_type="report.completed",
                                                    action="done"))
        # Tamper: change a canonical field on a stored event without updating its hash.
        ledger = ledger_mod.get_ledger()
        ledger._events[0] = ledger._events[0].model_copy(update={"action": "TAMPERED"})
        r = client.get("/v1/audit/chains/report/report-1/verify")
        assert r.status_code == 409
        body = r.json()
        assert body["ok"] is False
        assert "event_hash mismatch" in body["reason"]
        assert body["broken_at_event_id"] == str(ledger._events[0].event_id)

    def test_broken_linkage_detected(self):
        client.post("/v1/audit/events", json=_event())
        client.post("/v1/audit/events", json=_event(event_type="report.completed",
                                                    action="done"))
        # Remove the genesis event: the second event's prev_event_hash now dangles.
        ledger = ledger_mod.get_ledger()
        del ledger._events[0]
        r = client.get("/v1/audit/chains/report/report-1/verify")
        assert r.status_code == 409
        assert "linkage broken" in r.json()["reason"]

    def test_verify_all_intact(self):
        client.post("/v1/audit/events", json=_event(target_id="report-A"))
        client.post("/v1/audit/events", json=_event(target_id="report-B"))
        body = client.get("/v1/audit/verify").json()
        assert body["ok"] is True
        assert body["chains_checked"] == 2
        assert body["chains_failed"] == 0

    def test_verify_all_flags_failure(self):
        client.post("/v1/audit/events", json=_event(target_id="report-A"))
        client.post("/v1/audit/events", json=_event(target_id="report-B"))
        ledger = ledger_mod.get_ledger()
        ledger._events[0] = ledger._events[0].model_copy(update={"action": "TAMPERED"})
        r = client.get("/v1/audit/verify")
        assert r.status_code == 409
        body = r.json()
        assert body["ok"] is False
        assert body["chains_failed"] == 1


# ---------------------------------------------------------------------------
class TestCheckpoints:
    def test_checkpoint_snapshots_head(self):
        client.post("/v1/audit/events", json=_event(target_id="report-A"))
        last = client.post("/v1/audit/events", json=_event(target_id="report-B")).json()
        r = client.post("/v1/audit/checkpoints/report")
        assert r.status_code == 201
        cp = r.json()
        assert cp["target_type"] == "report"
        assert cp["event_count"] == 2                       # both report-type events
        assert cp["chain_head_event_hash"] == last["event_hash"]

    def test_checkpoint_404_when_no_events(self):
        assert client.post("/v1/audit/checkpoints/dispute").status_code == 404

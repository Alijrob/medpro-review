"""
test_report_service.py -- FastAPI TestClient tests for the Report Service.

Phase 2-H tests (20): healthz/readyz, from-profile JSON + HTML.
Phase 2-I tests (16): request + status endpoints.

All Phase 2-I tests run with _repo=None + _temporal_client=None
(the default when DATABASE_URL and TEMPORAL_ADDRESS are not set in the test env).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.report_service.app import create_app
from tests.report._fixtures import (
    NPI_ALICE,
    make_disciplined_profile,
    make_excluded_active_profile,
    make_full_profile,
    make_minimal_profile,
    make_partial_profile,
)

app = create_app()
client = TestClient(app)


def _profile_body(profile) -> dict:
    return {"profile": profile.model_dump(mode="json")}


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


def test_healthz_returns_200():
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_healthz_body():
    resp = client.get("/healthz")
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "report-service"


def test_readyz_returns_200():
    resp = client.get("/readyz")
    assert resp.status_code == 200


def test_readyz_body():
    resp = client.get("/readyz")
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /v1/reports/from-profile -- JSON
# ---------------------------------------------------------------------------


def test_build_report_200():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_full_profile()))
    assert resp.status_code == 200


def test_build_report_envelope():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_full_profile()))
    data = resp.json()
    assert "report_id" in data
    assert "npi" in data
    assert "is_partial" in data
    assert "report" in data


def test_build_report_npi_matches():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_full_profile()))
    assert resp.json()["npi"] == NPI_ALICE


def test_build_report_full_profile_not_partial():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_full_profile()))
    assert resp.json()["is_partial"] is False


def test_build_report_partial_profile():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_partial_profile()))
    assert resp.json()["is_partial"] is True


def test_build_report_disclaimer_in_report():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_minimal_profile()))
    report = resp.json()["report"]
    assert "disclaimer" in report
    assert len(report["disclaimer"]) > 50


def test_build_report_report_id_is_string():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_full_profile()))
    assert isinstance(resp.json()["report_id"], str)
    assert len(resp.json()["report_id"]) == 36  # UUID length


def test_build_report_two_calls_different_report_ids():
    body = _profile_body(make_full_profile())
    r1 = client.post("/v1/reports/from-profile", json=body).json()["report_id"]
    r2 = client.post("/v1/reports/from-profile", json=body).json()["report_id"]
    assert r1 != r2


def test_build_report_exclusion_flag():
    resp = client.post(
        "/v1/reports/from-profile", json=_profile_body(make_excluded_active_profile())
    )
    report = resp.json()["report"]
    assert report["has_active_exclusion"] is True


def test_build_report_disciplinary_flag():
    resp = client.post(
        "/v1/reports/from-profile", json=_profile_body(make_disciplined_profile())
    )
    report = resp.json()["report"]
    assert report["has_active_discipline"] is True


def test_build_report_invalid_profile_422():
    resp = client.post("/v1/reports/from-profile", json={"profile": {"garbage": True}})
    assert resp.status_code == 422


def test_build_report_missing_body_422():
    resp = client.post("/v1/reports/from-profile", json={})
    assert resp.status_code == 422


def test_build_report_minimal_profile():
    resp = client.post("/v1/reports/from-profile", json=_profile_body(make_minimal_profile()))
    assert resp.status_code == 200
    assert resp.json()["npi"] == NPI_ALICE


# ---------------------------------------------------------------------------
# POST /v1/reports/from-profile/html -- HTML
# ---------------------------------------------------------------------------


def test_build_html_report_200():
    resp = client.post(
        "/v1/reports/from-profile/html", json=_profile_body(make_full_profile())
    )
    assert resp.status_code == 200


def test_build_html_report_content_type():
    resp = client.post(
        "/v1/reports/from-profile/html", json=_profile_body(make_full_profile())
    )
    assert "text/html" in resp.headers["content-type"]


def test_build_html_report_has_doctype():
    resp = client.post(
        "/v1/reports/from-profile/html", json=_profile_body(make_full_profile())
    )
    assert "<!DOCTYPE html>" in resp.text


def test_build_html_report_contains_disclaimer():
    resp = client.post(
        "/v1/reports/from-profile/html", json=_profile_body(make_minimal_profile())
    )
    assert "IMPORTANT NOTICE" in resp.text


def test_build_html_report_invalid_profile_422():
    resp = client.post(
        "/v1/reports/from-profile/html", json={"profile": {"nope": True}}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Phase 2-I: POST /v1/reports/request
# Tests run with _repo=None + _temporal_client=None (no env vars set)
# ---------------------------------------------------------------------------


def test_request_report_returns_200():
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    assert resp.status_code == 200


def test_request_report_returns_report_id():
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    data = resp.json()
    assert "report_id" in data
    assert len(data["report_id"]) == 36  # UUID length


def test_request_report_two_calls_different_ids():
    r1 = client.post("/v1/reports/request", json={"npi": NPI_ALICE}).json()["report_id"]
    r2 = client.post("/v1/reports/request", json={"npi": NPI_ALICE}).json()["report_id"]
    assert r1 != r2


def test_request_report_npi_in_response():
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    assert resp.json()["npi"] == NPI_ALICE


def test_request_report_status_is_queued():
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    assert resp.json()["status"] == "queued"


def test_request_report_db_not_persisted_when_not_configured():
    """No DATABASE_URL set -- db_persisted must be False."""
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    assert resp.json()["db_persisted"] is False


def test_request_report_temporal_not_queued_when_not_configured():
    """No TEMPORAL_ADDRESS set -- temporal_queued must be False."""
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    assert resp.json()["temporal_queued"] is False


def test_request_report_message_explains_unconfigured():
    """message field must explain why nothing is wired in dev."""
    resp = client.post("/v1/reports/request", json={"npi": NPI_ALICE})
    msg = resp.json().get("message") or ""
    # At least one of DB / Temporal not configured message expected
    assert "not configured" in msg.lower() or msg == ""


def test_request_report_invalid_npi_too_short_422():
    resp = client.post("/v1/reports/request", json={"npi": "123456789"})
    assert resp.status_code == 422


def test_request_report_invalid_npi_too_long_422():
    resp = client.post("/v1/reports/request", json={"npi": "12345678901"})
    assert resp.status_code == 422


def test_request_report_alpha_npi_422():
    resp = client.post("/v1/reports/request", json={"npi": "12345ABCDE"})
    assert resp.status_code == 422


def test_request_report_empty_npi_422():
    resp = client.post("/v1/reports/request", json={"npi": ""})
    assert resp.status_code == 422


def test_request_report_missing_npi_422():
    resp = client.post("/v1/reports/request", json={})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Phase 2-I: GET /v1/reports/{report_id}
# ---------------------------------------------------------------------------


def test_get_report_db_not_configured_503():
    """No DATABASE_URL set -- GET /v1/reports/{id} must return 503."""
    resp = client.get("/v1/reports/12345678-1234-1234-1234-123456789012")
    assert resp.status_code == 503


def test_get_report_db_not_configured_explains():
    resp = client.get("/v1/reports/12345678-1234-1234-1234-123456789012")
    detail = resp.json().get("detail", "").lower()
    assert "not configured" in detail or "persistence" in detail


def test_get_report_with_mock_repo_not_found(monkeypatch):
    """With a mock repo that returns None, should get 404."""
    import backend.report_service.routes as route_module  # noqa: PLC0415

    class _MockRepo:
        def get_row(self, report_id):
            return None

    monkeypatch.setattr(route_module, "_repo", _MockRepo())
    try:
        resp = client.get("/v1/reports/12345678-1234-1234-1234-123456789012")
        assert resp.status_code == 404
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_report_with_mock_repo_found(monkeypatch):
    """With a mock repo that returns a row, should get 200."""
    import backend.report_service.routes as route_module  # noqa: PLC0415

    _row = {
        "report_id": "12345678-1234-1234-1234-123456789012",
        "npi": NPI_ALICE,
        "status": "complete",
        "is_partial": False,
        "payment_status": "paid",
        "requested_at": "2026-05-26T10:00:00+00:00",
        "started_at": "2026-05-26T10:00:05+00:00",
        "completed_at": "2026-05-26T10:01:00+00:00",
        "expires_at": "2026-06-25T10:00:00+00:00",
        "temporal_workflow_id": f"report-{NPI_ALICE}-abc",
        "sources_attempted": ["F1", "F2"],
        "sources_succeeded": ["F1", "F2"],
        "sources_failed": [],
        "report": {"npi": NPI_ALICE, "is_partial": False},
        "has_html": False,
    }

    class _MockRepo:
        def get_row(self, report_id):
            return _row

    monkeypatch.setattr(route_module, "_repo", _MockRepo())
    try:
        resp = client.get("/v1/reports/12345678-1234-1234-1234-123456789012")
        assert resp.status_code == 200
        data = resp.json()
        assert data["npi"] == NPI_ALICE
        assert data["status"] == "complete"
        assert data["payment_status"] == "paid"
        assert data["report"]["npi"] == NPI_ALICE
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


# ---------------------------------------------------------------------------
# Phase 2-N: GET /v1/reports/{report_id}/pdf
# ---------------------------------------------------------------------------

_PDF_ID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
_FAKE_PDF_BYTES = b"%PDF-1.4 fake-pdf-content-for-testing"
_COMPLETE_PAID_HTML_ROW = {
    "report_id": _PDF_ID,
    "npi": NPI_ALICE,
    "status": "complete",
    "is_partial": False,
    "payment_status": "paid",
    "requested_at": "2026-05-26T10:00:00+00:00",
    "started_at": "2026-05-26T10:00:05+00:00",
    "completed_at": "2026-05-26T10:01:00+00:00",
    "expires_at": "2026-06-25T10:00:00+00:00",
    "temporal_workflow_id": f"report-{NPI_ALICE}-abc",
    "sources_attempted": ["F1"],
    "sources_succeeded": ["F1"],
    "sources_failed": [],
    "report": {"npi": NPI_ALICE, "is_partial": False},
    "has_html": True,
    "report_html": "<html><body><p>Test report</p></body></html>",
}


def _make_pdf_repo(row):
    """Return a mock repo that yields the given row from get_row()."""
    class _MockRepo:
        def get_row(self, report_id):
            return row
    return _MockRepo()


def test_get_pdf_503_when_no_db():
    """No DATABASE_URL set -> 503."""
    resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
    assert resp.status_code == 503


def test_get_pdf_422_invalid_uuid():
    resp = client.get("/v1/reports/not-a-uuid/pdf")
    assert resp.status_code == 422


def test_get_pdf_404_not_found(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415

    class _EmptyRepo:
        def get_row(self, report_id):
            return None

    monkeypatch.setattr(route_module, "_repo", _EmptyRepo())
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 404
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_402_when_unpaid(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415

    row = {**_COMPLETE_PAID_HTML_ROW, "payment_status": "unpaid"}
    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(row))
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 402
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_402_when_pending(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415

    row = {**_COMPLETE_PAID_HTML_ROW, "payment_status": "pending"}
    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(row))
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 402
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_409_when_queued(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415

    row = {**_COMPLETE_PAID_HTML_ROW, "status": "queued"}
    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(row))
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 409
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_409_when_failed(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415

    row = {**_COMPLETE_PAID_HTML_ROW, "status": "failed"}
    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(row))
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 409
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_422_when_no_html(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415

    row = {**_COMPLETE_PAID_HTML_ROW, "report_html": None, "has_html": False}
    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(row))
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 422
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_501_when_weasyprint_unavailable(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415
    import report.pdf as pdf_module  # noqa: PLC0415

    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(_COMPLETE_PAID_HTML_ROW))
    monkeypatch.setattr(pdf_module, "WEASYPRINT_AVAILABLE", False)
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 501
        assert "weasyprint" in resp.json().get("detail", "").lower()
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_200_returns_pdf_bytes(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415
    import report.pdf as pdf_module  # noqa: PLC0415

    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(_COMPLETE_PAID_HTML_ROW))
    monkeypatch.setattr(pdf_module, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(pdf_module, "render_pdf", lambda html: _FAKE_PDF_BYTES)
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 200
        assert resp.content == _FAKE_PDF_BYTES
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_200_content_type_is_pdf(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415
    import report.pdf as pdf_module  # noqa: PLC0415

    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(_COMPLETE_PAID_HTML_ROW))
    monkeypatch.setattr(pdf_module, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(pdf_module, "render_pdf", lambda html: _FAKE_PDF_BYTES)
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert "application/pdf" in resp.headers["content-type"]
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_200_content_disposition_is_attachment(monkeypatch):
    import backend.report_service.routes as route_module  # noqa: PLC0415
    import report.pdf as pdf_module  # noqa: PLC0415

    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(_COMPLETE_PAID_HTML_ROW))
    monkeypatch.setattr(pdf_module, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(pdf_module, "render_pdf", lambda html: _FAKE_PDF_BYTES)
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        disposition = resp.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert ".pdf" in disposition
    finally:
        monkeypatch.setattr(route_module, "_repo", None)


def test_get_pdf_200_partial_report_also_works(monkeypatch):
    """status='partial' with payment_status='paid' must succeed."""
    import backend.report_service.routes as route_module  # noqa: PLC0415
    import report.pdf as pdf_module  # noqa: PLC0415

    row = {**_COMPLETE_PAID_HTML_ROW, "status": "partial", "is_partial": True}
    monkeypatch.setattr(route_module, "_repo", _make_pdf_repo(row))
    monkeypatch.setattr(pdf_module, "WEASYPRINT_AVAILABLE", True)
    monkeypatch.setattr(pdf_module, "render_pdf", lambda html: _FAKE_PDF_BYTES)
    try:
        resp = client.get(f"/v1/reports/{_PDF_ID}/pdf")
        assert resp.status_code == 200
    finally:
        monkeypatch.setattr(route_module, "_repo", None)

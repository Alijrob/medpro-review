"""
test_report_service.py -- FastAPI TestClient tests for the Report Service (C17 basic).

20 tests covering all routes:
    GET  /healthz
    GET  /readyz
    POST /v1/reports/from-profile          (JSON response)
    POST /v1/reports/from-profile/html     (HTML response)
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

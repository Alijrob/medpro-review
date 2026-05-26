"""
test_ny_courts.py -- New York eCourts WebCivil adapter tests (Phase 3-C).

Exercises NyCourtsConnector against stub transports (no live network).
Tests cover: config identity, contract harness, page-number/next-based pagination,
empty-page termination, camelCase normalization and alias mapping (caption variants,
RJI status), dict-wrapped and bare-list response shapes, and failure modes.

Run:
    PYTHONPATH=src pytest tests/connectors/test_ny_courts.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.court_records import NyCourtsConnector, ny_courts_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _ny_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "index_number": "150001/2022",
        "caption": "SMITH v. JONES MEMORIAL HOSPITAL",
        "court_name": "Supreme Court, New York County",
        "date_filed": "2022-07-01",
        "case_type": "Tort",
        "status": "Active",
    }
    row.update(over)
    return row


def _ny_row_camel(**over: Any) -> dict[str, Any]:
    """Row using camelCase field names."""
    row: dict[str, Any] = {
        "indexNumber": "101234/2021",
        "captionOnFiling": "DOE v. BROOKLYN MEDICAL CENTER",
        "courtName": "Supreme Court, Kings County",
        "dateFiled": "2021-03-15",
        "caseType": "Other Negligence",
        "rjiStatus": "Disposed",
    }
    row.update(over)
    return row


def _ny_row_alt_caption(**over: Any) -> dict[str, Any]:
    """Row using 'caseCaption' key variant."""
    row: dict[str, Any] = {
        "indexNumber": "200100/2023",
        "caseCaption": "ROE v. QUEENS HOSPITAL",
        "court": "Supreme Court, Queens County",
        "rjiDate": "2023-01-10",
        "natureOfAction": "Medical Malpractice",
        "caseStatus": "Active",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, Any]], has_next: bool = False) -> StubResponse:
    """Dict-wrapped response with 'cases' key and 'next' pagination field."""
    body = {
        "cases": rows,
        "next": "https://iapps.courts.state.ny.us/webcivil/api/cases?page=2" if has_next else None,
        "count": len(rows),
    }
    return StubResponse(json_body=body)


def _bare_list_page(rows: list[dict[str, Any]]) -> StubResponse:
    return StubResponse(json_body=rows)


def _recording_transport(*responses: StubResponse):
    calls: list[dict[str, Any]] = []
    seq = list(responses)

    async def _t(method: str, url: str, **kwargs: Any) -> StubResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _t, calls


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_court_ny(self):
        cfg = ny_courts_config()
        assert cfg.source_id == "court_ny"
        assert cfg.source_name == "New York eCourts WebCivil"
        assert cfg.source_category is SourceCategory.COURT
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_ny_courts(self):
        cfg = ny_courts_config()
        assert "courts.state.ny.us" in cfg.base_url

    def test_overrides_apply(self):
        cfg = ny_courts_config(rate_limit_per_sec=1.0)
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row(), _ny_row(index_number="999999/2022")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "court_ny" for r in result.records)


# ---------------------------------------------------------------------------
class TestPageNumberPagination:
    def test_follows_next_until_null(self):
        transport, calls = _recording_transport(
            _page([_ny_row(index_number="1"), _ny_row(index_number="2")], has_next=True),
            _page([_ny_row(index_number="3")], has_next=False),
        )
        conn = NyCourtsConnector(ny_courts_config(), transport=transport, page_size=2)
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2

    def test_empty_cases_terminates(self):
        transport, calls = _recording_transport(
            _page([_ny_row(index_number="1")], has_next=True),
            _page([], has_next=False),
        )
        conn = NyCourtsConnector(ny_courts_config(), transport=transport)
        result = asyncio.run(conn.run())
        assert result.record_count == 1
        assert len(calls) == 2

    def test_party_name_and_page_size_sent_in_params(self):
        transport, calls = _recording_transport(_page([_ny_row()]))
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=transport,
            party_name="Smith",
            page_size=50,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["partyName"] == "Smith"
        assert calls[0]["params"]["pageSize"] == 50
        assert calls[0]["params"]["page"] == 1

    def test_bare_list_response_accepted(self):
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_bare_list_page([_ny_row(), _ny_row(index_number="2")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_fields_normalized(self):
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("index_number", "caption", "court_name",
                      "date_filed", "case_type", "status"):
            assert field in raw, f"Missing: {field}"

    def test_case_caption_alias_maps_to_caption(self):
        """'caseCaption' variant should normalize to 'caption'."""
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row_alt_caption()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["caption"] == "ROE v. QUEENS HOSPITAL"

    def test_rji_status_maps_to_status(self):
        """'rjiStatus' should normalize to 'status'."""
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.records[0].raw["status"] == "Disposed"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _ny_row()
        del bad["court_name"]
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(_page([_ny_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = NyCourtsConnector(
            ny_courts_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

"""
test_court_listener.py -- CourtListener / RECAP Archive adapter tests
(Phase 3-C, C2).

Exercises CourtListenerConnector against stub transports (no live network).
Tests cover: config identity, contract harness, page-number/next-based pagination,
short-page and has_next=False termination, camelCase field normalization,
id coercion to str, None-to-empty-string normalization, and failure modes.

Run:
    PYTHONPATH=src pytest tests/connectors/test_court_listener.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.court_records import CourtListenerConnector, court_listener_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _cl_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "docket_id": "100001",
        "case_name": "Smith v. Memorial Hospital",
        "docket_number": "2:22-cv-01234",
        "court": "cacd",
        "date_filed": "2022-03-15",
        "nature_of_suit": "Personal Injury -- Medical",
    }
    row.update(over)
    return row


def _cl_row_camel(**over: Any) -> dict[str, Any]:
    """Row using API camelCase (and int id) as CourtListener may return."""
    row: dict[str, Any] = {
        "id": 100002,
        "caseName": "Jones v. General Hospital",
        "docketNumber": "1:21-cv-00567",
        "court": "nyed",
        "dateFiled": "2021-09-20",
        "natureOfSuit": "Medical Malpractice",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, Any]], has_next: bool = False) -> StubResponse:
    """Build a CourtListener-style paginated response."""
    body = {
        "count": len(rows),
        "next": "https://www.courtlistener.com/api/rest/v4/dockets/?page=2" if has_next else None,
        "previous": None,
        "results": rows,
    }
    return StubResponse(json_body=body)


def _recording_transport(*responses: StubResponse):
    calls: list[dict[str, Any]] = []
    seq = list(responses)

    async def _t(method: str, url: str, **kwargs: Any) -> StubResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _t, calls


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_court_listener(self):
        cfg = court_listener_config()
        assert cfg.source_id == "court_listener"
        assert cfg.source_name == "CourtListener / RECAP Archive"
        assert cfg.source_category is SourceCategory.COURT
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_courtlistener(self):
        cfg = court_listener_config()
        assert "courtlistener.com" in cfg.base_url

    def test_overrides_apply(self):
        cfg = court_listener_config(rate_limit_per_sec=1.0)
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([_cl_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([_cl_row(), _cl_row(docket_id="100099")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([_cl_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "court_listener" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_follows_next_until_null(self):
        transport, calls = _recording_transport(
            _page([_cl_row(docket_id="1"), _cl_row(docket_id="2")], has_next=True),
            _page([_cl_row(docket_id="3")], has_next=False),
        )
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2

    def test_empty_results_terminates(self):
        transport, calls = _recording_transport(
            _page([_cl_row(docket_id="1")], has_next=True),
            _page([], has_next=False),
        )
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 1
        assert len(calls) == 2

    def test_page_number_sent_in_params(self):
        transport, calls = _recording_transport(
            _page([_cl_row()], has_next=False),
        )
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=transport,
            page_size=50,
            party_name="Dr. Smith",
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["page"] == 1
        assert calls[0]["params"]["page_size"] == 50
        assert calls[0]["params"]["party_name"] == "Dr. Smith"

    def test_single_page_no_next_terminates_after_one_call(self):
        transport, calls = _recording_transport(
            _page([_cl_row(), _cl_row(docket_id="99")], has_next=False),
        )
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=transport,
            page_size=100,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 2
        assert len(calls) == 1


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_fields_normalized(self):
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([_cl_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("docket_id", "case_name", "docket_number",
                      "court", "date_filed", "nature_of_suit"):
            assert field in raw, f"Missing: {field}"

    def test_int_id_coerced_to_str(self):
        """API returns int for 'id'; contract requires str."""
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([_cl_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert isinstance(result.records[0].raw["docket_id"], str)

    def test_none_fields_normalized_to_empty_string(self):
        """date_filed=None should become '' not None."""
        row = _cl_row(date_filed=None)
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        # None becomes "" -- contract requires str, so schema drift should NOT fire
        assert result.status is FetchStatus.SUCCESS, result.errors


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _cl_row()
        del bad["nature_of_suit"]
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(_page([_cl_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=["bare", "list"])
        conn = CourtListenerConnector(
            court_listener_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

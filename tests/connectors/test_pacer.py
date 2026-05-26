"""
test_pacer.py -- PACER Case Locator adapter tests (Phase 3-C, C1).

Exercises PacerConnector against stub transports (no live network).
Tests cover: config identity, contract harness, page-number pagination with
totalPages termination, empty-content termination, camelCase normalization,
auth header injection, and failure modes.

Run:
    PYTHONPATH=src pytest tests/connectors/test_pacer.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.court_records import PacerConnector, pacer_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _pacer_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_id": "TXND-2022-CV-00123",
        "case_title": "SMITH VS JONES HOSPITAL INC",
        "case_number": "3:22-cv-00123",
        "court_id": "txnd",
        "date_filed": "2022-04-01",
        "case_type": "cv",
    }
    row.update(over)
    return row


def _pacer_row_camel(**over: Any) -> dict[str, Any]:
    """Row using PCL API camelCase field names."""
    row: dict[str, Any] = {
        "caseId": "CACD-2021-CV-05678",
        "caseTitle": "DOE VS MEMORIAL MEDICAL CENTER",
        "caseNumber": "2:21-cv-05678",
        "courtId": "cacd",
        "dateFiled": "2021-07-15",
        "caseType": "cv",
    }
    row.update(over)
    return row


def _page(
    rows: list[dict[str, Any]],
    total_pages: int = 1,
    page_num: int = 0,
) -> StubResponse:
    """Build a PACER PCL-style paginated response."""
    body = {
        "content": rows,
        "totalPages": total_pages,
        "totalElements": total_pages * len(rows),
        "number": page_num,
        "size": len(rows) or 50,
        "last": page_num >= total_pages - 1,
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
    def test_identity_is_pacer(self):
        cfg = pacer_config()
        assert cfg.source_id == "pacer"
        assert cfg.source_name == "PACER Case Locator (Federal Courts)"
        assert cfg.source_category is SourceCategory.COURT
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_pacer(self):
        cfg = pacer_config()
        assert "uscourts.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = pacer_config(rate_limit_per_sec=1.0)
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(_page([_pacer_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(
                _page([_pacer_row(), _pacer_row(case_id="TXND-2022-CV-99999")])
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(_page([_pacer_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "pacer" for r in result.records)


# ---------------------------------------------------------------------------
class TestPageNumberPagination:
    def test_pages_until_total_pages_reached(self):
        transport, calls = _recording_transport(
            _page([_pacer_row(case_id="1"), _pacer_row(case_id="2")], total_pages=2, page_num=0),
            _page([_pacer_row(case_id="3")], total_pages=2, page_num=1),
        )
        conn = PacerConnector(pacer_config(), transport=transport, page_size=2)
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["page"] == 0
        assert calls[1]["params"]["page"] == 1

    def test_empty_content_terminates_pagination(self):
        transport, calls = _recording_transport(
            _page([_pacer_row(case_id="1")], total_pages=1, page_num=0),
            _page([], total_pages=2, page_num=1),
        )
        conn = PacerConnector(pacer_config(), transport=transport, page_size=2)
        result = asyncio.run(conn.run())
        assert result.record_count == 1
        # First page terminates when page >= totalPages (page=1 >= totalPages=1)
        assert len(calls) == 1

    def test_party_name_params_sent(self):
        transport, calls = _recording_transport(_page([_pacer_row()]))
        conn = PacerConnector(
            pacer_config(),
            transport=transport,
            last_name="Smith",
            first_name="John",
            page_size=25,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["lastName"] == "Smith"
        assert calls[0]["params"]["firstName"] == "John"
        assert calls[0]["params"]["size"] == 25


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_fields_normalized(self):
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(_page([_pacer_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("case_id", "case_title", "case_number",
                      "court_id", "date_filed", "case_type"):
            assert field in raw, f"Missing: {field}"

    def test_auth_token_injected_in_header(self):
        """pacer_token should appear in the X-NEXT-GEN-CSO header."""
        transport, calls = _recording_transport(_page([_pacer_row()]))
        conn = PacerConnector(
            pacer_config(),
            transport=transport,
            pacer_token="test-token-abc123",
        )
        asyncio.run(conn.run())
        headers = calls[0].get("headers", {})
        assert headers.get("X-NEXT-GEN-CSO") == "test-token-abc123"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _pacer_row()
        del bad["case_type"]
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(_page([_pacer_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=[{"case_id": "x"}])
        conn = PacerConnector(
            pacer_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

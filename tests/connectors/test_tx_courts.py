"""
test_tx_courts.py -- Texas Courts Search adapter tests (Phase 3-C).

Exercises TxCourtsConnector against stub transports (no live network).
Tests cover: config identity, contract harness, offset/limit pagination,
short-page termination, camelCase and alias field normalization, dict-wrapped
response unwrapping, and failure modes.

Run:
    PYTHONPATH=src pytest tests/connectors/test_tx_courts.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.court_records import TxCourtsConnector, tx_courts_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _tx_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "case_number": "01-22-00123-CV",
        "style": "SMITH v. JONES HOSPITAL",
        "court": "1st Court of Appeals",
        "date_filed": "2022-05-10",
        "case_type": "CV",
        "status": "Active",
    }
    row.update(over)
    return row


def _tx_row_camel(**over: Any) -> dict[str, Any]:
    """Row using camelCase API field names."""
    row: dict[str, Any] = {
        "caseNumber": "14-21-00456-CV",
        "caseStyle": "DOE v. MEMORIAL MEDICAL",
        "courtName": "14th Court of Appeals",
        "dateFiled": "2021-11-30",
        "caseType": "CV",
        "caseStatus": "Disposed",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, Any]]) -> StubResponse:
    return StubResponse(json_body=rows)


def _wrapped_page(rows: list[dict[str, Any]], key: str = "results") -> StubResponse:
    return StubResponse(json_body={key: rows})


def _recording_transport(*responses: StubResponse):
    calls: list[dict[str, Any]] = []
    seq = list(responses)

    async def _t(method: str, url: str, **kwargs: Any) -> StubResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _t, calls


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_court_tx(self):
        cfg = tx_courts_config()
        assert cfg.source_id == "court_tx"
        assert cfg.source_name == "Texas Courts Search"
        assert cfg.source_category is SourceCategory.COURT
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_txcourts(self):
        cfg = tx_courts_config()
        assert "txcourts.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = tx_courts_config(rate_limit_per_sec=1.0)
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_page([_tx_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_page([_tx_row(), _tx_row(case_number="99-99-99999-CV")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_page([_tx_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "court_tx" for r in result.records)


# ---------------------------------------------------------------------------
class TestOffsetPagination:
    def test_pages_via_offset_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_tx_row(case_number="1"), _tx_row(case_number="2")]),
            _page([_tx_row(case_number="3")]),
        )
        conn = TxCourtsConnector(tx_courts_config(), transport=transport, page_size=2)
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_empty_array_terminates_pagination(self):
        transport, calls = _recording_transport(
            _page([_tx_row(case_number="1"), _tx_row(case_number="2")]),
            _page([]),
        )
        conn = TxCourtsConnector(tx_courts_config(), transport=transport, page_size=2)
        result = asyncio.run(conn.run())
        assert result.record_count == 2
        assert len(calls) == 2

    def test_party_name_sent_in_params(self):
        transport, calls = _recording_transport(_page([_tx_row()]))
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=transport,
            party_name="Smith, John",
            page_size=50,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["partyName"] == "Smith, John"
        assert calls[0]["params"]["limit"] == 50


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_fields_normalized(self):
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_page([_tx_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("case_number", "style", "court",
                      "date_filed", "case_type", "status"):
            assert field in raw, f"Missing: {field}"

    def test_dict_wrapped_response_results_key_unwrapped(self):
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_wrapped_page([_tx_row()], key="results")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_dict_wrapped_response_cases_key_unwrapped(self):
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_wrapped_page([_tx_row()], key="cases")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _tx_row()
        del bad["status"]
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(_page([_tx_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = TxCourtsConnector(
            tx_courts_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

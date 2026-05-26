"""
test_ny_op_nysed.py -- New York NYSED Office of Professions adapter tests (Phase 3-A, S2).

Exercises NyMedicalBoardConnector against stub transports (no live network).
Tests cover: config identity, contract harness, SODA 2.0 pagination, short-page
termination, non-list response handling, and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_ny_op_nysed.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import NyMedicalBoardConnector, ny_op_nysed_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _ny_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "NY-123456",
        "full_name": "John Doe",
        "profession_name": "Medicine",
        "license_status": "Registered",
        "issue_date": "2010-01-15",
        "expiration_date": "2026-01-15",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, str]]) -> StubResponse:
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
    def test_identity_is_state_board_ny_rest_api(self):
        cfg = ny_op_nysed_config()
        assert cfg.source_id == "state_board_ny"
        assert cfg.source_name == "New York NYSED Office of Professions"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_nysed(self):
        cfg = ny_op_nysed_config()
        assert "nysed.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = ny_op_nysed_config(rate_limit_per_sec=2.0, expected_min_records=1000)
        assert cfg.rate_limit_per_sec == 2.0
        assert cfg.expected_min_records == 1000

    def test_default_rate_limit(self):
        assert ny_op_nysed_config().rate_limit_per_sec == 5.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=stub_transport(_page([_ny_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=stub_transport(_page([_ny_row(), _ny_row(license_number="NY-999999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=stub_transport(_page([_ny_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_ny" for r in result.records)


# ---------------------------------------------------------------------------
class TestSodaPagination:
    def test_pages_via_offset_until_short_page(self):
        """Full page (2 rows) then short page (1 row) should stop after 2 requests."""
        transport, calls = _recording_transport(
            _page([_ny_row(license_number="1"), _ny_row(license_number="2")]),
            _page([_ny_row(license_number="3")]),
        )
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=transport,
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        # First page offset=0, second offset=2
        assert calls[0]["params"]["$offset"] == 0
        assert calls[1]["params"]["$offset"] == 2

    def test_first_short_page_makes_one_request(self):
        transport, calls = _recording_transport(_page([_ny_row()]))
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=transport,
            page_limit=5,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1

    def test_soda_params_include_limit_offset_order(self):
        transport, calls = _recording_transport(_page([_ny_row()]))
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=transport,
            page_limit=100,
        )
        asyncio.run(conn.run())
        params = calls[0]["params"]
        assert params["$limit"] == 100
        assert params["$offset"] == 0
        assert params["$order"] == ":id"

    def test_dataset_id_used_in_resource_path(self):
        transport, calls = _recording_transport(_page([_ny_row()]))
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=transport,
            dataset_id="test-dsid",
        )
        asyncio.run(conn.run())
        assert "test-dsid" in calls[0]["url"]


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_non_list_response_raises_source_unavailable(self):
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=stub_transport(StubResponse(json_body={"error": "bad request"})),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_missing_required_field_triggers_schema_drift(self):
        bad = _ny_row()
        del bad["profession_name"]
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=stub_transport(_page([_ny_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.record_count == 1
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)
        # Override json() to simulate a parse error
        original_json = stub.json

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = NyMedicalBoardConnector(
            ny_op_nysed_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

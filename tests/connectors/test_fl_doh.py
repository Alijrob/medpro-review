"""
test_fl_doh.py -- Florida Department of Health FDBPR adapter tests (Phase 3-A, S4).

Exercises FlDohConnector against stub transports (no live network).
Tests cover: config identity, contract harness, offset pagination, short-page
termination, field normalization (mixed-case FL DOH variants), dict-wrapped
response unwrapping (providers/results), and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_fl_doh.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import FlDohConnector, fl_doh_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _fl_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "ME12345",
        "last_name": "Johnson",
        "first_name": "Patricia",
        "license_status": "Active",
        "expiration_date": "03/31/2027",
        "license_type": "Medical Doctor (MD)",
    }
    row.update(over)
    return row


def _fl_row_mixed(**over: str) -> dict[str, str]:
    """Row using FL DOH mixed-case field names."""
    return {
        "LicenseNumber": "ME12345",
        "LastName": "Johnson",
        "FirstName": "Patricia",
        "LicenseStatus": "Active",
        "ExpirationDate": "03/31/2027",
        "ProfessionName": "Medical Doctor (MD)",
        **over,
    }


def _page(rows: list[dict[str, str]]) -> StubResponse:
    return StubResponse(json_body=rows)


def _wrapped(key: str, rows: list[dict[str, str]]) -> StubResponse:
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
    def test_identity_is_state_board_fl_rest_api(self):
        cfg = fl_doh_config()
        assert cfg.source_id == "state_board_fl"
        assert cfg.source_name == "Florida Department of Health FDBPR"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_fl_mqa(self):
        cfg = fl_doh_config()
        assert "doh.state.fl.us" in cfg.base_url

    def test_overrides_apply(self):
        cfg = fl_doh_config(expected_min_records=50000)
        assert cfg.expected_min_records == 50000


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_page([_fl_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_page([_fl_row(), _fl_row(license_number="DO99999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated(self):
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_page([_fl_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_fl" for r in result.records)


# ---------------------------------------------------------------------------
class TestOffsetPagination:
    def test_pages_via_offset_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_fl_row(license_number="1"), _fl_row(license_number="2")]),
            _page([_fl_row(license_number="3")]),
        )
        conn = FlDohConnector(
            fl_doh_config(),
            transport=transport,
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_single_short_page_makes_one_request(self):
        transport, calls = _recording_transport(_page([_fl_row()]))
        conn = FlDohConnector(
            fl_doh_config(),
            transport=transport,
            page_limit=100,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1

    def test_limit_sent_in_params(self):
        transport, calls = _recording_transport(_page([_fl_row()]))
        conn = FlDohConnector(
            fl_doh_config(),
            transport=transport,
            page_limit=500,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["limit"] == 500


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_mixed_case_fl_doh_fields_normalized(self):
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_page([_fl_row_mixed()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert "license_number" in raw
        assert "last_name" in raw
        assert "first_name" in raw
        assert "license_status" in raw
        assert "expiration_date" in raw
        assert "license_type" in raw

    def test_providers_key_unwrapped(self):
        """FL MQA may return {"providers": [...]}."""
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_wrapped("providers", [_fl_row()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_results_key_unwrapped(self):
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_wrapped("results", [_fl_row()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_profession_name_maps_to_license_type(self):
        row = _fl_row_mixed()
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        raw = result.records[0].raw
        assert raw.get("license_type") == "Medical Doctor (MD)"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_drift(self):
        bad = _fl_row()
        del bad["license_type"]
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(_page([_fl_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_list_response_fails_gracefully(self):
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(StubResponse(json_body="not a list")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse()

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = FlDohConnector(
            fl_doh_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

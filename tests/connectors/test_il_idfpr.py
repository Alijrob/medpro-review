"""
test_il_idfpr.py -- Illinois IDFPR license lookup adapter tests (Phase 3-A, S5).

Exercises IlIdfprConnector against stub transports (no live network).
Tests cover: config identity, contract harness, offset pagination, short-page
termination, field normalization (IDFPR mixed/uppercase variants), multiple dict
wrapper key variants (licenses/results/data/records), and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_il_idfpr.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import IlIdfprConnector, il_idfpr_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _il_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "036-123456",
        "full_name": "Dr. Maria Santos",
        "license_type": "Physician and Surgeon License",
        "license_status": "Active",
        "expiration_date": "2026-09-30",
    }
    row.update(over)
    return row


def _il_row_idfpr(**over: str) -> dict[str, str]:
    """Row using IDFPR's own mixed/uppercase field names."""
    return {
        "LicNum": "036-123456",
        "NAME": "Dr. Maria Santos",
        "LICTYPE": "Physician and Surgeon License",
        "STATUS": "Active",
        "EXP_DATE": "2026-09-30",
        **over,
    }


def _il_row_camel(**over: str) -> dict[str, str]:
    """Row using IDFPR camelCase variants."""
    return {
        "licenseNumber": "036-123456",
        "fullName": "Dr. Maria Santos",
        "licenseType": "Physician and Surgeon License",
        "licenseStatus": "Active",
        "expirationDate": "2026-09-30",
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
    def test_identity_is_state_board_il_rest_api(self):
        cfg = il_idfpr_config()
        assert cfg.source_id == "state_board_il"
        assert cfg.source_name == "Illinois IDFPR"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_idfpr(self):
        cfg = il_idfpr_config()
        assert "idfpr.illinois.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = il_idfpr_config(rate_limit_per_sec=1.5)
        assert cfg.rate_limit_per_sec == 1.5


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_page([_il_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_page([_il_row(), _il_row(license_number="036-999999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_page([_il_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_il" for r in result.records)


# ---------------------------------------------------------------------------
class TestOffsetPagination:
    def test_pages_via_offset_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_il_row(license_number="1"), _il_row(license_number="2")]),
            _page([_il_row(license_number="3")]),
        )
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=transport,
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_single_short_page_makes_one_request(self):
        transport, calls = _recording_transport(_page([_il_row()]))
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=transport,
            page_limit=100,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1

    def test_limit_and_offset_in_params(self):
        transport, calls = _recording_transport(_page([_il_row()]))
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=transport,
            page_limit=750,
        )
        asyncio.run(conn.run())
        p = calls[0]["params"]
        assert p["limit"] == 750
        assert p["offset"] == 0


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_idfpr_uppercase_variants_normalized(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_page([_il_row_idfpr()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert "license_number" in raw
        assert "full_name" in raw
        assert "license_type" in raw
        assert "license_status" in raw
        assert "expiration_date" in raw

    def test_camel_case_idfpr_variants_normalized(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_page([_il_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors

    def test_licenses_key_unwrapped(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_wrapped("licenses", [_il_row()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_records_key_unwrapped(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_wrapped("records", [_il_row()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_data_key_unwrapped(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_wrapped("data", [_il_row()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_drift(self):
        bad = _il_row()
        del bad["license_type"]
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(_page([_il_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_list_non_dict_response_fails_gracefully(self):
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(StubResponse(json_body=42)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse()

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = IlIdfprConnector(
            il_idfpr_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

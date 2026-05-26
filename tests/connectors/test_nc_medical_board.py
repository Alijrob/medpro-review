"""
test_nc_medical_board.py -- North Carolina Medical Board adapter tests
(Phase 3-B, S10).

Exercises NcMedicalBoardConnector against stub transports (no live network).
Tests cover: config identity, contract harness, page-number pagination, short-page
and empty-page termination, camelCase field normalization, dict-wrapped response
unwrapping, non-JSON/non-list failure modes, and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_nc_medical_board.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import NcMedicalBoardConnector, nc_medical_board_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _nc_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "NC-20000",
        "last_name": "Rivera",
        "first_name": "Maria",
        "license_status": "Active",
        "expiration_date": "2027-06-30",
        "specialty": "Family Medicine",
    }
    row.update(over)
    return row


def _nc_row_camel(**over: str) -> dict[str, str]:
    """Row using NCMB API camelCase field names."""
    row: dict[str, str] = {
        "licenseNumber": "NC-20000",
        "lastName": "Rivera",
        "firstName": "Maria",
        "licenseStatus": "Active",
        "expirationDate": "2027-06-30",
        "specialty": "Family Medicine",
    }
    row.update(over)
    return row


def _nc_row_primary_specialty(**over: str) -> dict[str, str]:
    """Row using 'primarySpecialty' key variant."""
    row: dict[str, str] = {
        "licenseNumber": "NC-20001",
        "lastName": "Lee",
        "firstName": "James",
        "licenseStatus": "Active",
        "expirationDate": "2027-06-30",
        "primarySpecialty": "Internal Medicine",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, str]]) -> StubResponse:
    return StubResponse(json_body=rows)


def _wrapped_page(rows: list[dict[str, str]], key: str = "data") -> StubResponse:
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
    def test_identity_is_state_board_nc_rest_api(self):
        cfg = nc_medical_board_config()
        assert cfg.source_id == "state_board_nc"
        assert cfg.source_name == "North Carolina Medical Board"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_ncmedboard(self):
        cfg = nc_medical_board_config()
        assert "ncmedboard.org" in cfg.base_url

    def test_overrides_apply(self):
        cfg = nc_medical_board_config(rate_limit_per_sec=1.0)
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_page([_nc_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_page([_nc_row(), _nc_row(license_number="NC-99999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_page([_nc_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_nc" for r in result.records)


# ---------------------------------------------------------------------------
class TestPageNumberPagination:
    def test_pages_via_page_number_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_nc_row(license_number="1"), _nc_row(license_number="2")]),
            _page([_nc_row(license_number="3")]),
        )
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["page"] == 1
        assert calls[1]["params"]["page"] == 2

    def test_empty_array_terminates_pagination(self):
        """NCMB returns [] on last page (same pattern as TX Medical Board)."""
        transport, calls = _recording_transport(
            _page([_nc_row(license_number="1"), _nc_row(license_number="2")]),
            _page([]),
        )
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 2
        assert len(calls) == 2

    def test_page_size_sent_in_params(self):
        transport, calls = _recording_transport(_page([_nc_row()]))
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=transport,
            page_size=250,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["pageSize"] == 250


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_fields_normalized(self):
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_page([_nc_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("license_number", "last_name", "first_name",
                      "license_status", "expiration_date", "specialty"):
            assert field in raw, f"Missing: {field}"

    def test_primary_specialty_mapped_to_specialty(self):
        """'primarySpecialty' key variant should normalize to 'specialty'."""
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_page([_nc_row_primary_specialty()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["specialty"] == "Internal Medicine"

    def test_dict_wrapped_response_data_key_unwrapped(self):
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_wrapped_page([_nc_row()], key="data")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_dict_wrapped_response_licenses_key_unwrapped(self):
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_wrapped_page([_nc_row()], key="licenses")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _nc_row()
        del bad["specialty"]
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(_page([_nc_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = NcMedicalBoardConnector(
            nc_medical_board_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

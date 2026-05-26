"""
test_pa_medical_board.py -- Pennsylvania State Medical Board adapter tests
(Phase 3-B, S7).

Exercises PaMedicalBoardConnector against stub transports (no live network).
Tests cover: config identity, contract harness, SODA 2.0 pagination, short-page
termination, field normalization (PALS/SODA column variants), non-list/non-JSON
failure modes, and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_pa_medical_board.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import PaMedicalBoardConnector, pa_medical_board_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _pa_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "PA-MD-654321-L",
        "last_name": "Chen",
        "first_name": "Wei",
        "license_type": "Medical Doctor",
        "license_status": "Active",
        "expiration_date": "2026-12-31",
    }
    row.update(over)
    return row


def _pa_row_pals_variants(**over: str) -> dict[str, str]:
    """Row using PA PALS system field name variants."""
    row: dict[str, str] = {
        "licnum": "PA-MD-654321-L",
        "lname": "Chen",
        "fname": "Wei",
        "lic_type": "Medical Doctor",
        "lic_status": "Active",
        "exp_date": "2026-12-31",
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
    def test_identity_is_state_board_pa_rest_api(self):
        cfg = pa_medical_board_config()
        assert cfg.source_id == "state_board_pa"
        assert cfg.source_name == "Pennsylvania State Medical Board"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_pa_opendata(self):
        cfg = pa_medical_board_config()
        assert "data.pa.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = pa_medical_board_config(rate_limit_per_sec=2.0, expected_min_records=1000)
        assert cfg.rate_limit_per_sec == 2.0
        assert cfg.expected_min_records == 1000


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(_page([_pa_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(_page([_pa_row(), _pa_row(license_number="PA-MD-999999-L")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(_page([_pa_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_pa" for r in result.records)


# ---------------------------------------------------------------------------
class TestSodaPagination:
    def test_pages_via_offset_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_pa_row(license_number="1"), _pa_row(license_number="2")]),
            _page([_pa_row(license_number="3")]),
        )
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=transport,
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["$offset"] == 0
        assert calls[1]["params"]["$offset"] == 2

    def test_first_short_page_makes_one_request(self):
        transport, calls = _recording_transport(_page([_pa_row()]))
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=transport,
            page_limit=5,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1

    def test_soda_params_include_limit_offset_order(self):
        transport, calls = _recording_transport(_page([_pa_row()]))
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=transport,
            page_limit=100,
        )
        asyncio.run(conn.run())
        params = calls[0]["params"]
        assert params["$limit"] == 100
        assert params["$offset"] == 0
        assert params["$order"] == ":id"

    def test_dataset_id_used_in_resource_path(self):
        transport, calls = _recording_transport(_page([_pa_row()]))
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=transport,
            dataset_id="test-pa-id",
        )
        asyncio.run(conn.run())
        assert "test-pa-id" in calls[0]["url"]


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_pals_column_variants_normalized(self):
        """licnum/lname/fname/lic_type/lic_status/exp_date -> contract names."""
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(_page([_pa_row_pals_variants()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert "license_number" in raw
        assert "last_name" in raw
        assert "first_name" in raw
        assert "license_type" in raw
        assert "license_status" in raw
        assert "expiration_date" in raw

    def test_renewal_date_mapped_to_expiration_date(self):
        """PA PALS sometimes uses 'renewal_date' instead of 'expiration_date'."""
        row = {
            "license_number": "PA-MD-111111-L",
            "last_name": "Smith",
            "first_name": "Alice",
            "license_type": "Medical Doctor",
            "license_status": "Active",
            "renewal_date": "2027-06-30",
        }
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["expiration_date"] == "2027-06-30"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _pa_row()
        del bad["license_status"]
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(_page([_pa_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_list_response_fails_with_source_unavailable(self):
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(StubResponse(json_body={"error": "service unavailable"})),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = PaMedicalBoardConnector(
            pa_medical_board_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

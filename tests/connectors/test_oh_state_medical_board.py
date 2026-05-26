"""
test_oh_state_medical_board.py -- Ohio State Medical Board adapter tests
(Phase 3-B, S8).

Exercises OhStateMedicalBoardConnector against stub transports (no live network).
Tests cover: config identity, contract harness, offset-based pagination,
short-page termination, camelCase/PascalCase field normalization, dict-wrapped
response unwrapping, non-JSON/non-list failure modes, and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_oh_state_medical_board.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import (
    OhStateMedicalBoardConnector,
    oh_state_medical_board_config,
)
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _oh_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "OH-35.123456",
        "last_name": "Patel",
        "first_name": "Priya",
        "license_type": "Physician (MD)",
        "license_status": "Active",
        "expiration_date": "2027-09-30",
    }
    row.update(over)
    return row


def _oh_row_camel(**over: str) -> dict[str, str]:
    """Row using Ohio eLicense camelCase field names."""
    row: dict[str, str] = {
        "licenseNumber": "OH-35.123456",
        "lastName": "Patel",
        "firstName": "Priya",
        "licenseType": "Physician (MD)",
        "licenseStatus": "Active",
        "expirationDate": "2027-09-30",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, str]]) -> StubResponse:
    return StubResponse(json_body=rows)


def _wrapped_page(rows: list[dict[str, str]], key: str = "providers") -> StubResponse:
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
    def test_identity_is_state_board_oh_rest_api(self):
        cfg = oh_state_medical_board_config()
        assert cfg.source_id == "state_board_oh"
        assert cfg.source_name == "Ohio State Medical Board"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_elicense_ohio(self):
        cfg = oh_state_medical_board_config()
        assert "elicense.ohio.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = oh_state_medical_board_config(rate_limit_per_sec=1.0)
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_page([_oh_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_page([_oh_row(), _oh_row(license_number="OH-35.999999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_page([_oh_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_oh" for r in result.records)


# ---------------------------------------------------------------------------
class TestOffsetPagination:
    def test_pages_via_offset_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_oh_row(license_number="1"), _oh_row(license_number="2")]),
            _page([_oh_row(license_number="3")]),
        )
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=transport,
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_first_short_page_makes_one_request(self):
        transport, calls = _recording_transport(_page([_oh_row()]))
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=transport,
            page_limit=5,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1

    def test_limit_sent_in_params(self):
        transport, calls = _recording_transport(_page([_oh_row()]))
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=transport,
            page_limit=250,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["limit"] == 250


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_fields_normalized(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_page([_oh_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("license_number", "last_name", "first_name",
                      "license_type", "license_status", "expiration_date"):
            assert field in raw, f"Missing: {field}"

    def test_dict_wrapped_response_providers_key_unwrapped(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_wrapped_page([_oh_row()], key="providers")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_dict_wrapped_response_results_key_unwrapped(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_wrapped_page([_oh_row()], key="results")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _oh_row()
        del bad["license_type"]
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(_page([_oh_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_list_non_dict_response_fails(self):
        conn = OhStateMedicalBoardConnector(
            oh_state_medical_board_config(),
            transport=stub_transport(StubResponse(json_body="unexpected string")),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

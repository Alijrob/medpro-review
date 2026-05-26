"""
test_tx_medical_board.py -- Texas Medical Board adapter tests (Phase 3-A, S3).

Exercises TxMedicalBoardConnector against stub transports (no live network).
Tests cover: config identity, contract harness, page-number pagination, short-page
and empty-page termination, camelCase field normalization, dict-wrapped response,
and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_tx_medical_board.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import TxMedicalBoardConnector, tx_medical_board_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _tx_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "TX-12345",
        "last_name": "Williams",
        "first_name": "Robert",
        "license_status": "Active",
        "expiration_date": "2027-06-30",
        "specialty": "Internal Medicine",
    }
    row.update(over)
    return row


def _tx_row_camel(**over: str) -> dict[str, str]:
    """Row using the TMB API's camelCase field names."""
    row: dict[str, str] = {
        "licenseNumber": "TX-12345",
        "lastName": "Williams",
        "firstName": "Robert",
        "licenseStatus": "Active",
        "expirationDate": "2027-06-30",
        "specialty": "Internal Medicine",
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, str]]) -> StubResponse:
    """Bare array response (most common TMB API shape)."""
    return StubResponse(json_body=rows)


def _wrapped_page(rows: list[dict[str, str]]) -> StubResponse:
    """Dict-wrapped response: {"data": [...]}."""
    return StubResponse(json_body={"data": rows})


def _recording_transport(*responses: StubResponse):
    calls: list[dict[str, Any]] = []
    seq = list(responses)

    async def _t(method: str, url: str, **kwargs: Any) -> StubResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _t, calls


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_state_board_tx_rest_api(self):
        cfg = tx_medical_board_config()
        assert cfg.source_id == "state_board_tx"
        assert cfg.source_name == "Texas Medical Board"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_tmb(self):
        cfg = tx_medical_board_config()
        assert "tmb.state.tx.us" in cfg.base_url

    def test_overrides_apply(self):
        cfg = tx_medical_board_config(rate_limit_per_sec=5.0)
        assert cfg.rate_limit_per_sec == 5.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(_page([_tx_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(_page([_tx_row(), _tx_row(license_number="TX-99999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated(self):
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(_page([_tx_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_tx" for r in result.records)


# ---------------------------------------------------------------------------
class TestPageNumberPagination:
    def test_pages_via_page_number_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_tx_row(license_number="1"), _tx_row(license_number="2")]),
            _page([_tx_row(license_number="3")]),
        )
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["page"] == 1
        assert calls[1]["params"]["page"] == 2

    def test_empty_array_terminates_pagination(self):
        """TMB returns [] on the last page rather than a short page."""
        transport, calls = _recording_transport(
            _page([_tx_row(license_number="1"), _tx_row(license_number="2")]),
            _page([]),  # empty = done
        )
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 2
        assert len(calls) == 2

    def test_page_size_sent_in_params(self):
        transport, calls = _recording_transport(_page([_tx_row()]))
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=transport,
            page_size=250,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["pageSize"] == 250


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_license_number_normalized(self):
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(_page([_tx_row_camel()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert "license_number" in raw
        assert "last_name" in raw
        assert "first_name" in raw
        assert "license_status" in raw
        assert "expiration_date" in raw

    def test_dict_wrapped_response_unwrapped(self):
        """API may return {"data": [...]} -- should be transparently unwrapped."""
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(_wrapped_page([_tx_row()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS

    def test_licenses_key_unwrapped(self):
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(StubResponse(json_body={"licenses": [_tx_row()]})),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_drift(self):
        bad = _tx_row()
        del bad["specialty"]
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(_page([_tx_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse()

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = TxMedicalBoardConnector(
            tx_medical_board_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

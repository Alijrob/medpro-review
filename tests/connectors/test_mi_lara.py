"""
test_mi_lara.py -- Michigan LARA Bureau of Professional Licensing adapter tests
(Phase 3-B, S9).

Exercises MiLaraConnector against stub transports (no live network). Tests cover:
config identity, contract harness, SODA 2.0 pagination, short-page termination,
field normalization (MI LARA/SODA column variants), non-list/non-JSON failure
modes, and schema drift detection.

Run:
    PYTHONPATH=src pytest tests/connectors/test_mi_lara.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.state_boards import MiLaraConnector, mi_lara_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- helpers ----------------------------------------------------------------

def _mi_row(**over: str) -> dict[str, str]:
    row: dict[str, str] = {
        "license_number": "MI-4301234567",
        "last_name": "Kim",
        "first_name": "Daniel",
        "license_type": "Physician and Surgeon",
        "license_status": "Active",
        "expiration_date": "2027-01-31",
    }
    row.update(over)
    return row


def _mi_row_lara_variants(**over: str) -> dict[str, str]:
    """Row using MI LARA CERTS/SODA column name variants."""
    row: dict[str, str] = {
        "licnumber": "MI-4301234567",
        "lname": "Kim",
        "fname": "Daniel",
        "lic_type": "Physician and Surgeon",
        "lic_status": "Active",
        "exp_date": "2027-01-31",
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
    def test_identity_is_state_board_mi_rest_api(self):
        cfg = mi_lara_config()
        assert cfg.source_id == "state_board_mi"
        assert cfg.source_name == "Michigan LARA Bureau of Professional Licensing"
        assert cfg.source_category is SourceCategory.STATE_BOARD
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_michigan_opendata(self):
        cfg = mi_lara_config()
        assert "data.michigan.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = mi_lara_config(rate_limit_per_sec=2.0, expected_min_records=5000)
        assert cfg.rate_limit_per_sec == 2.0
        assert cfg.expected_min_records == 5000


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(_page([_mi_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(_page([_mi_row(), _mi_row(license_number="MI-4309999999")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(_page([_mi_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "state_board_mi" for r in result.records)


# ---------------------------------------------------------------------------
class TestSodaPagination:
    def test_pages_via_offset_until_short_page(self):
        transport, calls = _recording_transport(
            _page([_mi_row(license_number="1"), _mi_row(license_number="2")]),
            _page([_mi_row(license_number="3")]),
        )
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=transport,
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["params"]["$offset"] == 0
        assert calls[1]["params"]["$offset"] == 2

    def test_first_short_page_makes_one_request(self):
        transport, calls = _recording_transport(_page([_mi_row()]))
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=transport,
            page_limit=5,
        )
        asyncio.run(conn.run())
        assert len(calls) == 1

    def test_soda_params_include_limit_offset_order(self):
        transport, calls = _recording_transport(_page([_mi_row()]))
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=transport,
            page_limit=100,
        )
        asyncio.run(conn.run())
        params = calls[0]["params"]
        assert params["$limit"] == 100
        assert params["$offset"] == 0
        assert params["$order"] == ":id"

    def test_dataset_id_used_in_resource_path(self):
        transport, calls = _recording_transport(_page([_mi_row()]))
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=transport,
            dataset_id="test-mi-dsid",
        )
        asyncio.run(conn.run())
        assert "test-mi-dsid" in calls[0]["url"]


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_lara_soda_column_variants_normalized(self):
        """licnumber/lname/fname/lic_type/lic_status/exp_date -> contract names."""
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(_page([_mi_row_lara_variants()])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        for field in ("license_number", "last_name", "first_name",
                      "license_type", "license_status", "expiration_date"):
            assert field in raw, f"Missing: {field}"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _mi_row()
        del bad["expiration_date"]
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(_page([_mi_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_list_response_fails_with_source_unavailable(self):
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(StubResponse(json_body={"error": "bad request"})),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = MiLaraConnector(
            mi_lara_config(),
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

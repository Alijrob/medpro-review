"""
test_healthgrades.py -- Healthgrades licensed provider data adapter tests
(Phase 3-D, D2).

Exercises HealthgradesConnector against stub transports (no live network).
Tests cover: config identity, contract harness (with dummy api_key), offset/limit
pagination with short-page sentinel, NPI and name query params, Authorization Bearer
header, camelCase field normalization, numeric-to-str coercion for rating/review_count,
None board_certifications coercion to [], schema drift, failure modes, and
AuthenticationError when api_key is absent.

Run:
    PYTHONPATH=src pytest tests/connectors/test_healthgrades.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.commercial import HealthgradesConnector, healthgrades_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

_DUMMY_KEY = "test-hg-api-key"


# --- helpers ------------------------------------------------------------------

def _hg_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "npi": "1234567890",
        "provider_name": "Dr. Robert Jones",
        "specialty": "Orthopedic Surgery",
        "rating": "4.2",
        "review_count": "87",
        "board_certifications": [{"board": "ABOS", "specialty": "Orthopedic Surgery"}],
    }
    row.update(over)
    return row


def _page(rows: list[dict[str, Any]], total: int | None = None) -> StubResponse:
    body: dict[str, Any] = {"providers": rows}
    if total is not None:
        body["total"] = total
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
    def test_identity_is_healthgrades(self):
        cfg = healthgrades_config()
        assert cfg.source_id == "healthgrades"
        assert cfg.source_name == "Healthgrades Provider Profiles"
        assert cfg.source_category is SourceCategory.COMMERCIAL_DIRECTORY
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_healthgrades(self):
        cfg = healthgrades_config()
        assert "healthgrades.com" in cfg.base_url

    def test_overrides_apply(self):
        cfg = healthgrades_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_hg_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_hg_row(), _hg_row(npi="9876543210")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_hg_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "healthgrades" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_short_page_terminates(self):
        """Last page shorter than page_size ends pagination."""
        transport, calls = _recording_transport(
            _page([_hg_row(npi="1"), _hg_row(npi="2")]),
            _page([_hg_row(npi="3")]),  # short page
        )
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2

    def test_full_pages_continue_until_short(self):
        transport, calls = _recording_transport(
            _page([_hg_row(npi="1"), _hg_row(npi="2")]),
            _page([_hg_row(npi="3"), _hg_row(npi="4")]),
            _page([_hg_row(npi="5")]),
        )
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 5
        assert len(calls) == 3

    def test_empty_page_terminates_immediately(self):
        transport, calls = _recording_transport(_page([]))
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 0
        assert len(calls) == 1

    def test_offset_advances_by_page_size(self):
        transport, calls = _recording_transport(
            _page([_hg_row(npi="1"), _hg_row(npi="2")]),
            _page([_hg_row(npi="3")]),
        )
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_npi_sent_in_params(self):
        transport, calls = _recording_transport(_page([_hg_row()]))
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            npi="1234567890",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["npi"] == "1234567890"


# ---------------------------------------------------------------------------
class TestAuthHeader:
    def test_bearer_header_sent(self):
        transport, calls = _recording_transport(_page([_hg_row()]))
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key="secret-bearer",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["headers"]["Authorization"] == "Bearer secret-bearer"

    def test_no_api_key_results_in_failed_run(self):
        """Without api_key, run() returns FAILED with an authentication error message."""
        conn = HealthgradesConnector(healthgrades_config())
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert any("api_key" in e for e in result.errors)


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_provider_name_normalized(self):
        row = {
            "npi": "1234567890",
            "providerName": "Dr. Alice Wu",
            "specialty": "Neurology",
            "rating": "4.5",
            "review_count": "210",
            "board_certifications": [],
        }
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["provider_name"] == "Dr. Alice Wu"

    def test_numeric_rating_coerced_to_str(self):
        row = _hg_row(rating=4.2)
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["rating"], str)
        assert result.records[0].raw["rating"] == "4.2"

    def test_numeric_review_count_coerced_to_str(self):
        row = _hg_row(review_count=87)
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["review_count"], str)

    def test_none_board_certifications_coerced_to_list(self):
        row = _hg_row(board_certifications=None)
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["board_certifications"] == []


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _hg_row()
        del bad["rating"]
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_hg_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=["bare", "list"])
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_list_providers_key_fails_gracefully(self):
        stub = StubResponse(json_body={"providers": "not-a-list", "total": 1})
        conn = HealthgradesConnector(
            healthgrades_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

"""
test_ribbon_health.py -- Ribbon Health provider directory adapter tests
(Phase 3-D, D1).

Exercises RibbonHealthConnector against stub transports (no live network).
Tests cover: config identity, contract harness (with dummy api_key), page-number
pagination (current_page/total_pages envelope), empty-data termination, NPI and
name query params, Authorization Token header, camelCase field normalization,
specialties-list-to-str coercion, None list coercion, schema drift, failure modes,
and AuthenticationError when api_key is absent.

Run:
    PYTHONPATH=src pytest tests/connectors/test_ribbon_health.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.commercial import RibbonHealthConnector, ribbon_health_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

_DUMMY_KEY = "test-ribbon-api-key"


# --- helpers ------------------------------------------------------------------

def _rh_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "npi": "1234567890",
        "provider_name": "Dr. Jane Smith",
        "specialty": "Internal Medicine",
        "locations": [{"address": "123 Main St", "city": "Boston", "state": "MA"}],
        "insurances": [{"plan": "Blue Cross PPO"}],
        "affiliations": [{"name": "Boston General Hospital"}],
    }
    row.update(over)
    return row


def _page(
    rows: list[dict[str, Any]],
    current_page: int = 1,
    total_pages: int = 1,
) -> StubResponse:
    body = {
        "data": rows,
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "count": len(rows),
        },
    }
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
    def test_identity_is_ribbon_health(self):
        cfg = ribbon_health_config()
        assert cfg.source_id == "ribbon_health"
        assert cfg.source_name == "Ribbon Health Provider Directory"
        assert cfg.source_category is SourceCategory.COMMERCIAL_DIRECTORY
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_base_url_points_to_ribbonhealth(self):
        cfg = ribbon_health_config()
        assert "ribbonhealth.com" in cfg.base_url

    def test_overrides_apply(self):
        cfg = ribbon_health_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_rh_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_rh_row(), _rh_row(npi="9876543210")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_rh_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "ribbon_health" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_multi_page_fetches_all(self):
        transport, calls = _recording_transport(
            _page([_rh_row(npi="1")], current_page=1, total_pages=2),
            _page([_rh_row(npi="2")], current_page=2, total_pages=2),
        )
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=1,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 2
        assert len(calls) == 2

    def test_single_page_stops_after_one_call(self):
        transport, calls = _recording_transport(
            _page([_rh_row(), _rh_row(npi="9")], current_page=1, total_pages=1),
        )
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 2
        assert len(calls) == 1

    def test_empty_data_terminates_immediately(self):
        transport, calls = _recording_transport(
            _page([], current_page=1, total_pages=3),
        )
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 0
        assert len(calls) == 1

    def test_page_number_and_npi_sent_in_params(self):
        transport, calls = _recording_transport(
            _page([_rh_row()], total_pages=1),
        )
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            npi="1234567890",
            transport=transport,
            page_size=50,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["page"] == 1
        assert calls[0]["params"]["page_size"] == 50
        assert calls[0]["params"]["npi"] == "1234567890"

    def test_provider_name_sent_in_params(self):
        transport, calls = _recording_transport(
            _page([_rh_row()], total_pages=1),
        )
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            provider_name="Dr. Smith",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["name"] == "Dr. Smith"


# ---------------------------------------------------------------------------
class TestAuthHeader:
    def test_authorization_token_header_sent(self):
        transport, calls = _recording_transport(_page([_rh_row()]))
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key="secret-token",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["headers"]["Authorization"] == "Token secret-token"

    def test_no_api_key_results_in_failed_run(self):
        """Without api_key, run() returns FAILED with an authentication error message."""
        conn = RibbonHealthConnector(ribbon_health_config())
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert any("api_key" in e for e in result.errors)


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_provider_name_normalized(self):
        """'name' key maps to 'provider_name'."""
        row = {
            "npi": "1234567890",
            "name": "Dr. John Doe",
            "specialty": "Cardiology",
            "locations": [],
            "insurances": [],
            "affiliations": [],
        }
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["provider_name"] == "Dr. John Doe"

    def test_specialties_list_coerced_to_first_element(self):
        """Ribbon may return 'specialties' as a list; normalize to first entry."""
        row = _rh_row()
        row.pop("specialty")
        row["specialties"] = ["Cardiology", "Internal Medicine"]
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["specialty"] == "Cardiology"

    def test_none_list_fields_coerced_to_empty_list(self):
        """None locations/insurances/affiliations become [] not None."""
        row = _rh_row(locations=None, insurances=None, affiliations=None)
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        raw = result.records[0].raw
        assert raw["locations"] == []
        assert raw["insurances"] == []
        assert raw["affiliations"] == []


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _rh_row()
        del bad["specialty"]
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_rh_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_wrong_type_for_list_field_triggers_drift(self):
        """locations must be list; sending a str triggers SCHEMA_DRIFT."""
        bad = _rh_row(locations="not-a-list")
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([bad])),
        )
        result = asyncio.run(conn.run())
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=["bare", "list"])
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_list_data_key_fails_gracefully(self):
        stub = StubResponse(json_body={"data": "not-a-list", "pagination": {}})
        conn = RibbonHealthConnector(
            ribbon_health_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

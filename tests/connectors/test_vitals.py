"""
test_vitals.py -- Vitals (WebMD Health Corp.) licensed provider data adapter tests
(Phase 3-D, D3).

Exercises VitalsConnector against stub transports (no live network).
Tests cover: config identity (source_id, WebMD parent in source_name), contract harness
(with dummy api_key), offset/limit pagination with short-page sentinel, NPI and name
query params, Authorization Bearer header, camelCase field normalization,
numeric-to-str coercion for rating/review_count, None education coercion to [],
schema drift, failure modes, and AuthenticationError when api_key is absent.

Run:
    PYTHONPATH=src pytest tests/connectors/test_vitals.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

from connectors import FetchStatus, IntegrationMethod
from connectors.sources.commercial import VitalsConnector, vitals_config
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

_DUMMY_KEY = "test-vitals-api-key"


# --- helpers ------------------------------------------------------------------

def _vt_row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "npi": "1234567890",
        "provider_name": "Dr. Maria Chen",
        "specialty": "Family Medicine",
        "rating": "4.6",
        "review_count": "134",
        "education": [{"school": "Harvard Medical School", "degree": "MD", "year": "2005"}],
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
    def test_identity_is_vitals(self):
        cfg = vitals_config()
        assert cfg.source_id == "vitals"
        assert cfg.source_category is SourceCategory.COMMERCIAL_DIRECTORY
        assert cfg.integration_method is IntegrationMethod.REST_API

    def test_source_name_includes_webmd(self):
        """Source name must reference WebMD Health Corp. as parent company."""
        cfg = vitals_config()
        assert "WebMD" in cfg.source_name

    def test_base_url_points_to_vitals(self):
        cfg = vitals_config()
        assert "vitals.com" in cfg.base_url

    def test_overrides_apply(self):
        cfg = vitals_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_contract_harness(self):
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_vt_row()])),
        )
        asyncio.run(assert_connector_contract(conn))

    def test_run_reports_healthy_on_success(self):
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_vt_row(), _vt_row(npi="9876543210")])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY

    def test_source_id_propagated_to_records(self):
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_vt_row()])),
        )
        result = asyncio.run(conn.run())
        assert all(r.source_id == "vitals" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_short_page_terminates(self):
        """Last page shorter than page_size ends pagination."""
        transport, calls = _recording_transport(
            _page([_vt_row(npi="1"), _vt_row(npi="2")]),
            _page([_vt_row(npi="3")]),
        )
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2

    def test_full_pages_continue_until_short(self):
        transport, calls = _recording_transport(
            _page([_vt_row(npi="1"), _vt_row(npi="2")]),
            _page([_vt_row(npi="3"), _vt_row(npi="4")]),
            _page([_vt_row(npi="5")]),
        )
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 5
        assert len(calls) == 3

    def test_empty_page_terminates_immediately(self):
        transport, calls = _recording_transport(_page([]))
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 0
        assert len(calls) == 1

    def test_offset_advances_by_page_size(self):
        transport, calls = _recording_transport(
            _page([_vt_row(npi="1"), _vt_row(npi="2")]),
            _page([_vt_row(npi="3")]),
        )
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=transport,
            page_size=2,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["offset"] == 0
        assert calls[1]["params"]["offset"] == 2

    def test_npi_sent_in_params(self):
        transport, calls = _recording_transport(_page([_vt_row()]))
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            npi="1234567890",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["params"]["npi"] == "1234567890"


# ---------------------------------------------------------------------------
class TestAuthHeader:
    def test_bearer_header_sent(self):
        transport, calls = _recording_transport(_page([_vt_row()]))
        conn = VitalsConnector(
            vitals_config(),
            api_key="secret-bearer",
            transport=transport,
        )
        asyncio.run(conn.run())
        assert calls[0]["headers"]["Authorization"] == "Bearer secret-bearer"

    def test_no_api_key_results_in_failed_run(self):
        """Without api_key, run() returns FAILED with an authentication error message."""
        conn = VitalsConnector(vitals_config())
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert any("api_key" in e for e in result.errors)


# ---------------------------------------------------------------------------
class TestFieldNormalization:
    def test_camel_case_provider_name_normalized(self):
        row = {
            "npi": "1234567890",
            "providerName": "Dr. Carlos Rivera",
            "specialty": "Pediatrics",
            "rating": "4.8",
            "review_count": "302",
            "education": [],
        }
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["provider_name"] == "Dr. Carlos Rivera"

    def test_training_alias_maps_to_education(self):
        """'training' key maps to 'education'."""
        row = {
            "npi": "1234567890",
            "provider_name": "Dr. Test",
            "specialty": "Radiology",
            "rating": "4.0",
            "review_count": "50",
            "training": [{"program": "Radiology Residency", "institution": "Mass General"}],
        }
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert "education" in result.records[0].raw

    def test_numeric_rating_coerced_to_str(self):
        row = _vt_row(rating=4.6)
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["rating"], str)

    def test_numeric_review_count_coerced_to_str(self):
        row = _vt_row(review_count=134)
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert isinstance(result.records[0].raw["review_count"], str)

    def test_none_education_coerced_to_list(self):
        row = _vt_row(education=None)
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([row])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS, result.errors
        assert result.records[0].raw["education"] == []


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_required_field_triggers_schema_drift(self):
        bad = _vt_row()
        del bad["education"]
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(_page([_vt_row(), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.health.schema_drift_detected is True

    def test_non_json_response_fails_gracefully(self):
        stub = StubResponse(json_body=None)

        def bad_json():
            raise ValueError("not JSON")

        stub.json = bad_json  # type: ignore[method-assign]
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_dict_response_fails_gracefully(self):
        stub = StubResponse(json_body=["bare", "list"])
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

    def test_non_list_providers_key_fails_gracefully(self):
        stub = StubResponse(json_body={"providers": "not-a-list", "total": 1})
        conn = VitalsConnector(
            vitals_config(),
            api_key=_DUMMY_KEY,
            transport=stub_transport(stub),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED

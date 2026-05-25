"""
test_nppes.py — NPPES / NPI Registry adapter (F1, C10, Phase 2-B.1) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport — no network, consistent with the Phase 0 legal gate.
They exercise: the reusable framework contract harness, query param building +
validation, pagination via `skip`, schema-drift detection (risk R6), and NPPES's
HTTP-200-with-`Errors` failure mode.

Run:
    PYTHONPATH=src pytest tests/connectors/test_nppes.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import NppesConnector, NppesQuery, nppes_config
from connectors.sources.nppes import API_PATH
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# --- fixtures ---------------------------------------------------------------
def nppes_result(npi: int = 1234567890, **over: Any) -> dict[str, Any]:
    """A representative NPPES API result (the shape the contract guards)."""
    r: dict[str, Any] = {
        "number": npi,
        "enumeration_type": "NPI-1",
        "basic": {"first_name": "Jane", "last_name": "Doe", "credential": "MD", "status": "A"},
        "addresses": [
            {
                "address_1": "1 Main St",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "address_purpose": "LOCATION",
            }
        ],
        "taxonomies": [
            {"code": "207R00000X", "desc": "Internal Medicine", "primary": True, "state": "TX"}
        ],
    }
    r.update(over)
    return r


def page(results: list[dict[str, Any]]) -> StubResponse:
    return StubResponse(json_body={"result_count": len(results), "results": results})


def recording_transport(*responses: StubResponse):
    """A transport that records each call's kwargs and returns responses in order."""
    calls: list[dict[str, Any]] = []
    seq = list(responses)

    async def _t(method: str, url: str, **kwargs: Any) -> StubResponse:
        calls.append({"method": method, "url": url, **kwargs})
        return seq.pop(0) if len(seq) > 1 else seq[0]

    return _t, calls


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_f1_federal_rest_api(self):
        cfg = nppes_config()
        assert cfg.source_id == "F1"
        assert cfg.source_name == "NPPES NPI Registry"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert cfg.base_url.endswith("npiregistry.cms.hhs.gov")

    def test_overrides_apply(self):
        assert nppes_config(rate_limit_per_sec=1.0).rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestQuery:
    def test_requires_a_search_criterion(self):
        with pytest.raises(Exception) as e:
            NppesQuery(state="TX")  # no number / last_name / organization_name
        assert "at least one of" in str(e.value)

    def test_number_only_omits_empty_fields(self):
        params = NppesQuery(number="1234567890").to_params()
        assert params == {"number": "1234567890"}

    def test_name_query_includes_set_fields_only(self):
        params = NppesQuery(last_name="Doe", state="TX", enumeration_type="NPI-1").to_params()
        assert params == {"last_name": "Doe", "state": "TX", "enumeration_type": "NPI-1"}

    def test_rejects_bad_npi_and_bad_state(self):
        with pytest.raises(Exception):
            NppesQuery(number="123")  # not 10 digits
        with pytest.raises(Exception):
            NppesQuery(last_name="Doe", state="texas")  # not a 2-letter code


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_response_passes_the_framework_harness(self):
        conn = NppesConnector(
            nppes_config(),
            query=NppesQuery(number="1234567890"),
            transport=stub_transport(page([nppes_result()])),
        )
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_run_wraps_results_and_reports_healthy(self):
        conn = NppesConnector(
            nppes_config(),
            query=NppesQuery(last_name="Doe"),
            transport=stub_transport(page([nppes_result(1), nppes_result(2)])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY
        # NPPES is a REST_API source, not bulk — bulk fields stay unset.
        assert result.health.bulk_download_record_count is None
        assert all(r.source_id == "F1" for r in result.records)


# ---------------------------------------------------------------------------
class TestPagination:
    def test_pages_via_skip_until_short_page(self):
        # page_size=2: a full first page (2) then a short page (1) ends the loop.
        transport, calls = recording_transport(
            page([nppes_result(1), nppes_result(2)]),
            page([nppes_result(3)]),
        )
        conn = NppesConnector(
            nppes_config(),
            query=NppesQuery(last_name="Doe"),
            transport=transport,
            page_size=2,
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        assert len(calls) == 2
        assert calls[0]["url"] == API_PATH
        assert calls[0]["params"]["skip"] == 0
        assert calls[1]["params"]["skip"] == 2
        # Every request carries the API version + the page limit.
        assert calls[0]["params"]["version"] == "2.1"
        assert calls[0]["params"]["limit"] == 2

    def test_single_short_page_makes_one_request(self):
        transport, calls = recording_transport(page([nppes_result(1)]))
        conn = NppesConnector(
            nppes_config(), query=NppesQuery(number="1234567890"), transport=transport, page_size=2
        )
        asyncio.run(conn.run())
        assert len(calls) == 1


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_schema_drift_flagged_when_a_field_is_missing(self):
        # First record is good; second drops `taxonomies` (a real R6 drift).
        bad = nppes_result(2)
        del bad["taxonomies"]
        conn = NppesConnector(
            nppes_config(),
            query=NppesQuery(last_name="Doe"),
            transport=stub_transport(page([nppes_result(1), bad])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL          # the good record survived
        assert result.record_count == 1
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_wrong_type_is_drift(self):
        conn = NppesConnector(
            nppes_config(),
            query=NppesQuery(last_name="Doe"),
            transport=stub_transport(page([nppes_result(1, basic=["not", "a", "dict"])])),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED           # drift on the only record
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_nppes_errors_array_fails_the_run(self):
        # NPPES reports a bad query as HTTP 200 + an `Errors` array, not a 4xx.
        conn = NppesConnector(
            nppes_config(),
            query=NppesQuery(number="1234567890"),
            transport=stub_transport(
                StubResponse(json_body={"Errors": [{"description": "Bad request", "field": "number"}]})
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.record_count == 0
        assert any("NPPES query rejected" in e for e in result.errors)

    def test_non_json_response_is_source_unavailable(self):
        class BadResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not json")

        conn = NppesConnector(
            nppes_config(max_retries=0),
            query=NppesQuery(number="1234567890"),
            transport=stub_transport(BadResp()),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

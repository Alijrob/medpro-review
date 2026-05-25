"""
test_cms_care_compare.py -- CMS Care Compare adapter (F4, C10, Phase 2-B.4) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport -- no network, consistent with the Phase 0 legal gate.
They exercise: the reusable framework contract harness, Socrata short-page pagination
termination (single page, multi-page, exact-page-size stop), one-row-per-location
semantics, schema-drift detection (missing required fields, wrong type), and failure
modes (non-JSON body, non-list response, HTTP 5xx).

Run:
    PYTHONPATH=src pytest tests/connectors/test_cms_care_compare.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import CmsCareCompareConnector, cms_care_compare_config
from connectors.sources.cms_care_compare import DEFAULT_DATASET_ID, PAGE_LIMIT
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


def cms_row(npi: str = "1234567890", **overrides: Any) -> dict[str, Any]:
    """A representative CMS Care Compare physician row (all required fields set)."""
    row: dict[str, Any] = {
        "npi": npi,
        "ind_pac_id": "0042370496",
        "ind_enrl_id": "I20120312000028",
        "last_name": "DOE",
        "first_name": "JOHN",
        "middle_name": "A",
        "suf": "",
        "gndr": "M",
        "cred": "MD",
        "med_sch": "HARVARD MEDICAL SCHOOL",
        "grd_yr": "1995",
        "pri_spec": "INTERNAL MEDICINE",
        "sec_spec_1": "",
        "org_nm": "ACME MEDICAL GROUP",
        "org_pac_id": "0042370000",
        "num_org_mem": "12",
        "adr_ln_1": "100 MAIN ST",
        "adr_ln_2": "SUITE 200",
        "cty": "BOSTON",
        "st": "MA",
        "zip": "021010000",
        "phn_numbr": "6175551234",
        "hosp_afl_1": "010001",
        "hosp_afl_2": "",
        "assgn": "Y",
        "telehlth": "Y",
    }
    row.update(overrides)
    return row


def cms_response(rows: list[dict[str, Any]]) -> StubResponse:
    """Build a StubResponse with a SODA-style JSON array body."""
    return StubResponse(json_body=rows)


def _connector(**kwargs: Any) -> CmsCareCompareConnector:
    """Shortcut: CmsCareCompareConnector with a test dataset_id and any overrides."""
    cfg_overrides = {k: v for k, v in kwargs.items() if k not in {"transport", "page_limit", "dataset_id"}}
    return CmsCareCompareConnector(
        cms_care_compare_config(**cfg_overrides),
        dataset_id=kwargs.get("dataset_id", DEFAULT_DATASET_ID),
        page_limit=kwargs.get("page_limit", PAGE_LIMIT),
        transport=kwargs.get("transport"),
    )


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_f4_federal_rest_api(self):
        cfg = cms_care_compare_config()
        assert cfg.source_id == "F4"
        assert cfg.source_name == "CMS Care Compare"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert "data.cms.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = cms_care_compare_config(expected_min_records=2_000_000, rate_limit_per_sec=1.0)
        assert cfg.expected_min_records == 2_000_000
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_row_passes_the_framework_harness(self):
        conn = _connector(transport=stub_transport(cms_response([cms_row()])))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_run_wraps_results_and_reports_healthy(self):
        rows = [cms_row("1111111111"), cms_row("2222222222")]
        conn = _connector(transport=stub_transport(cms_response(rows)))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY
        assert all(r.source_id == "F4" for r in result.records)
        # REST_API -- bulk_download_record_count should NOT be populated.
        assert result.health.bulk_download_record_count is None


# ---------------------------------------------------------------------------
class TestPagination:
    def test_single_page_short_response_stops_pagination(self):
        # page_limit=5, response has 3 rows → short page → stop after one request.
        rows = [cms_row(str(i) * 10) for i in range(1, 4)]
        conn = _connector(
            page_limit=5,
            transport=stub_transport(cms_response(rows)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_multi_page_fetches_all_rows(self):
        # page_limit=2, 5 rows total → 3 requests (2+2+1).
        rows = [cms_row(str(i) * 10) for i in range(5)]
        conn = _connector(
            page_limit=2,
            transport=stub_transport(
                cms_response(rows[0:2]),  # full page
                cms_response(rows[2:4]),  # full page
                cms_response(rows[4:5]),  # short page (1 < 2) → stop
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 5

    def test_empty_first_response_yields_zero_records(self):
        # No active records or dataset is empty -- valid response, not an error.
        conn = _connector(transport=stub_transport(cms_response([])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 0

    def test_exact_page_size_followed_by_empty_page_stops(self):
        # Full page (exact) then empty → the empty response triggers the stop.
        rows = [cms_row(str(i) * 10) for i in range(3)]
        conn = _connector(
            page_limit=3,
            transport=stub_transport(
                cms_response(rows),   # full page (3 == page_limit, so continue)
                cms_response([]),     # empty → stop
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_dataset_id_is_configurable(self):
        # Custom dataset_id is accepted; resource path is constructed from it.
        custom_id = "xxxx-9999"
        conn = CmsCareCompareConnector(
            cms_care_compare_config(),
            dataset_id=custom_id,
            page_limit=5,
            transport=stub_transport(cms_response([cms_row()])),
        )
        assert conn._dataset_id == custom_id
        result = asyncio.run(conn.run())
        assert result.record_count == 1

    def test_multiple_rows_same_npi_all_yielded(self):
        # One provider with 3 practice locations → 3 rows with the same NPI.
        # C11 normalization handles grouping; this adapter yields all rows.
        npi = "1234567890"
        rows = [
            cms_row(npi, adr_ln_1="100 MAIN ST", st="MA"),
            cms_row(npi, adr_ln_1="200 OAK AVE", st="NH"),
            cms_row(npi, adr_ln_1="300 ELM RD", st="VT"),
        ]
        conn = _connector(transport=stub_transport(cms_response(rows)))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3
        assert all(r.raw["npi"] == npi for r in result.records)


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_npi_field_is_schema_drift(self):
        bad_row = {k: v for k, v in cms_row().items() if k != "npi"}
        conn = _connector(transport=stub_transport(cms_response([bad_row])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_missing_assgn_field_is_schema_drift(self):
        # assgn (accepts assignment) is the key participation signal.
        bad_row = {k: v for k, v in cms_row().items() if k != "assgn"}
        conn = _connector(transport=stub_transport(cms_response([bad_row])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_wrong_type_on_npi_is_schema_drift(self):
        # If CMS returns npi as a number instead of a string -- type drift.
        bad_row = cms_row()
        bad_row["npi"] = 1234567890  # int, not str
        conn = _connector(transport=stub_transport(cms_response([bad_row])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_extra_fields_pass_through_unchanged(self):
        # CMS may add new fields; extra keys must not break the adapter.
        row = cms_row()
        row["new_quality_metric"] = "4.5"
        conn = _connector(transport=stub_transport(cms_response([row])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["new_quality_metric"] == "4.5"

    def test_non_json_response_is_source_unavailable(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not JSON -- got HTML maintenance page")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = CmsCareCompareConnector(
            cms_care_compare_config(max_retries=0),
            transport=_transport,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_non_list_json_response_is_source_unavailable(self):
        # If SODA returns a JSON object instead of an array (e.g., an error envelope).
        conn = _connector(
            max_retries=0,
            transport=stub_transport(StubResponse(json_body={"error": "dataset not found"})),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_http_503_marks_source_down(self):
        conn = _connector(
            max_retries=0,
            transport=stub_transport(StubResponse(status_code=503)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN
        assert result.record_count == 0

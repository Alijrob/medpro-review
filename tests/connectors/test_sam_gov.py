"""
test_sam_gov.py -- SAM.gov Exclusions adapter (F3, C10, Phase 2-B.3) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport -- no network, consistent with the Phase 0 legal gate.
They exercise: the reusable framework contract harness, REST API pagination
(totalRecords-based stop + empty-page sentinel), schema-drift detection (missing
required top-level key, risk R6), and failure modes (non-JSON body, HTTP 5xx).

Run:
    PYTHONPATH=src pytest tests/connectors/test_sam_gov.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import SamGovConnector, sam_gov_config
from connectors.sources.sam_gov import EXCLUSIONS_PATH, PAGE_SIZE
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_TEST_API_KEY = "test-api-key-f3"


def sam_record(**overrides: Any) -> dict[str, Any]:
    """A representative SAM.gov exclusion entityData item (both required top-level keys)."""
    record: dict[str, Any] = {
        "entityRegistration": {
            "ueiSAM": "TESTUE1234AB",
            "legalBusinessName": "ACME HEALTH SERVICES LLC",
            "exclusionStatusFlag": "Y",
        },
        "exclusionDetails": {
            "exclusionName": "ACME HEALTH SERVICES LLC",
            "firstName": "JOHN",
            "lastName": "DOE",
            "classification": "Firm",
            "exclusionType": "Ineligible (Proceedings Pending)",
            "exclusionDate": "2020-01-15",
            "terminationDate": None,
            "excludingAgencyCode": "HHS",
            "excludingAgencyName": "Dept of Health and Human Services",
            "npi": "1234567890",
            "exclusionProgram": "NON-PROCUREMENT",
        },
    }
    record.update(overrides)
    return record


def sam_response(
    items: list[dict[str, Any]],
    *,
    total: int | None = None,
) -> StubResponse:
    """Build a StubResponse with a valid SAM.gov exclusions JSON envelope."""
    effective_total = total if total is not None else len(items)
    return StubResponse(
        json_body={"totalRecords": effective_total, "entityData": items}
    )


def _connector(**kwargs: Any) -> SamGovConnector:
    """Shortcut: SamGovConnector with the test API key and any extra overrides."""
    cfg_overrides = {k: v for k, v in kwargs.items() if k not in {"transport", "page_size"}}
    transport = kwargs.get("transport")
    page_size = kwargs.get("page_size", PAGE_SIZE)
    return SamGovConnector(
        sam_gov_config(**cfg_overrides),
        api_key=_TEST_API_KEY,
        page_size=page_size,
        transport=transport,
    )


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_f3_federal_rest_api(self):
        cfg = sam_gov_config()
        assert cfg.source_id == "F3"
        assert cfg.source_name == "SAM.gov Exclusions"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert "api.sam.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = sam_gov_config(expected_min_records=70_000, rate_limit_per_sec=1.0)
        assert cfg.expected_min_records == 70_000
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_record_passes_the_framework_harness(self):
        conn = _connector(transport=stub_transport(sam_response([sam_record()])))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_run_wraps_results_and_reports_healthy(self):
        records = [sam_record(), sam_record(entityRegistration={"ueiSAM": "DIFFUE5678"})]
        conn = _connector(transport=stub_transport(sam_response(records)))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY
        assert all(r.source_id == "F3" for r in result.records)
        # REST_API source -- bulk_download_record_count should NOT be populated.
        assert result.health.bulk_download_record_count is None


# ---------------------------------------------------------------------------
class TestApiPagination:
    def test_single_page_stop_when_total_reached(self):
        # totalRecords=2, page_size=10 => one page is enough; after that fetch
        # (page+1)*10 = 10 >= 2, loop terminates.
        conn = _connector(
            page_size=10,
            transport=stub_transport(sam_response([sam_record(), sam_record()], total=2)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2

    def test_multi_page_pagination_fetches_all_records(self):
        # 3 records total, page_size=1 => 3 requests needed.
        rec_a = sam_record()
        rec_b = sam_record(entityRegistration={"ueiSAM": "BBBUE111111"})
        rec_c = sam_record(entityRegistration={"ueiSAM": "CCCUE222222"})
        conn = _connector(
            page_size=1,
            transport=stub_transport(
                sam_response([rec_a], total=3),
                sam_response([rec_b], total=3),
                sam_response([rec_c], total=3),
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_stops_on_empty_entity_data_sentinel(self):
        # Source returns totalRecords=5 but second page is empty -- respect the
        # empty-page sentinel even if totalRecords says there should be more.
        conn = _connector(
            page_size=2,
            transport=stub_transport(
                sam_response([sam_record(), sam_record()], total=5),
                sam_response([], total=5),  # unexpected empty -- still stop
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2

    def test_missing_total_records_falls_back_to_empty_page_stop(self):
        # If totalRecords is absent from the response, pagination uses only the
        # empty-page sentinel. First page has items; second is empty.
        page0_body = {"entityData": [sam_record()]}  # no totalRecords key
        page1_body = {"entityData": []}
        conn = _connector(
            page_size=1,
            transport=stub_transport(
                StubResponse(json_body=page0_body),
                StubResponse(json_body=page1_body),
            ),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1

    def test_extra_top_level_keys_pass_through(self):
        # SAM.gov may add fields (e.g., "links") to entityData items; they should
        # not break the adapter or the contract check.
        record = sam_record()
        record["futureField"] = "new_sam_value"
        conn = _connector(transport=stub_transport(sam_response([record])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["futureField"] == "new_sam_value"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_missing_exclusion_details_is_schema_drift(self):
        # Drop exclusionDetails -- a real R6 drift event.
        bad_record = {"entityRegistration": {"ueiSAM": "XYZUE999999"}}
        conn = _connector(transport=stub_transport(sam_response([bad_record])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_missing_entity_registration_is_schema_drift(self):
        # Drop entityRegistration -- the identity anchor is gone.
        bad_record = {"exclusionDetails": {"exclusionType": "Ineligible"}}
        conn = _connector(transport=stub_transport(sam_response([bad_record])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_wrong_type_on_exclusion_details_is_schema_drift(self):
        # SAM.gov returns a string instead of a dict for exclusionDetails -- type drift.
        bad_record = sam_record()
        bad_record["exclusionDetails"] = "FLAT_STRING"
        conn = _connector(transport=stub_transport(sam_response([bad_record])))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_non_json_response_is_source_unavailable(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not JSON -- got HTML error page")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = SamGovConnector(
            sam_gov_config(max_retries=0),
            api_key=_TEST_API_KEY,
            transport=_transport,
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

    def test_http_401_marks_source_down_auth_error(self):
        # 401 = bad or missing API key -- surfaces as AuthenticationError (non-retryable).
        conn = _connector(
            max_retries=0,
            transport=stub_transport(StubResponse(status_code=401)),
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.record_count == 0

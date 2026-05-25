"""
test_cms_medicaid_enrollment.py -- CMS Medicaid Enrollment adapter (I2, C10, Phase 2-B.6) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport -- no network, consistent with the Phase 0 legal gate.

Test coverage:
  - Config identity (I2, FEDERAL, REST_API)
  - Config overrides (expected_min_records, rate_limit_per_sec)
  - Framework contract harness
  - SODA pagination: single short page, multi-page, empty dataset, exact-page-then-empty
  - Dataset ID is configurable
  - Source ID stamped on all RawRecords
  - Schema drift: missing required field (npi, state_cd, provider_type_desc),
    wrong type on npi, extra fields pass through
  - Failure modes: non-JSON response, non-list JSON, HTTP 503

Run:
    PYTHONPATH=src pytest tests/connectors/test_cms_medicaid_enrollment.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import CmsMedicaidEnrollmentConnector, cms_medicaid_enrollment_config
from connectors.sources.cms_medicaid_enrollment import (
    DEFAULT_DATASET_ID,
    PAGE_LIMIT,
    _MEDICAID_REQUIRED_FIELDS,
)
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def medicaid_row(npi: str = "1234567890", **overrides: Any) -> dict[str, Any]:
    """A representative CMS Medicaid enrollment row (all required fields set)."""
    row: dict[str, Any] = {
        "npi": npi,
        "last_name": "DOE",
        "first_name": "JANE",
        "middle_name": "M",
        "state_cd": "TX",
        "provider_type_desc": "PRIMARY CARE PHYSICIAN",
        "provider_type_code": "01",
        "org_name": "",
        "enrollment_status": "ACTIVE",
    }
    row.update(overrides)
    return row


def soda(rows: list[dict[str, Any]]) -> StubResponse:
    """Build a SODA-style StubResponse (JSON array body)."""
    return StubResponse(json_body=rows)


def _connector(
    *transport_items: Any,
    page_limit: int = PAGE_LIMIT,
    dataset_id: str = DEFAULT_DATASET_ID,
    **cfg_overrides: Any,
) -> CmsMedicaidEnrollmentConnector:
    """Shortcut: build a connector with a stubbed transport."""
    return CmsMedicaidEnrollmentConnector(
        cms_medicaid_enrollment_config(**cfg_overrides),
        dataset_id=dataset_id,
        page_limit=page_limit,
        transport=stub_transport(*transport_items),
    )


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_i2_federal_rest_api(self):
        cfg = cms_medicaid_enrollment_config()
        assert cfg.source_id == "I2"
        assert cfg.source_name == "CMS Medicaid Enrollment"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert "data.cms.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = cms_medicaid_enrollment_config(expected_min_records=500_000, rate_limit_per_sec=2.0)
        assert cfg.expected_min_records == 500_000
        assert cfg.rate_limit_per_sec == 2.0

    def test_no_api_key_in_config(self):
        # I2 is a public SODA endpoint; no API key in config (unlike F3/SAM.gov).
        cfg = cms_medicaid_enrollment_config()
        assert not hasattr(cfg, "api_key")


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_conformant_row_passes_framework_harness(self):
        conn = _connector(soda([medicaid_row()]))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_full_run_with_one_row_is_healthy(self):
        conn = _connector(soda([medicaid_row()]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1
        assert result.health.status is SourceStatus.HEALTHY
        assert result.records[0].source_id == "I2"


# ---------------------------------------------------------------------------
class TestPagination:
    def test_single_short_page_stops_pagination(self):
        rows = [medicaid_row(str(i) * 10) for i in range(1, 4)]
        conn = _connector(soda(rows), page_limit=5)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_multi_page_fetches_all_rows(self):
        # page_limit=2; 5 rows -> 3 requests: (2 + 2 + 1).
        rows = [medicaid_row(str(i) * 10) for i in range(5)]
        conn = _connector(
            soda(rows[0:2]),  # full page
            soda(rows[2:4]),  # full page
            soda(rows[4:5]),  # short page -> stop
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 5

    def test_empty_dataset_is_valid_not_an_error(self):
        # A state with no Medicaid providers in the dataset should succeed cleanly.
        conn = _connector(soda([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 0

    def test_exact_page_size_followed_by_empty_page_stops(self):
        # 3 rows, page_limit=3: first page is full (continue); second is empty (stop).
        rows = [medicaid_row(str(i) * 10) for i in range(3)]
        conn = _connector(
            soda(rows),  # full page (3 == limit, continue)
            soda([]),    # empty -> stop
            page_limit=3,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_source_id_stamped_on_all_records(self):
        rows = [medicaid_row(str(i) * 10) for i in range(3)]
        conn = _connector(soda(rows))
        result = asyncio.run(conn.run())
        assert all(r.source_id == "I2" for r in result.records)


# ---------------------------------------------------------------------------
class TestDatasetId:
    def test_dataset_id_is_configurable(self):
        custom_id = "aaaa-1111"
        conn = CmsMedicaidEnrollmentConnector(
            cms_medicaid_enrollment_config(),
            dataset_id=custom_id,
            page_limit=5,
            transport=stub_transport(soda([medicaid_row()])),
        )
        assert conn._dataset_id == custom_id
        result = asyncio.run(conn.run())
        assert result.record_count == 1

    def test_default_dataset_id_is_set(self):
        # The default should be a non-empty string; actual value must be verified
        # against data.cms.gov before live ingest.
        conn = CmsMedicaidEnrollmentConnector(
            cms_medicaid_enrollment_config(),
            transport=stub_transport(soda([medicaid_row()])),
        )
        assert isinstance(conn._dataset_id, str)
        assert len(conn._dataset_id) > 0
        assert conn._dataset_id == DEFAULT_DATASET_ID


# ---------------------------------------------------------------------------
class TestSchemaDrift:
    def test_missing_npi_is_schema_drift(self):
        bad = {k: v for k, v in medicaid_row().items() if k != "npi"}
        conn = _connector(soda([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_missing_state_cd_is_schema_drift(self):
        # state_cd is the critical Medicaid-specific field (state-administered).
        bad = {k: v for k, v in medicaid_row().items() if k != "state_cd"}
        conn = _connector(soda([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_missing_provider_type_desc_is_schema_drift(self):
        bad = {k: v for k, v in medicaid_row().items() if k != "provider_type_desc"}
        conn = _connector(soda([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_wrong_type_on_npi_is_schema_drift(self):
        bad = medicaid_row()
        bad["npi"] = 1234567890  # int, not str
        conn = _connector(soda([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_extra_fields_pass_through_without_drift(self):
        row = medicaid_row()
        row["new_cms_field"] = "extra_value"
        row["another_new_field"] = "12345"
        conn = _connector(soda([row]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["new_cms_field"] == "extra_value"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_non_json_response_is_source_down(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not JSON -- got HTML maintenance page")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = CmsMedicaidEnrollmentConnector(
            cms_medicaid_enrollment_config(max_retries=0),
            transport=_transport,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_non_list_json_is_source_down(self):
        # SODA error envelope (object instead of array).
        conn = _connector(
            StubResponse(json_body={"error": "dataset not found"}),
            max_retries=0,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_http_503_marks_source_down(self):
        conn = _connector(StubResponse(status_code=503), max_retries=0)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN
        assert result.record_count == 0

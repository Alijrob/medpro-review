"""
test_cms_medicare_enrollment.py -- CMS Medicare Enrollment adapter (I1, C10, Phase 2-B.5) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport -- no network, consistent with the Phase 0 legal gate.

Test coverage:
  - Config identity (I1, FEDERAL, REST_API)
  - Framework contract harness (enrollment, opt-out, combined)
  - Enrollment dataset SODA pagination (short page, multi-page, empty, exact+empty)
  - Opt-out dataset SODA pagination (short page, multi-page, empty)
  - Record-type tagging (_record_type = "enrollment" | "opt_out")
  - Combined run: enrollment records precede opt-out records
  - Schema drift detection (enrollment missing field, opt-out missing field,
    wrong types, extra fields pass through)
  - Failure modes (non-JSON, non-list, HTTP 5xx, enrollment-ok/opt-out-fails partial)

Run:
    PYTHONPATH=src pytest tests/connectors/test_cms_medicare_enrollment.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import CmsMedicareEnrollmentConnector, cms_medicare_enrollment_config
from connectors.sources.cms_medicare_enrollment import (
    DEFAULT_ENROLLMENT_DATASET_ID,
    DEFAULT_OPT_OUT_DATASET_ID,
    PAGE_LIMIT,
    RECORD_TYPE_ENROLLMENT,
    RECORD_TYPE_OPT_OUT,
    _RECORD_TYPE_KEY,
)
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def enroll_row(npi: str = "1234567890", **overrides: Any) -> dict[str, Any]:
    """A representative Medicare enrollment row (all required fields set)."""
    row: dict[str, Any] = {
        "npi": npi,
        "last_name": "DOE",
        "first_name": "JOHN",
        "middle_name": "A",
        "enroll_id": "I20120312000028",
        "provider_type_code": "14",
        "provider_type_desc": "PHYSICIAN/SURGEON",
        "state_cd": "MA",
        "org_name": "",
    }
    row.update(overrides)
    return row


def opt_out_row(npi: str = "1234567890", **overrides: Any) -> dict[str, Any]:
    """A representative opt-out affidavit row (all required fields set)."""
    row: dict[str, Any] = {
        "npi": npi,
        "last_name": "DOE",
        "first_name": "JOHN",
        "specialty_desc": "Internal Medicine",
        "optout_effective_date": "01/01/2023",
        "optout_end_date": "",          # blank = still within 2-year opt-out window
        "order_refer_flag": "Y",
        "first_approved_date": "01/01/2023",
    }
    row.update(overrides)
    return row


def soda(rows: list[dict[str, Any]]) -> StubResponse:
    """Build a SODA-style StubResponse (JSON array body)."""
    return StubResponse(json_body=rows)


def _connector(*transport_items: Any, page_limit: int = PAGE_LIMIT, **cfg_overrides: Any) -> CmsMedicareEnrollmentConnector:
    """Shortcut: build a connector with a stubbed transport."""
    conn_kwargs: dict[str, Any] = {}
    for k in ("enrollment_dataset_id", "opt_out_dataset_id"):
        if k in cfg_overrides:
            conn_kwargs[k] = cfg_overrides.pop(k)
    return CmsMedicareEnrollmentConnector(
        cms_medicare_enrollment_config(**cfg_overrides),
        page_limit=page_limit,
        transport=stub_transport(*transport_items),
        **conn_kwargs,
    )


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_i1_federal_rest_api(self):
        cfg = cms_medicare_enrollment_config()
        assert cfg.source_id == "I1"
        assert cfg.source_name == "CMS Medicare Enrollment"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert "data.cms.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = cms_medicare_enrollment_config(expected_min_records=900_000, rate_limit_per_sec=1.0)
        assert cfg.expected_min_records == 900_000
        assert cfg.rate_limit_per_sec == 1.0


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_enrollment_conformant_row_passes_framework_harness(self):
        # Enrollment page (1 row) + empty opt-out → SUCCESS, 1 record.
        conn = _connector(soda([enroll_row()]), soda([]))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_opt_out_conformant_row_passes_framework_harness(self):
        # Empty enrollment + opt-out page (1 row) → SUCCESS, 1 record.
        conn = _connector(soda([]), soda([opt_out_row()]))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_combined_run_with_both_datasets_is_healthy(self):
        conn = _connector(soda([enroll_row()]), soda([opt_out_row()]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2
        assert result.health.status is SourceStatus.HEALTHY
        assert all(r.source_id == "I1" for r in result.records)


# ---------------------------------------------------------------------------
class TestEnrollmentPagination:
    def test_single_short_enrollment_page_stops_pagination(self):
        rows = [enroll_row(str(i) * 10) for i in range(1, 4)]
        conn = _connector(soda(rows), soda([]), page_limit=5)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_multi_page_enrollment_fetches_all_rows(self):
        # page_limit=2; 5 enrollment rows → 3 requests (2+2+1); then empty opt-out.
        rows = [enroll_row(str(i) * 10) for i in range(5)]
        conn = _connector(
            soda(rows[0:2]),    # full page
            soda(rows[2:4]),    # full page
            soda(rows[4:5]),    # short page → stop
            soda([]),           # opt-out empty
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 5

    def test_empty_enrollment_dataset_is_not_an_error(self):
        # Empty enrollment is valid; move on to opt-out.
        conn = _connector(soda([]), soda([opt_out_row()]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1

    def test_exact_enrollment_page_size_followed_by_empty_stops(self):
        # 3 rows, page_limit=3: first page is full → request another;
        # second page is empty → stop.
        rows = [enroll_row(str(i) * 10) for i in range(3)]
        conn = _connector(
            soda(rows),   # full page (3 == limit, continue)
            soda([]),     # empty → stop enrollment
            soda([]),     # empty opt-out
            page_limit=3,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3


# ---------------------------------------------------------------------------
class TestOptOutPagination:
    def test_single_short_opt_out_page_stops_pagination(self):
        rows = [opt_out_row(str(i) * 10) for i in range(1, 3)]
        conn = _connector(soda([]), soda(rows), page_limit=5)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2

    def test_multi_page_opt_out_fetches_all_rows(self):
        # page_limit=2; 3 opt-out rows → 2 requests (2+1).
        rows = [opt_out_row(str(i) * 10) for i in range(3)]
        conn = _connector(
            soda([]),           # enrollment empty
            soda(rows[0:2]),    # opt-out full page
            soda(rows[2:3]),    # opt-out short page → stop
            page_limit=2,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_empty_opt_out_dataset_is_not_an_error(self):
        # A provider database with no opt-outs is valid.
        conn = _connector(soda([enroll_row()]), soda([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1


# ---------------------------------------------------------------------------
class TestRecordTypeTags:
    def test_enrollment_rows_are_tagged_enrollment(self):
        rows = [enroll_row("1111111111"), enroll_row("2222222222")]
        conn = _connector(soda(rows), soda([]))
        result = asyncio.run(conn.run())
        assert all(r.raw[_RECORD_TYPE_KEY] == RECORD_TYPE_ENROLLMENT for r in result.records)

    def test_opt_out_rows_are_tagged_opt_out(self):
        rows = [opt_out_row("3333333333"), opt_out_row("4444444444")]
        conn = _connector(soda([]), soda(rows))
        result = asyncio.run(conn.run())
        assert all(r.raw[_RECORD_TYPE_KEY] == RECORD_TYPE_OPT_OUT for r in result.records)

    def test_combined_run_enrollment_records_precede_opt_out_records(self):
        # Enrollment rows first, opt-out rows second -- order is guaranteed.
        conn = _connector(
            soda([enroll_row("1111111111"), enroll_row("2222222222")]),
            soda([opt_out_row("3333333333")]),
        )
        result = asyncio.run(conn.run())
        assert result.record_count == 3
        types = [r.raw[_RECORD_TYPE_KEY] for r in result.records]
        assert types == [RECORD_TYPE_ENROLLMENT, RECORD_TYPE_ENROLLMENT, RECORD_TYPE_OPT_OUT]

    def test_dataset_ids_are_configurable(self):
        custom_enroll = "aaaa-1111"
        custom_opt_out = "bbbb-2222"
        conn = CmsMedicareEnrollmentConnector(
            cms_medicare_enrollment_config(),
            enrollment_dataset_id=custom_enroll,
            opt_out_dataset_id=custom_opt_out,
            page_limit=5,
            transport=stub_transport(soda([enroll_row()]), soda([])),
        )
        assert conn._enrollment_dataset_id == custom_enroll
        assert conn._opt_out_dataset_id == custom_opt_out
        result = asyncio.run(conn.run())
        assert result.record_count == 1


# ---------------------------------------------------------------------------
class TestSchemaDrift:
    def test_enrollment_missing_npi_is_schema_drift(self):
        bad = {k: v for k, v in enroll_row().items() if k != "npi"}
        conn = _connector(soda([bad]), soda([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_enrollment_missing_enroll_id_is_schema_drift(self):
        bad = {k: v for k, v in enroll_row().items() if k != "enroll_id"}
        conn = _connector(soda([bad]), soda([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_opt_out_missing_optout_effective_date_is_schema_drift(self):
        bad = {k: v for k, v in opt_out_row().items() if k != "optout_effective_date"}
        conn = _connector(soda([]), soda([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_opt_out_missing_order_refer_flag_is_schema_drift(self):
        bad = {k: v for k, v in opt_out_row().items() if k != "order_refer_flag"}
        conn = _connector(soda([]), soda([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_wrong_type_on_enrollment_npi_is_schema_drift(self):
        bad = enroll_row()
        bad["npi"] = 1234567890  # int, not str
        conn = _connector(soda([bad]), soda([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_extra_fields_on_enrollment_pass_through_unchanged(self):
        row = enroll_row()
        row["new_cms_field"] = "some_value"
        conn = _connector(soda([row]), soda([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["new_cms_field"] == "some_value"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_non_json_from_enrollment_endpoint_is_source_down(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not JSON -- got HTML maintenance page")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = CmsMedicareEnrollmentConnector(
            cms_medicare_enrollment_config(max_retries=0),
            transport=_transport,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_non_list_json_from_opt_out_endpoint_is_source_down(self):
        # SODA error envelope (object instead of array) on the opt-out request.
        conn = _connector(
            soda([]),                                                    # enrollment empty
            StubResponse(json_body={"error": "dataset not found"}),     # opt-out bad
            max_retries=0,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_http_503_on_enrollment_marks_source_down(self):
        conn = _connector(StubResponse(status_code=503), max_retries=0)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN
        assert result.record_count == 0

    def test_enrollment_succeeds_opt_out_fails_yields_partial(self):
        # Enrollment pass returns 2 records; opt-out returns a 503 → PARTIAL.
        conn = _connector(
            soda([enroll_row("1111111111"), enroll_row("2222222222")]),  # enrollment ok
            StubResponse(status_code=503),                               # opt-out fail
            max_retries=0,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.PARTIAL
        assert result.record_count == 2
        assert all(r.raw[_RECORD_TYPE_KEY] == RECORD_TYPE_ENROLLMENT for r in result.records)

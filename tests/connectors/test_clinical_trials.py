"""
test_clinical_trials.py -- ClinicalTrials.gov adapter (A2, C10, Phase 2-B.9) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport -- no network, consistent with the Phase 0 legal gate.

Test coverage:
  - Config identity (A2, FEDERAL, REST_API)
  - Config overrides
  - Framework contract harness
  - Cursor-based pagination: no next token (last page), multi-page, empty studies list
  - investigator_name passed as constructor arg
  - Schema drift: missing protocolSection, wrong type on protocolSection, extra fields pass through
  - Failure modes: non-JSON response, non-dict response, missing studies list, HTTP 503

Run:
    PYTHONPATH=src pytest tests/connectors/test_clinical_trials.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import ClinicalTrialsConnector, clinical_trials_config
from connectors.sources.clinical_trials import DEFAULT_PAGE_SIZE
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def study(nct_id: str = "NCT01234567", **overrides: Any) -> dict[str, Any]:
    """A representative ClinicalTrials.gov study record (required fields set)."""
    rec: dict[str, Any] = {
        "protocolSection": {
            "identificationModule": {
                "nctId": nct_id,
                "officialTitle": "A Phase III Study of Novel Drug",
            },
            "statusModule": {
                "overallStatus": "COMPLETED",
            },
            "contactsLocationsModule": {
                "overallOfficials": [
                    {"name": "Doe, John MD", "role": "PRINCIPAL_INVESTIGATOR", "affiliation": "Mass General Hospital"}
                ],
            },
        },
        "derivedSection": {},
        "hasResults": True,
    }
    rec.update(overrides)
    return rec


def ct_resp(
    studies: list[dict[str, Any]],
    next_token: str | None = None,
    total_count: int | None = None,
) -> StubResponse:
    """Build a stubbed ClinicalTrials.gov API v2 response."""
    body: dict[str, Any] = {
        "studies": studies,
        "totalCount": total_count or len(studies),
    }
    if next_token is not None:
        body["nextPageToken"] = next_token
    return StubResponse(json_body=body)


def _connector(
    *transport_items: Any,
    investigator_name: str = "Doe John",
    page_size: int = DEFAULT_PAGE_SIZE,
    **cfg_overrides: Any,
) -> ClinicalTrialsConnector:
    """Shortcut: build a connector with a stubbed transport."""
    return ClinicalTrialsConnector(
        clinical_trials_config(**cfg_overrides),
        investigator_name=investigator_name,
        page_size=page_size,
        transport=stub_transport(*transport_items),
    )


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_a2_federal_rest_api(self):
        cfg = clinical_trials_config()
        assert cfg.source_id == "A2"
        assert cfg.source_name == "ClinicalTrials.gov"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert "clinicaltrials.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = clinical_trials_config(rate_limit_per_sec=2.0)
        assert cfg.rate_limit_per_sec == 2.0

    def test_no_api_key_in_config(self):
        # ClinicalTrials.gov requires no API key.
        cfg = clinical_trials_config()
        assert not hasattr(cfg, "api_key")


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_single_study_passes_framework_harness(self):
        conn = _connector(ct_resp([study()]))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_full_run_with_one_study_is_healthy(self):
        conn = _connector(ct_resp([study("NCT99999999")]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1
        assert result.health.status is SourceStatus.HEALTHY
        assert result.records[0].source_id == "A2"


# ---------------------------------------------------------------------------
class TestPagination:
    def test_no_next_token_stops_after_first_page(self):
        # Response has no nextPageToken -> single page, stop.
        studies = [study(f"NCT{i:08d}") for i in range(3)]
        conn = _connector(ct_resp(studies))  # no next_token
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_next_token_triggers_second_page(self):
        # Page 1 has nextPageToken; page 2 does not -> 2 pages total.
        s1 = [study(f"NCT0000000{i}") for i in range(2)]
        s2 = [study(f"NCT9999999{i}") for i in range(2)]
        conn = _connector(
            ct_resp(s1, next_token="cursor-abc"),  # first page
            ct_resp(s2),                            # second page (no next token)
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 4

    def test_multi_page_with_three_pages(self):
        pages = [
            [study(f"NCT1111{i:04d}") for i in range(2)],
            [study(f"NCT2222{i:04d}") for i in range(2)],
            [study(f"NCT3333{i:04d}") for i in range(2)],
        ]
        conn = _connector(
            ct_resp(pages[0], next_token="cursor-1"),
            ct_resp(pages[1], next_token="cursor-2"),
            ct_resp(pages[2]),  # last page
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 6

    def test_empty_studies_list_is_valid_success(self):
        # Provider has no clinical trials -- valid (most providers have none).
        conn = _connector(ct_resp([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 0

    def test_investigator_name_passed_as_constructor_arg(self):
        conn = ClinicalTrialsConnector(
            clinical_trials_config(),
            investigator_name="Smith Jane",
            transport=stub_transport(ct_resp([])),
        )
        assert conn._investigator_name == "Smith Jane"
        result = asyncio.run(conn.run())
        assert result.record_count == 0


# ---------------------------------------------------------------------------
class TestSchemaDrift:
    def test_missing_protocol_section_is_schema_drift(self):
        bad = {"derivedSection": {}, "hasResults": False}  # no protocolSection
        conn = _connector(ct_resp([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_wrong_type_on_protocol_section_is_schema_drift(self):
        bad = study()
        bad["protocolSection"] = "not-a-dict"  # str, not dict
        conn = _connector(ct_resp([bad]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_extra_fields_in_study_pass_through_without_drift(self):
        s = study("NCT55555555")
        s["newClinicalTrialsField"] = "extra_data"
        conn = _connector(ct_resp([s]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["newClinicalTrialsField"] == "extra_data"

    def test_extra_fields_inside_protocol_section_pass_through(self):
        s = study("NCT66666666")
        s["protocolSection"]["newModule"] = {"key": "value"}
        conn = _connector(ct_resp([s]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_non_json_response_is_source_down(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not JSON")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = ClinicalTrialsConnector(
            clinical_trials_config(max_retries=0),
            investigator_name="Doe John",
            transport=_transport,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_non_dict_json_is_source_down(self):
        bad = StubResponse(json_body=["unexpected", "array"])
        conn = _connector(bad, max_retries=0)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_missing_studies_list_is_source_down(self):
        bad = StubResponse(json_body={"nextPageToken": "abc", "totalCount": 0})
        conn = _connector(bad, max_retries=0)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_http_503_marks_source_down(self):
        conn = _connector(StubResponse(status_code=503), max_retries=0)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN
        assert result.record_count == 0

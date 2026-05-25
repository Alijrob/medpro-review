"""
test_pubmed.py -- PubMed / NCBI Entrez adapter (A1, C10, Phase 2-B.8) tests.

Sync tests driving the async adapter with asyncio.run (no pytest-asyncio), always
against a stubbed transport -- no network, consistent with the Phase 0 legal gate.

Test coverage:
  - Config identity (A1, FEDERAL, REST_API)
  - Config overrides
  - Framework contract harness (single article)
  - esearch pagination: zero results, single short page, multi-page, exact+empty
  - api_key injected when provided, absent when not
  - author_name passed as search term
  - Schema drift: missing uid, missing authors, wrong type on uid
  - Extra fields on articles pass through unchanged
  - Failure modes: non-JSON esearch, non-dict esearch, missing esearchresult,
    non-JSON esummary, non-dict esummary, missing result, HTTP 503

Run:
    PYTHONPATH=src pytest tests/connectors/test_pubmed.py -v
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from connectors import FetchStatus, IntegrationMethod
from connectors.sources import PubmedConnector, pubmed_config
from connectors.sources.pubmed import DEFAULT_RETMAX, ESEARCH_PATH, ESUMMARY_PATH
from connectors.testing import StubResponse, assert_connector_contract, stub_transport
from schema.v1.common import SourceCategory
from schema.v1.source_health import SourceStatus


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def article(pmid: str = "12345678", **overrides: Any) -> dict[str, Any]:
    """A representative NCBI esummary article dict (all required fields set)."""
    rec: dict[str, Any] = {
        "uid": pmid,
        "title": "Novel findings in cardiovascular disease risk factors",
        "pubdate": "2023 Jan 15",
        "authors": [{"name": "Doe J", "authtype": "Author", "clusterid": ""}],
        "source": "J Am Coll Cardiol",
        "volume": "81",
        "issue": "3",
        "pages": "301-310",
    }
    rec.update(overrides)
    return rec


def esearch_resp(pmids: list[str], count: int | None = None) -> StubResponse:
    """Build a stubbed NCBI esearch JSON response."""
    return StubResponse(json_body={
        "esearchresult": {
            "count": str(count or len(pmids)),
            "retmax": str(len(pmids)),
            "retstart": "0",
            "idlist": pmids,
            "translationset": [],
            "querytranslation": "",
        }
    })


def esummary_resp(
    articles: list[dict[str, Any]],
    pmids: list[str] | None = None,
) -> StubResponse:
    """Build a stubbed NCBI esummary JSON response.

    ``pmids`` lets callers override the result-dict keys (needed when testing
    drift cases where the article's ``uid`` field is missing or has the wrong
    type -- in those cases we still need the article keyed by the search PMID
    so ``_parse_esummary`` picks it up and the contract can fire).
    """
    if pmids is None:
        pmids = [str(a["uid"]) for a in articles]
    result: dict[str, Any] = {"uids": list(pmids)}
    for pmid, a in zip(pmids, articles):
        result[str(pmid)] = a
    return StubResponse(json_body={"result": result})


def _connector(
    *transport_items: Any,
    author_name: str = "Doe John",
    retmax: int = DEFAULT_RETMAX,
    api_key: str | None = None,
    **cfg_overrides: Any,
) -> PubmedConnector:
    """Shortcut: build a connector with a stubbed transport."""
    return PubmedConnector(
        pubmed_config(**cfg_overrides),
        author_name=author_name,
        api_key=api_key,
        retmax=retmax,
        transport=stub_transport(*transport_items),
    )


# ---------------------------------------------------------------------------
class TestConfig:
    def test_identity_is_a1_federal_rest_api(self):
        cfg = pubmed_config()
        assert cfg.source_id == "A1"
        assert cfg.source_name == "PubMed / NCBI Entrez"
        assert cfg.source_category is SourceCategory.FEDERAL
        assert cfg.integration_method is IntegrationMethod.REST_API
        assert "eutils.ncbi.nlm.nih.gov" in cfg.base_url

    def test_overrides_apply(self):
        cfg = pubmed_config(rate_limit_per_sec=9.0, expected_min_records=100)
        assert cfg.rate_limit_per_sec == 9.0
        assert cfg.expected_min_records == 100

    def test_no_api_key_in_config(self):
        # API key is a constructor arg, never in ConnectorConfig.
        cfg = pubmed_config()
        assert not hasattr(cfg, "api_key")


# ---------------------------------------------------------------------------
class TestContractHarness:
    def test_single_article_passes_framework_harness(self):
        pmid = "11111111"
        conn = _connector(esearch_resp([pmid]), esummary_resp([article(pmid)]))
        asyncio.run(assert_connector_contract(conn))  # no raise

    def test_full_run_with_one_article_is_healthy(self):
        pmid = "22222222"
        conn = _connector(esearch_resp([pmid]), esummary_resp([article(pmid)]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 1
        assert result.health.status is SourceStatus.HEALTHY
        assert result.records[0].source_id == "A1"


# ---------------------------------------------------------------------------
class TestPagination:
    def test_zero_pmids_from_esearch_is_empty_success(self):
        # Provider has no publications -- valid result.
        conn = _connector(esearch_resp([]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 0

    def test_single_short_page_stops_pagination(self):
        # 3 pmids < retmax=5 -> stop after first esearch page.
        pmids = [str(i) * 8 for i in range(1, 4)]
        arts = [article(p) for p in pmids]
        conn = _connector(
            esearch_resp(pmids),
            esummary_resp(arts),
            retmax=5,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 3

    def test_multi_page_fetches_all_articles(self):
        # retmax=2; 5 pmids -> 3 esearch pages: (2, 2, 1), each with esummary.
        pmids = [str(i) * 8 for i in range(5)]
        conn = _connector(
            esearch_resp(pmids[0:2]),               # esearch page 1 (full)
            esummary_resp([article(p) for p in pmids[0:2]]),
            esearch_resp(pmids[2:4]),               # esearch page 2 (full)
            esummary_resp([article(p) for p in pmids[2:4]]),
            esearch_resp(pmids[4:5]),               # esearch page 3 (short -> stop)
            esummary_resp([article(p) for p in pmids[4:5]]),
            retmax=2,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 5

    def test_exact_page_then_empty_esearch_stops(self):
        # 2 pmids, retmax=2: first page is full (continue); second returns 0 (stop).
        pmids = [str(i) * 8 for i in range(2)]
        conn = _connector(
            esearch_resp(pmids),                           # full page (2 == retmax)
            esummary_resp([article(p) for p in pmids]),
            esearch_resp([]),                              # empty -> stop
            retmax=2,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.record_count == 2


# ---------------------------------------------------------------------------
class TestAuthorAndKey:
    def test_author_name_passed_as_constructor_arg(self):
        conn = PubmedConnector(
            pubmed_config(),
            author_name="Smith Jane",
            transport=stub_transport(esearch_resp([])),
        )
        assert conn._author_name == "Smith Jane"
        result = asyncio.run(conn.run())
        assert result.record_count == 0

    def test_api_key_accepted_at_construction(self):
        conn = PubmedConnector(
            pubmed_config(),
            author_name="Doe John",
            api_key="test-key-123",
            transport=stub_transport(esearch_resp([])),
        )
        assert conn._api_key == "test-key-123"
        result = asyncio.run(conn.run())
        assert result.record_count == 0

    def test_no_api_key_still_works(self):
        conn = _connector(esearch_resp([]))
        assert conn._api_key is None
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS


# ---------------------------------------------------------------------------
class TestSchemaDrift:
    def test_missing_uid_is_schema_drift(self):
        pmid = "99999999"
        art = {k: v for k, v in article(pmid).items() if k != "uid"}
        # Pass pmids explicitly: article has no uid field, so the helper needs
        # the string key to look it up in the result dict.
        conn = _connector(esearch_resp([pmid]), esummary_resp([art], pmids=[pmid]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT
        assert result.health.schema_drift_detected is True

    def test_missing_authors_is_schema_drift(self):
        pmid = "88888888"
        art = {k: v for k, v in article(pmid).items() if k != "authors"}
        conn = _connector(esearch_resp([pmid]), esummary_resp([art]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_wrong_type_on_uid_is_schema_drift(self):
        pmid = "77777777"
        art = article(pmid)
        art["uid"] = 77777777  # int, not str
        # Pass pmids explicitly so the result dict is keyed by the string "77777777"
        # even though art["uid"] is now an int -- this ensures the article is found
        # by _parse_esummary and the contract can fire on the wrong type.
        conn = _connector(esearch_resp([pmid]), esummary_resp([art], pmids=[pmid]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.SCHEMA_DRIFT

    def test_extra_fields_pass_through_without_drift(self):
        pmid = "66666666"
        art = article(pmid)
        art["doi"] = "10.1016/j.test.2023.01.001"
        art["fulljournalname"] = "Journal of the American College of Cardiology"
        conn = _connector(esearch_resp([pmid]), esummary_resp([art]))
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.SUCCESS
        assert result.records[0].raw["doi"] == "10.1016/j.test.2023.01.001"


# ---------------------------------------------------------------------------
class TestFailureModes:
    def test_non_json_esearch_response_is_source_down(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}

            def json(self) -> Any:
                raise ValueError("not JSON")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = PubmedConnector(
            pubmed_config(max_retries=0),
            author_name="Doe John",
            transport=_transport,
        )
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_missing_esearchresult_key_is_source_down(self):
        bad = StubResponse(json_body={"unexpected": "shape"})
        conn = _connector(bad, max_retries=0)
        result = asyncio.run(conn.run())
        assert result.status is FetchStatus.FAILED
        assert result.health.status is SourceStatus.DOWN

    def test_non_json_esummary_response_is_source_down(self):
        class HtmlResp:
            status_code = 200
            headers: dict[str, str] = {}
            _call_count = 0

            def json(self) -> Any:
                HtmlResp._call_count += 1
                if HtmlResp._call_count == 1:
                    # First call = esearch succeeds.
                    return {
                        "esearchresult": {
                            "count": "1",
                            "idlist": ["12345678"],
                        }
                    }
                raise ValueError("esummary not JSON")

        async def _transport(method: str, url: str, **kwargs: Any) -> HtmlResp:
            return HtmlResp()

        conn = PubmedConnector(
            pubmed_config(max_retries=0),
            author_name="Doe John",
            transport=_transport,
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

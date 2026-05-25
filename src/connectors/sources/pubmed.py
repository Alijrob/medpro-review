"""
pubmed.py -- PubMed / NCBI Entrez API adapter (source A1, component C10, Phase 2-B.8).

PubMed (A1) adds a research-activity signal to provider profiles: publication count,
affiliated institution, co-authorship patterns, and clinical trial authorship. A provider
with significant PubMed presence is likely an academic or research-active physician --
useful context for report consumers choosing between providers.

Integration: NIH NCBI Entrez API (free, public domain). Two-step fetch per batch:
  1. **esearch** -- search PubMed for articles by author name, returns a page of PMIDs.
  2. **esummary** -- batch-fetch article metadata for those PMIDs.

Both steps use the same ``base_url`` (``https://eutils.ncbi.nlm.nih.gov``) and both
pass through the C9 ``request()`` helper for throttling + retry.

Rate limit:
  Without an API key: 3 requests/second. With an API key (free, register at
  https://www.ncbi.nlm.nih.gov/account/): 10 requests/second. The default
  ``rate_limit_per_sec`` is set to 3; override with an ``api_key`` + a higher
  ``rate_limit_per_sec`` in production.

Author name disambiguation:
  PubMed is searched by author name (``{name}[Author]``), not by NPI. Name
  disambiguation (which publications actually belong to the target provider vs. a
  namesake) is a C11 normalization concern, not the adapter's. The adapter yields all
  articles matching the search term. C11 uses affiliation, co-author overlap, specialty,
  and institution to filter.

Schema contract:
  Guards 4 fields on each esummary article: ``uid`` (PMID string), ``title`` (str),
  ``pubdate`` (str), ``authors`` (list). These are present on every NCBI esummary
  response for PubMed articles. Extra fields (``source``, ``volume``, ``pages``,
  ``fulljournalname``, etc.) pass through without SCHEMA_DRIFT.

Output is ``RawRecord``s (pre-normalization). Aggregating publication counts and
deriving the research-activity signal is C11 (Phase 2-D).

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing
here hits the network on import; tests drive it with stubbed transports. A1 is
public domain (NIH/NLM), T1/L0 (source-priority.md).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ..base import SourceConnector
from ..config import ConnectorConfig
from ..contract import SchemaContract
from ..errors import SourceUnavailableError
from ..models import IntegrationMethod

DEFAULT_BASE_URL = "https://eutils.ncbi.nlm.nih.gov"
ESEARCH_PATH = "/entrez/eutils/esearch.fcgi"
ESUMMARY_PATH = "/entrez/eutils/esummary.fcgi"

# Number of PMIDs fetched per esearch page (and per esummary batch).
# NCBI recommends <= 500 per esummary call. 200 is conservative.
DEFAULT_RETMAX = 200


def pubmed_config(**overrides: Any) -> ConnectorConfig:
    """Build the A1 ConnectorConfig (identity + operational defaults).

    Rate limit defaults to 3 req/s (unauthenticated NCBI limit). If an
    ``api_key`` is provided to the connector, you can safely override to
    ``rate_limit_per_sec=9.0`` (leaving 10% headroom below the 10/s limit).

    ``expected_min_records`` is ``None`` by default -- publication counts vary
    widely by provider. Set a floor in production only if a specific batch
    pipeline requires it (unusual for a per-provider on-demand lookup).
    """
    params: dict[str, Any] = dict(
        source_id="A1",
        source_name="PubMed / NCBI Entrez",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (PubMed A1; mailto:support@researchyourdoctor.com)",
        # Unauthenticated NCBI rate limit is 3 req/s.
        # Two requests are made per batch (esearch + esummary); the throttle
        # applies per-request so the effective throughput is ~1.5 batches/s.
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class PubmedConnector(SourceConnector):
    """PubMed / NCBI Entrez API adapter (A1).

    Fetches all PubMed articles matching ``author_name[Author]`` via a two-step
    NCBI Entrez API call (esearch -> esummary), paginated by ``retmax``.

    Per batch:
      1. esearch: ``GET /entrez/eutils/esearch.fcgi?db=pubmed&term={name}[Author]&...``
         Returns a JSON list of PMIDs (up to ``retmax`` per page).
      2. esummary: ``GET /entrez/eutils/esummary.fcgi?db=pubmed&id={pmid,...}&...``
         Returns a JSON dict of ``{pmid: article_summary}``.

    Pagination continues until an esearch page returns fewer PMIDs than ``retmax``
    (the NCBI short-page sentinel). The ``retstart`` cursor advances by ``retmax``
    each iteration.

    Author name disambiguation is a C11 concern, not the adapter's. All articles
    matching the search term are yielded.

    If an API key is provided, pass it at construction time (not in ``ConnectorConfig``
    -- secrets are never in the framework config). The key is included as a ``api_key``
    query parameter on all Entrez requests.
    """

    # Guards the 4 fields present on every NCBI esummary article.
    # Extra fields (source, volume, doi, etc.) pass through without drift alerts.
    contract = SchemaContract(
        required_fields=frozenset({"uid", "title", "pubdate", "authors"}),
        field_types={
            "uid": str,
            "title": str,
            "pubdate": str,
            "authors": list,
        },
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        author_name: str,
        api_key: str | None = None,
        retmax: int = DEFAULT_RETMAX,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._author_name = author_name
        self._api_key = api_key
        self._retmax = retmax

    def _entrez_params(self, extra: dict[str, Any]) -> dict[str, Any]:
        """Base Entrez parameters (api_key injected if provided)."""
        params = dict(extra)
        if self._api_key:
            params["api_key"] = self._api_key
        return params

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Yield one esummary article dict per PubMed publication.

        Paginates through esearch (retstart/retmax), then batch-fetches
        esummary for each page of PMIDs. Stops when esearch returns a
        short page (fewer PMIDs than retmax) -- the NCBI pagination sentinel.

        Both esearch and esummary requests pass through the C9 ``request()``
        helper (throttle, retry, HTTP->error classification).
        """
        retstart = 0
        while True:
            # Step 1: esearch -- get the next page of PMIDs.
            search_resp = await self.request(
                "GET",
                ESEARCH_PATH,
                params=self._entrez_params({
                    "db": "pubmed",
                    "term": f"{self._author_name}[Author]",
                    "retstart": retstart,
                    "retmax": self._retmax,
                    "retmode": "json",
                }),
            )
            pmids = self._parse_esearch(search_resp)
            if not pmids:
                break  # No results (or exhausted).

            # Step 2: esummary -- batch-fetch article metadata for this page.
            summary_resp = await self.request(
                "GET",
                ESUMMARY_PATH,
                params=self._entrez_params({
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "json",
                }),
            )
            articles = self._parse_esummary(summary_resp, pmids)
            for article in articles:
                yield article

            # Short page: esearch is exhausted -- stop pagination.
            if len(pmids) < self._retmax:
                break
            retstart += self._retmax

    def _parse_esearch(self, resp: Any) -> list[str]:
        """Extract the PMID list from an esearch JSON response.

        NCBI esearch JSON structure:
            {"esearchresult": {"idlist": ["12345678", ...], "count": "42", ...}}
        """
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON esearch response from NCBI: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected esearch shape ({type(body).__name__})"
            )
        result = body.get("esearchresult")
        if not isinstance(result, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: missing esearchresult in esearch response"
            )
        ids = result.get("idlist", [])
        if not isinstance(ids, list):
            raise SourceUnavailableError(
                f"{self.source_id}: esearchresult.idlist is not a list"
            )
        return [str(i) for i in ids]

    def _parse_esummary(self, resp: Any, expected_ids: list[str]) -> list[dict[str, Any]]:
        """Extract article dicts from an esummary JSON response.

        NCBI esummary JSON structure:
            {
              "result": {
                "uids": ["12345678", "23456789"],
                "12345678": {"uid": "12345678", "title": "...", ...},
                "23456789": {...}
              }
            }

        Articles are returned in the ``expected_ids`` order for determinism.
        """
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON esummary response from NCBI: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected esummary shape ({type(body).__name__})"
            )
        result = body.get("result")
        if not isinstance(result, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: missing result in esummary response"
            )
        # Return articles in the order of expected_ids; silently skip missing IDs
        # (rare but possible if NCBI returns a partial result for a requested set).
        articles = []
        for pmid in expected_ids:
            article = result.get(pmid)
            if isinstance(article, dict):
                articles.append(article)
        return articles

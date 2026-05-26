"""
client.py -- Thin httpx wrapper over the OpenSearch REST API (C14).

Uses httpx (already in pyproject.toml) rather than opensearch-py to avoid
adding a new dependency. The surface area is intentionally small -- just the
four operations Phase 2-G requires:

  index_doc(index, doc_id, body)  ->  IndexRawResponse
  bulk_index(index, docs)         ->  BulkRawResponse
  search(index, body)             ->  SearchRawResponse
  get_doc(index, doc_id)          ->  GetRawResponse

All methods are synchronous. Async is deferred until Phase 2-H Temporal
integration requires it.

Local dev credentials (docker-compose.dev.yml):
  username: admin
  password: DevOpenSearch1!   (set SEARCH_OPENSEARCH_PASSWORD in .env)

Authentication: HTTP basic auth if both username and password are set.
If password is blank (default), no auth header is sent (suitable for
single-node local dev with security disabled, which is NOT the
docker-compose setup -- see OPENSEARCH_INITIAL_ADMIN_PASSWORD in
docker-compose.dev.yml).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx

from .config import SearchSettings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw response containers (dataclasses, not Pydantic -- thin pass-through)
# ---------------------------------------------------------------------------


@dataclass
class IndexRawResponse:
    """Raw result from PUT /{index}/_doc/{id}."""

    npi: str
    success: bool
    index: str
    result: str = ""  # "created" | "updated" | "noop" | ""
    error: str | None = None


@dataclass
class BulkRawResponse:
    """Raw result from POST /_bulk."""

    took: int
    errors: bool
    items: list[dict] = field(default_factory=list)


@dataclass
class SearchRawResponse:
    """Raw result from POST /{index}/_search."""

    total: int
    hits: list[dict]  # each dict has _score merged into the _source fields
    took_ms: int


@dataclass
class GetRawResponse:
    """Raw result from GET /{index}/_doc/{id}."""

    found: bool
    source: dict | None  # _source dict, or None when not found


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class OpenSearchClient:
    """
    Thin httpx-based client for the OpenSearch REST API.

    Thread-safe -- httpx.Client reuses the underlying connection pool.
    Instantiate once per service startup (wired in the app factory).

    All methods catch exceptions and return a typed error response rather
    than propagating -- callers check `.success` / `.errors` / `.found`.
    """

    def __init__(self, settings: SearchSettings) -> None:
        auth: httpx.BasicAuth | None = None
        if settings.has_auth:
            auth = httpx.BasicAuth(settings.opensearch_username, settings.opensearch_password)
        self._base_url = settings.opensearch_url.rstrip("/")
        self._timeout = settings.opensearch_timeout_s
        self._http = httpx.Client(
            auth=auth,
            timeout=self._timeout,
            headers={"Content-Type": "application/json"},
        )

    # ------------------------------------------------------------------
    # Index single document
    # ------------------------------------------------------------------

    def index_doc(self, index: str, doc_id: str, body: dict) -> IndexRawResponse:
        """
        Index (or update) a single document using PUT /{index}/_doc/{id}.

        Uses PUT so the document ID is always the NPI. Returns
        IndexRawResponse(success=False, error=...) on any exception.
        """
        url = f"{self._base_url}/{index}/_doc/{doc_id}"
        try:
            resp = self._http.put(url, content=json.dumps(body))
            resp.raise_for_status()
            data = resp.json()
            return IndexRawResponse(
                npi=doc_id,
                success=True,
                index=index,
                result=data.get("result", ""),
            )
        except Exception as exc:
            logger.warning("index_doc failed npi=%s: %s", doc_id, exc)
            return IndexRawResponse(
                npi=doc_id, success=False, index=index, result="error", error=str(exc)
            )

    # ------------------------------------------------------------------
    # Bulk index
    # ------------------------------------------------------------------

    def bulk_index(self, index: str, docs: list[tuple[str, dict]]) -> BulkRawResponse:
        """
        Bulk-index documents using POST /_bulk with index actions.

        docs: list of (doc_id, body) tuples. Doc ID = NPI.
        Returns BulkRawResponse(errors=True, items=[]) on exception.
        """
        if not docs:
            return BulkRawResponse(took=0, errors=False, items=[])

        lines: list[str] = []
        for doc_id, body in docs:
            action = json.dumps({"index": {"_index": index, "_id": doc_id}})
            lines.append(action)
            lines.append(json.dumps(body))
        ndjson = "\n".join(lines) + "\n"

        url = f"{self._base_url}/_bulk"
        try:
            resp = self._http.post(
                url,
                content=ndjson.encode(),
                headers={"Content-Type": "application/x-ndjson"},
            )
            resp.raise_for_status()
            data = resp.json()
            return BulkRawResponse(
                took=data.get("took", 0),
                errors=data.get("errors", False),
                items=data.get("items", []),
            )
        except Exception as exc:
            logger.error("bulk_index failed: %s", exc)
            return BulkRawResponse(took=0, errors=True, items=[])

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, index: str, body: dict) -> SearchRawResponse:
        """
        Execute a search query via POST /{index}/_search.

        Returns SearchRawResponse with total=0, hits=[] on exception.
        Each hit dict has _score merged into the _source fields for
        convenience (routes.py does not need to unwrap nested keys).
        """
        url = f"{self._base_url}/{index}/_search"
        try:
            resp = self._http.post(url, content=json.dumps(body))
            resp.raise_for_status()
            data = resp.json()

            total_node = data.get("hits", {}).get("total", {})
            total = (
                total_node.get("value", 0)
                if isinstance(total_node, dict)
                else int(total_node)
            )

            raw_hits = data.get("hits", {}).get("hits", [])
            hits = [
                {"_score": h.get("_score", 0.0), **h.get("_source", {})}
                for h in raw_hits
            ]
            return SearchRawResponse(
                total=total, hits=hits, took_ms=data.get("took", 0)
            )
        except Exception as exc:
            logger.error("search failed index=%s: %s", index, exc)
            return SearchRawResponse(total=0, hits=[], took_ms=0)

    # ------------------------------------------------------------------
    # Get single document
    # ------------------------------------------------------------------

    def get_doc(self, index: str, doc_id: str) -> GetRawResponse:
        """
        Fetch a single document by ID via GET /{index}/_doc/{id}.

        Returns GetRawResponse(found=False, source=None) on 404 or exception.
        """
        url = f"{self._base_url}/{index}/_doc/{doc_id}"
        try:
            resp = self._http.get(url)
            if resp.status_code == 404:
                return GetRawResponse(found=False, source=None)
            resp.raise_for_status()
            data = resp.json()
            return GetRawResponse(
                found=data.get("found", False),
                source=data.get("_source"),
            )
        except Exception as exc:
            logger.warning("get_doc failed id=%s: %s", doc_id, exc)
            return GetRawResponse(found=False, source=None)

    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying httpx client. Called on service shutdown."""
        self._http.close()

"""
routes.py -- Provider Search Service API routes (C14, Phase 2-G).

Endpoints:
  GET  /healthz                       Service liveness probe
  GET  /readyz                        Readiness probe (cluster health check)
  GET  /v1/providers/search           Multi-field name/specialty search
  GET  /v1/providers/{npi}            NPI exact lookup (direct get_doc)
  POST /v1/providers/{npi}/index      Index (or re-index) a CanonicalProviderProfile

Design:
  - GET /v1/providers/{npi} uses client.get_doc() -- O(1) fetch by document ID.
  - GET /v1/providers/search uses client.search() with build_search_query().
  - POST /v1/providers/{npi}/index accepts a full CanonicalProviderProfile body;
    path NPI must match profile.npi (422 if not).
  - All OpenSearch errors are caught by the client layer and returned as typed
    error responses; routes translate them to 404/502 as appropriate.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from schema.v1.profile import CanonicalProviderProfile
from search.client import OpenSearchClient
from search.config import SearchSettings
from search.indexer import ProviderIndexer
from search.models import (
    IndexResult,
    ProviderSearchHit,
    SearchResponse,
)
from search.query import build_search_query

router = APIRouter()

# ---------------------------------------------------------------------------
# Singletons (set by app factory via _set_singletons)
# ---------------------------------------------------------------------------

_client: OpenSearchClient | None = None
_indexer: ProviderIndexer | None = None
_settings: SearchSettings | None = None


def _set_singletons(
    client: OpenSearchClient,
    indexer: ProviderIndexer,
    settings: SearchSettings,
) -> None:
    """Called by app.py to wire the singletons before first request."""
    global _client, _indexer, _settings
    _client = client
    _indexer = indexer
    _settings = settings


def _get_client() -> OpenSearchClient:
    assert _client is not None, "OpenSearchClient not initialised"
    return _client


def _get_indexer() -> ProviderIndexer:
    assert _indexer is not None, "ProviderIndexer not initialised"
    return _indexer


def _get_settings() -> SearchSettings:
    assert _settings is not None, "SearchSettings not initialised"
    return _settings


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------


@router.get("/healthz", tags=["probes"])
def healthz() -> dict:
    """Liveness probe. Always 200 when the process is alive."""
    return {"status": "ok", "service": "search-service"}


@router.get("/readyz", tags=["probes"])
def readyz() -> dict:
    """
    Readiness probe.

    Returns 200 {"status": "ok"} when OpenSearch cluster health is reachable.
    Returns 200 {"status": "not_configured"} when the cluster URL is not yet
    wired (shell mode -- DECISIONS.md Entry 003).
    Returns 503 when the cluster is unreachable.
    """
    settings = _get_settings()
    if not settings.is_configured:
        return {"status": "not_configured", "detail": "SEARCH_OPENSEARCH_URL not wired (Entry 003)"}

    client = _get_client()
    try:
        resp = client._http.get(f"{client._base_url}/_cluster/health", timeout=2.0)
        if resp.is_success:
            return {"status": "ok"}
        return {"status": "degraded", "detail": f"cluster health {resp.status_code}"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OpenSearch unreachable: {exc}",
        )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@router.get("/v1/providers/search", response_model=SearchResponse, tags=["providers"])
def search_providers(
    q: str | None = Query(
        default=None, description="Free-text query (name, specialty, city)."
    ),
    state: str | None = Query(
        default=None, description="2-letter state code filter (e.g. CA)."
    ),
    specialty_code: str | None = Query(
        default=None, description="NUCC taxonomy code filter (e.g. 207Q00000X)."
    ),
    entity_type: str | None = Query(
        default=None, description="individual | organization"
    ),
    has_exclusion: bool | None = Query(
        default=None, description="True = only excluded providers."
    ),
    has_active_license: bool | None = Query(
        default=None, description="True = only providers with an active license."
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> SearchResponse:
    """Search providers by name, specialty, state, or risk flags."""
    settings = _get_settings()
    client = _get_client()

    query_body = build_search_query(
        q=q,
        state=state,
        specialty_code=specialty_code,
        entity_type=entity_type,
        has_exclusion=has_exclusion,
        has_active_license=has_active_license,
        from_offset=(page - 1) * page_size,
        page_size=page_size,
    )

    raw = client.search(index=settings.index_name, body=query_body)

    results = [
        ProviderSearchHit(
            npi=h.get("primary_npi", ""),
            entity_type=h.get("entity_type", ""),
            primary_name=h.get("primary_name", {}),
            primary_specialty=h.get("primary_specialty"),
            known_states=h.get("known_states", []),
            has_active_exclusion=h.get("has_active_exclusion", False),
            has_active_license=h.get("has_active_license", False),
            identity_confidence=h.get("identity_confidence", 0.0),
            score=h.get("_score", 0.0),
        )
        for h in raw.hits
    ]

    return SearchResponse(total=raw.total, page=page, page_size=page_size, results=results)


# ---------------------------------------------------------------------------
# NPI lookup
# ---------------------------------------------------------------------------


@router.get("/v1/providers/{npi}", response_model=ProviderSearchHit, tags=["providers"])
def get_provider(npi: str) -> ProviderSearchHit:
    """
    Fetch a single provider by NPI. Uses direct document get_doc (O(1)).

    Returns 404 when the provider has not yet been indexed.
    Returns 422 when the NPI format is invalid (must be exactly 10 digits).
    """
    if not npi.isdigit() or len(npi) != 10:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid NPI '{npi}': must be exactly 10 digits.",
        )

    settings = _get_settings()
    client = _get_client()

    resp = client.get_doc(index=settings.index_name, doc_id=npi)

    if not resp.found or resp.source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider NPI {npi} not found in index.",
        )

    src = resp.source
    return ProviderSearchHit(
        npi=src.get("primary_npi", npi),
        entity_type=src.get("entity_type", ""),
        primary_name=src.get("primary_name", {}),
        primary_specialty=src.get("primary_specialty"),
        known_states=src.get("known_states", []),
        has_active_exclusion=src.get("has_active_exclusion", False),
        has_active_license=src.get("has_active_license", False),
        identity_confidence=src.get("identity_confidence", 0.0),
        score=0.0,
    )


# ---------------------------------------------------------------------------
# Indexing endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/v1/providers/{npi}/index",
    response_model=IndexResult,
    status_code=status.HTTP_201_CREATED,
    tags=["indexing"],
)
def index_provider(npi: str, profile: CanonicalProviderProfile) -> IndexResult:
    """
    Index (or re-index) a single provider profile.

    Accepts a full CanonicalProviderProfile JSON body. The path NPI must
    match profile.npi -- returns 422 when they disagree. Used by the
    ingestion pipeline and CLI tooling; Phase 2-H Temporal workflow calls
    this internally.

    Returns 502 when OpenSearch is unreachable or rejects the document.
    """
    if profile.npi != npi:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Path NPI '{npi}' does not match profile NPI '{profile.npi}'.",
        )

    indexer = _get_indexer()
    client = _get_client()
    result = indexer.index_profile(profile, client)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenSearch indexing failed: {result.error}",
        )
    return result

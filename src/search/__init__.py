"""
search -- Provider Search Service library (C14, Phase 2-G).

Provides the indexer, document builder, query DSL builders, and OpenSearch
client for the provider search feature. Consumed by:
  - src/backend/search_service/ (FastAPI shell, Phase 2-G)
  - Phase 2-H Temporal workflow activities (indexing after each merge cycle)
  - Phase 2-K frontend API (search/lookup endpoints)

Public API
----------
SearchSettings / get_settings   env-driven config (SEARCH_ prefix)
ProviderDoc                     OpenSearch document shape (mirrors index template)
SearchFilters                   Structured filter params
SearchRequest / SearchResponse  API request/response envelopes
ProviderSearchHit               Single search result
IndexResult / BatchIndexResult  Indexing operation results
build_provider_doc              CanonicalProviderProfile -> ProviderDoc (pure)
build_npi_query                 NPI exact-match query DSL (pure)
build_search_query              Multi-field search query DSL (pure)
ProviderIndexer                 index_profile() / index_batch() coordinator
OpenSearchClient                Thin httpx wrapper over OpenSearch REST API
"""
from .client import GetRawResponse, OpenSearchClient
from .config import SearchSettings, get_settings
from .document import build_provider_doc
from .indexer import ProviderIndexer
from .models import (
    BatchIndexResult,
    IndexResult,
    ProviderDoc,
    ProviderSearchHit,
    SearchFilters,
    SearchRequest,
    SearchResponse,
)
from .query import build_npi_query, build_search_query

__all__ = [
    # config
    "SearchSettings",
    "get_settings",
    # document builder
    "build_provider_doc",
    # query builders
    "build_npi_query",
    "build_search_query",
    # indexer
    "ProviderIndexer",
    # client
    "OpenSearchClient",
    "GetRawResponse",
    # models
    "BatchIndexResult",
    "IndexResult",
    "ProviderDoc",
    "ProviderSearchHit",
    "SearchFilters",
    "SearchRequest",
    "SearchResponse",
]

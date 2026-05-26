"""
models.py -- Request/response and document models for the Provider Search Service (C14).

ProviderDoc is the document shape written to and read from the OpenSearch
providers-{env} index. Its field names mirror the mapping in
src/data/opensearch/providers_index_template.json exactly.

SearchRequest / SearchResponse / ProviderSearchHit are the FastAPI API shapes.
IndexResult / BatchIndexResult are the indexing-operation result types returned
by ProviderIndexer.
"""
from __future__ import annotations

from pydantic import Field

from schema.v1.common import MedproBaseModel, utc_now


# ---------------------------------------------------------------------------
# OpenSearch document shape
# ---------------------------------------------------------------------------


class ProviderDoc(MedproBaseModel):
    """
    OpenSearch document for a single provider. Mirrors the field mapping in
    src/data/opensearch/providers_index_template.json.

    Document _id in the index = primary_npi.
    Built by document.build_provider_doc() from a CanonicalProviderProfile.

    Fields left out of the index template (e.g. exclusion details, publication
    titles) are stored in Aurora and fetched at report-generation time (C17).
    The index intentionally holds only search-facet and ranking signals.
    """

    primary_npi: str
    entity_type: str  # "individual" | "organization"

    # name fields -- keys mirror the OpenSearch mapping object properties
    primary_name: dict[str, str | None]
    name_variants: list[str] = Field(default_factory=list)

    # specialty
    primary_specialty: dict[str, str] | None = None
    all_taxonomy_descriptions: str = ""

    # address facets
    known_states: list[str] = Field(default_factory=list)
    known_cities: list[str] = Field(default_factory=list)
    practice_zip_codes: list[str] = Field(default_factory=list)

    # identity
    gender: str = "unknown"
    identity_confidence: float = 0.0

    # risk flags
    has_active_license: bool = False
    has_active_exclusion: bool = False
    has_active_discipline: bool = False
    overall_risk_score: float = 0.0

    # coverage / freshness
    source_coverage_count: int = 0
    report_count: int = 0

    profile_last_rebuilt_at: str  # ISO-8601 UTC
    last_indexed_at: str = Field(
        default_factory=lambda: utc_now().isoformat(),
        description="Set to UTC now by build_provider_doc().",
    )


# ---------------------------------------------------------------------------
# Search API shapes
# ---------------------------------------------------------------------------


class SearchFilters(MedproBaseModel):
    """Optional structured filters applied as OpenSearch filter clauses."""

    state: str | None = None
    specialty_code: str | None = None
    entity_type: str | None = None  # "individual" | "organization"
    has_exclusion: bool | None = None
    has_active_license: bool | None = None


class SearchRequest(MedproBaseModel):
    """
    Request body for POST /v1/providers/search (alternative to query params).
    GET /v1/providers/search uses individual query params instead.
    """

    q: str | None = Field(default=None, description="Free-text query (name, specialty, city).")
    filters: SearchFilters = Field(default_factory=SearchFilters)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)

    @property
    def from_offset(self) -> int:
        return (self.page - 1) * self.page_size


class ProviderSearchHit(MedproBaseModel):
    """A single provider result returned by search or NPI lookup endpoints."""

    npi: str
    entity_type: str
    primary_name: dict[str, str | None]
    primary_specialty: dict[str, str] | None = None
    known_states: list[str] = Field(default_factory=list)
    has_active_exclusion: bool = False
    has_active_license: bool = False
    identity_confidence: float = 0.0
    score: float = Field(default=0.0, description="OpenSearch relevance score (_score).")


class SearchResponse(MedproBaseModel):
    """Response envelope for GET /v1/providers/search."""

    total: int
    page: int
    page_size: int
    results: list[ProviderSearchHit]


# ---------------------------------------------------------------------------
# Indexing operation results
# ---------------------------------------------------------------------------


class IndexResult(MedproBaseModel):
    """Result of indexing a single provider document into OpenSearch."""

    npi: str
    success: bool
    index_name: str
    result: str = ""  # OpenSearch "result" field: "created" | "updated" | "noop" | "error"
    error: str | None = None


class BatchIndexResult(MedproBaseModel):
    """Aggregate result of bulk-indexing a list of CanonicalProviderProfiles."""

    total: int
    succeeded: int
    failed: int
    failures: list[IndexResult] = Field(default_factory=list)

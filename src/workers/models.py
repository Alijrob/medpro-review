"""
models.py -- Temporal activity input/output models (C15 basic).

All models are Pydantic BaseModel subclasses. Temporal serialises them as
JSON payloads between the workflow and activity workers.

Design rule: every model must be fully JSON-round-trippable. No UUID, datetime,
or date fields from schema.v1 appear directly -- they are converted to str
by the activity functions before returning.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# fetch_source_activity
# ---------------------------------------------------------------------------


class FetchSourceInput(BaseModel):
    npi: str
    source_id: str


class FetchSourceOutput(BaseModel):
    source_id: str
    raw_records: list[dict[str, Any]] = Field(default_factory=list)
    fetch_status: str  # "success" | "partial" | "failed"
    error_message: str | None = None
    records_count: int = 0


# ---------------------------------------------------------------------------
# normalize_records_activity
# ---------------------------------------------------------------------------


class NormalizeRecordsInput(BaseModel):
    raw_records: list[dict[str, Any]]  # serialised RawRecord dicts
    entity_npi: str


class NormalizeRecordsOutput(BaseModel):
    normalized_records: list[dict[str, Any]] = Field(default_factory=list)
    normalization_errors: list[str] = Field(default_factory=list)
    records_count: int = 0


# ---------------------------------------------------------------------------
# resolve_identity_activity
# ---------------------------------------------------------------------------


class ResolveIdentityInput(BaseModel):
    npi: str
    normalized_records: list[dict[str, Any]]


class ResolveIdentityOutput(BaseModel):
    bundle: dict[str, Any] | None = None  # serialised UnifiedIdBundle or None
    confidence: float = 0.0
    source_ids_contributing: list[str] = Field(default_factory=list)
    resolution_status: str  # "resolved" | "no_records" | "failed"


# ---------------------------------------------------------------------------
# link_and_merge_activity
# ---------------------------------------------------------------------------


class LinkAndMergeInput(BaseModel):
    bundle: dict[str, Any]
    normalized_records: list[dict[str, Any]]
    npi: str


class LinkAndMergeOutput(BaseModel):
    profile: dict[str, Any]  # serialised CanonicalProviderProfile
    record_type_counts: dict[str, int] = Field(default_factory=dict)
    completeness_score: float = 0.0


# ---------------------------------------------------------------------------
# index_profile_activity
# ---------------------------------------------------------------------------


class IndexProfileInput(BaseModel):
    profile: dict[str, Any]
    npi: str


class IndexProfileOutput(BaseModel):
    indexed: bool = False
    doc_id: str | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# generate_report_activity
# ---------------------------------------------------------------------------


class GenerateReportInput(BaseModel):
    profile: dict[str, Any]
    npi: str
    include_html: bool = True
    narrative: dict[str, Any] | None = None
    """Serialised NarrativeResult dict from generate_ai_narrative_activity (Phase 4-H)."""


class GenerateReportOutput(BaseModel):
    report: dict[str, Any]  # serialised ProviderReport
    html: str = ""
    report_id: str = ""


# ---------------------------------------------------------------------------
# persist_report_activity
# ---------------------------------------------------------------------------


class PersistReportInput(BaseModel):
    report_id: str  # UUID string -- the reports table primary key
    pipeline_result: dict[str, Any]  # serialised ProviderPipelineResult


class PersistReportOutput(BaseModel):
    persisted: bool = False
    error_message: str | None = None


# ---------------------------------------------------------------------------
# generate_ai_narrative_activity (Phase 4-H)
# ---------------------------------------------------------------------------


class GenerateNarrativeInput(BaseModel):
    profile: dict[str, Any]
    npi: str


class GenerateNarrativeOutput(BaseModel):
    narrative: dict[str, Any] | None = None
    """Serialised NarrativeResult, or None if narrative_enabled=False or fatal error."""

    fallback: bool = False
    """True when one or more AI providers were unavailable or returned empty."""

    error_message: str | None = None
    """Set when the activity itself failed (not provider-level failures)."""


# ---------------------------------------------------------------------------
# ProviderPipelineInput / ProviderPipelineResult (workflow level)
# ---------------------------------------------------------------------------


class ProviderPipelineInput(BaseModel):
    npi: str
    source_ids: list[str] = Field(
        default_factory=list,
        description="Which source IDs to attempt. Empty = use P1_SOURCE_IDS default.",
    )
    include_html: bool = True
    report_id: str | None = Field(
        default=None,
        description=(
            "Optional reports-table UUID. When set, ProviderPipelineWorkflow calls "
            "persist_report_activity as its final step to write the result to Aurora."
        ),
    )


class ProviderPipelineResult(BaseModel):
    npi: str
    report: dict[str, Any] | None = None
    html: str = ""
    report_id: str | None = None
    is_partial: bool = True
    pipeline_status: str  # "complete" | "partial" | "no_data" | "failed"
    sources_attempted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    error_message: str | None = None

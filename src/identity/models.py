"""
models.py -- Result and event types for the C12 Identity Resolution Engine.

These are internal operation types (not stored directly in Aurora -- the
UnifiedIdBundle is the persisted output). They carry enough context to build
audit events and drive downstream logic (C13 Entity Linking & Merge).
"""
from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import Field

from schema.v1.common import MedproBaseModel, NPI
from schema.v1.identity import UnifiedIdBundle


class ResolutionAction(str, Enum):
    """
    What the resolver did with the incoming NormalizedRecord.

    - CREATED: no bundle existed for this NPI; a new bundle was created.
    - MERGED:  an existing bundle was updated with the new source's contribution.
    - SKIPPED: the source was already in contributing_sources; no-op (idempotent).
    """

    CREATED = "created"
    MERGED = "merged"
    SKIPPED = "skipped"


class ResolutionResult(MedproBaseModel):
    """
    The outcome of resolving a single NormalizedRecord through the IdentityResolver.

    Returned by IdentityResolver.resolve() and collected in IdentityResolver.resolve_batch().
    Carries the current bundle state (post-resolution), the action taken, and source context.
    """

    bundle: UnifiedIdBundle = Field(
        ...,
        description="The UnifiedIdBundle after the resolution step (created, merged, or unchanged).",
    )
    action: ResolutionAction = Field(
        ...,
        description="Whether the resolver created a new bundle, merged into an existing one, or skipped.",
    )
    record_id: UUID = Field(
        ...,
        description="The record_id of the NormalizedRecord that triggered this resolution.",
    )
    source_id: str = Field(
        ...,
        max_length=20,
        description="Source identifier of the NormalizedRecord (e.g., 'F1', 'F2').",
    )
    provider_npi: NPI = Field(
        ...,
        description="The NPI this resolution resolved against.",
    )
    confidence_before: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Bundle identity_confidence before this merge (None if action=CREATED).",
    )
    confidence_after: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Bundle identity_confidence after this resolution step.",
    )


class BatchResolutionSummary(MedproBaseModel):
    """
    Aggregated summary returned by IdentityResolver.resolve_batch().

    Useful for logging and monitoring without iterating every individual ResolutionResult.
    """

    total_records: int = Field(default=0)
    created: int = Field(default=0, description="Number of new bundles created.")
    merged: int = Field(default=0, description="Number of existing bundles updated.")
    skipped: int = Field(default=0, description="Number of no-op re-submissions (idempotency).")
    bundles_requiring_review: int = Field(
        default=0,
        description="Number of bundles with human_review_required=True after the batch.",
    )
    unique_npis: int = Field(default=0, description="Number of distinct NPIs in the batch.")
    results: list[ResolutionResult] = Field(default_factory=list)

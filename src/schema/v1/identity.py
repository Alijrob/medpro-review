"""
identity.py — Identity resolution models: UnifiedIdBundle and ProviderIdentity.

These are the output of C12 (Identity Resolution Engine). A UnifiedIdBundle
anchors all NormalizedRecords for a single real-world provider. The primary
key throughout the system is the NPI.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from .common import (
    NPI,
    Address,
    ConfidenceScore,
    EntityType,
    Gender,
    ImmutableRecord,
    MedproBaseModel,
    ProviderName,
    TaxonomyCode,
    new_uuid,
    utc_now,
)


class OtherIdentifier(ImmutableRecord):
    """A provider identifier from a non-NPI system."""

    identifier_type: str = Field(
        ...,
        max_length=50,
        description="Type of identifier (e.g., 'DEA', 'state_license', 'UPIN', 'medicaid').",
        examples=["DEA", "state_license", "UPIN"],
    )
    identifier_value: str = Field(..., max_length=100)
    state: str | None = Field(default=None, max_length=2, description="Issuing state, if applicable.")
    issuer: str | None = Field(default=None, max_length=100, description="Issuing organization.")


class ProviderIdentity(ImmutableRecord):
    """
    Core identity fields for a single provider as reported by ONE source (typically NPPES).

    This is NOT the merged canonical identity — it is the raw identity assertion from a
    specific source. Multiple ProviderIdentity records may exist for one provider (one per
    source that reports identity fields). The UnifiedIdBundle is the merged output.
    """

    npi: NPI
    entity_type: EntityType
    name: ProviderName
    gender: Gender = Field(default=Gender.UNKNOWN)
    enumeration_date: datetime | None = Field(
        default=None,
        description="Date the NPI was assigned by CMS.",
    )
    last_updated: datetime | None = Field(
        default=None,
        description="Date the NPI record was last updated in NPPES.",
    )
    deactivation_date: datetime | None = Field(
        default=None,
        description="Date the NPI was deactivated, if applicable.",
    )
    reactivation_date: datetime | None = Field(
        default=None,
        description="Date the NPI was reactivated after deactivation, if applicable.",
    )
    sole_proprietor: bool | None = Field(
        default=None,
        description="True if the provider is a sole proprietor (NPPES field).",
    )
    organization_name: str | None = Field(
        default=None,
        max_length=300,
        description="For entity_type=ORGANIZATION: the legal organization name.",
    )
    other_names: list[ProviderName] = Field(
        default_factory=list,
        description="Alternate names reported by the source (e.g., former name, DBA).",
    )
    taxonomy_codes: list[TaxonomyCode] = Field(
        default_factory=list,
        description="NUCC taxonomy codes from NPPES. First element with primary=True is the primary specialty.",
    )
    addresses: list[Address] = Field(
        default_factory=list,
        description="All addresses reported for this provider (mailing and/or practice).",
    )
    other_identifiers: list[OtherIdentifier] = Field(
        default_factory=list,
        description="Non-NPI identifiers reported by the source.",
    )


class UnifiedIdBundle(MedproBaseModel):
    """
    The output of C12 (Identity Resolution Engine). Represents the system's
    best determination that all collected data for a given primary_npi belongs
    to a single real-world provider.

    One UnifiedIdBundle per NPI. Mutated in place as new sources are ingested
    and identity resolution runs. The `confidence` field tracks the system's
    certainty that all contributing records refer to the same individual.

    Supersedes individual ProviderIdentity records from each source.
    """

    bundle_id: UUID = Field(default_factory=new_uuid)
    primary_npi: NPI = Field(
        ...,
        description="The canonical NPI for this provider. All records are keyed on this.",
    )
    entity_type: EntityType

    # --- Best-confidence identity fields (merged from all sources) ---
    primary_name: ProviderName = Field(
        ...,
        description="Highest-confidence name for this provider (typically from NPPES).",
    )
    name_variants: list[ProviderName] = Field(
        default_factory=list,
        description="All other name forms seen across sources (for search and matching).",
    )
    gender: Gender = Field(default=Gender.UNKNOWN)
    primary_specialty: TaxonomyCode | None = Field(
        default=None,
        description="Primary NUCC taxonomy (from NPPES primary taxonomy code).",
    )
    all_taxonomies: list[TaxonomyCode] = Field(
        default_factory=list,
        description="All taxonomy codes seen across sources.",
    )
    known_addresses: list[Address] = Field(
        default_factory=list,
        description="All known practice and mailing addresses across sources.",
    )
    other_identifiers: list[OtherIdentifier] = Field(
        default_factory=list,
        description="Non-NPI identifiers accumulated from all sources.",
    )

    # --- Resolution metadata ---
    identity_confidence: ConfidenceScore = Field(
        ...,
        description=(
            "Confidence (0.0-1.0) that all contributing records refer to the same provider. "
            "Target: >0.98 per architecture acceptance criteria."
        ),
    )
    contributing_sources: list[str] = Field(
        default_factory=list,
        description="Source IDs (e.g., 'F1', 'F2', 'S5') that contributed to this bundle.",
    )
    human_review_required: bool = Field(
        default=False,
        description="True when identity_confidence < threshold and HitL review is needed.",
    )
    human_review_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Notes from HitL reviewer if human_review_required was True.",
    )

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_full_refresh_at: datetime | None = Field(
        default=None,
        description="Last time all source adapters were re-queried for this provider.",
    )

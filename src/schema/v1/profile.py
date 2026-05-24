"""
profile.py — CanonicalProviderProfile and its sub-models.

The CanonicalProviderProfile is the read model: the merged, provenance-tagged,
confidence-scored view of a single real-world provider built from all ingested
NormalizedRecords. It is what gets rendered into reports.

This model is updated by C13 (Entity Linking & Merge) after each source
ingestion cycle. It is NOT a source record — it is a derived view.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from .common import (
    NPI,
    Address,
    ConfidenceScore,
    EntityType,
    Gender,
    LicenseStatus,
    MedproBaseModel,
    ProviderName,
    SchemaVersion,
    SourceCategory,
    TaxonomyCode,
    VerificationStatus,
    new_uuid,
    utc_now,
)


# ---------------------------------------------------------------------------
# Sub-models embedded in CanonicalProviderProfile
# ---------------------------------------------------------------------------


class LicenseRecord(MedproBaseModel):
    """A single state medical license, as it appears in the canonical profile."""

    license_id: UUID = Field(default_factory=new_uuid)
    state: str = Field(..., max_length=2)
    board_name: str = Field(..., max_length=200)
    license_number: str = Field(..., max_length=50)
    license_type: str = Field(..., max_length=100, description="e.g., 'MD', 'DO', 'PA'.")
    status: LicenseStatus
    issue_date: date | None = None
    expiration_date: date | None = None
    last_renewed_date: date | None = None
    verification_status: VerificationStatus = Field(default=VerificationStatus.VERIFIED)
    source_id: str = Field(..., max_length=20, description="Source ID (e.g., 'S5' for CA Board).")
    source_url: str | None = Field(default=None, max_length=500)
    as_of_date: date | None = Field(
        default=None,
        description="Date this license status was last confirmed from the source.",
    )


class DisciplinaryAction(MedproBaseModel):
    """A disciplinary action against the provider from any state board."""

    action_id: UUID = Field(default_factory=new_uuid)
    state: str = Field(..., max_length=2)
    board_name: str = Field(..., max_length=200)
    action_type: str = Field(..., max_length=100)
    effective_date: date | None = None
    expiration_date: date | None = None
    is_active: bool
    basis: str | None = Field(default=None, max_length=1000)
    order_url: str | None = Field(default=None, max_length=500)
    case_number: str | None = Field(default=None, max_length=100)
    source_id: str = Field(..., max_length=20)
    verification_status: VerificationStatus = Field(default=VerificationStatus.VERIFIED)


class ExclusionRecord(MedproBaseModel):
    """An active or historical federal exclusion or debarment record."""

    exclusion_id: UUID = Field(default_factory=new_uuid)
    source_registry: str = Field(
        ...,
        max_length=50,
        description="Registry that issued the exclusion (e.g., 'OIG LEIE', 'SAM.gov').",
    )
    exclusion_type: str = Field(..., max_length=100)
    exclusion_date: date
    reinstatement_date: date | None = None
    is_active: bool = Field(
        ...,
        description="True if the exclusion is currently in effect.",
    )
    general_exclusion: bool | None = Field(
        default=None,
        description="For OIG LEIE: True = mandatory, False = permissive.",
    )
    description: str | None = Field(default=None, max_length=500)
    source_id: str = Field(..., max_length=20)


class CourtCaseSummary(MedproBaseModel):
    """
    A court case summary as rendered in the canonical profile.
    References the full CourtCaseRecord by record_id.
    """

    case_id: UUID = Field(default_factory=new_uuid)
    source_record_id: UUID = Field(..., description="FK to the NormalizedRecord.record_id.")
    court_type: str = Field(..., max_length=50)
    court_name: str = Field(..., max_length=200)
    case_number: str = Field(..., max_length=100)
    case_type: str = Field(..., max_length=100)
    filing_date: date | None = None
    disposition: str | None = Field(default=None, max_length=200)
    provider_party_role: str | None = Field(default=None, max_length=50)
    docket_url: str | None = Field(default=None, max_length=500)
    source_id: str = Field(..., max_length=20)
    verification_status: VerificationStatus = Field(default=VerificationStatus.VERIFIED)


class HospitalAffiliation(MedproBaseModel):
    """A hospital or health system affiliation."""

    affiliation_id: UUID = Field(default_factory=new_uuid)
    hospital_name: str = Field(..., max_length=300)
    hospital_pac_id: str | None = Field(default=None, max_length=20)
    hospital_ccn: str | None = Field(default=None, max_length=10)
    affiliation_type: str | None = Field(
        default=None,
        max_length=100,
        description="e.g., 'admitting privileges', 'employment', 'group practice'.",
    )
    effective_date: date | None = None
    source_id: str = Field(..., max_length=20)


class InsuranceParticipation(MedproBaseModel):
    """Medicare, Medicaid, or commercial insurance network participation record."""

    participation_id: UUID = Field(default_factory=new_uuid)
    program: str = Field(
        ...,
        max_length=100,
        description="Insurance program (e.g., 'Medicare', 'Medicaid-CA', 'NPPES-taxonomy-proxy').",
    )
    status: str = Field(
        ...,
        max_length=50,
        description="Participation status (e.g., 'participating', 'non-participating', 'opted_out').",
    )
    opted_out: bool = Field(default=False)
    opt_out_effective_date: date | None = None
    accepts_assignment: bool | None = None
    effective_date: date | None = None
    source_id: str = Field(..., max_length=20)
    as_of_date: date | None = None


class PublicationSummary(MedproBaseModel):
    """A published research paper attributed to this provider."""

    publication_id: UUID = Field(default_factory=new_uuid)
    pmid: str = Field(..., max_length=20)
    title: str = Field(..., max_length=1000)
    journal: str | None = Field(default=None, max_length=200)
    publication_year: int | None = None
    doi: str | None = Field(default=None, max_length=200)
    citation_count: int | None = Field(default=None, ge=0)
    author_position: str | None = Field(default=None, max_length=50)


class ReviewAggregate(MedproBaseModel):
    """Aggregated review signals from a single platform for this provider."""

    platform: str = Field(..., max_length=50)
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    review_count: int | None = Field(default=None, ge=0)
    platform_url: str | None = Field(default=None, max_length=500)
    as_of_date: datetime | None = None
    cache_expires_at: datetime | None = None


class SourceCoverage(MedproBaseModel):
    """Tracks which sources contributed to a section of the profile."""

    category: SourceCategory
    sources_attempted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    last_refreshed_at: datetime | None = None
    coverage_confidence: ConfidenceScore = Field(default=0.0)


class DerivedSignalSummary(MedproBaseModel):
    """A computed risk/confidence/anomaly signal for the provider."""

    signal_type: str = Field(
        ...,
        max_length=100,
        description=(
            "Type of derived signal (e.g., 'license_status_risk', 'exclusion_flag', "
            "'disciplinary_history_risk', 'identity_confidence', 'data_completeness')."
        ),
    )
    value: float = Field(..., description="Numeric signal value (interpretation depends on type).")
    confidence: ConfidenceScore
    explanation: str = Field(
        ...,
        max_length=500,
        description="Plain-English explanation of this signal, suitable for display in the report.",
    )
    contributing_sources: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# CanonicalProviderProfile — the master read model
# ---------------------------------------------------------------------------


class CanonicalProviderProfile(MedproBaseModel):
    """
    The merged, provenance-tagged, confidence-scored view of a single provider.

    Built by C13 (Entity Linking & Merge) from all NormalizedRecords for a
    given NPI. This is what the report generation service (C17) reads.

    Every list field is ordered by relevance/date descending (most recent first).
    Fields with `confidence` annotations reflect the system's certainty in that
    specific value.
    """

    # --- Primary key ---
    profile_id: UUID = Field(default_factory=new_uuid)
    npi: NPI = Field(..., description="Primary NPI — the system-wide unique key for this provider.")
    bundle_id: UUID = Field(..., description="FK to the UnifiedIdBundle for this provider.")

    # --- Identity ---
    entity_type: EntityType
    primary_name: ProviderName
    name_variants: list[ProviderName] = Field(default_factory=list)
    gender: Gender = Field(default=Gender.UNKNOWN)
    primary_specialty: TaxonomyCode | None = None
    all_specialties: list[TaxonomyCode] = Field(default_factory=list)
    practice_addresses: list[Address] = Field(default_factory=list)
    organization_name: str | None = Field(
        default=None,
        max_length=300,
        description="Set for entity_type=ORGANIZATION.",
    )

    # --- Education ---
    medical_school: str | None = Field(default=None, max_length=200)
    graduation_year: int | None = Field(default=None, ge=1900, le=2030)

    # --- Licensing ---
    licenses: list[LicenseRecord] = Field(
        default_factory=list,
        description="All state medical licenses, current and historical.",
    )
    active_license_count: int = Field(
        default=0,
        ge=0,
        description="Count of licenses with status=ACTIVE as of last refresh.",
    )
    license_states: list[str] = Field(
        default_factory=list,
        description="List of state codes where the provider holds any license.",
    )

    # --- Exclusions and Debarments ---
    exclusions: list[ExclusionRecord] = Field(
        default_factory=list,
        description="All OIG LEIE and SAM.gov exclusion records. Empty list = no exclusions found.",
    )
    currently_excluded: bool = Field(
        default=False,
        description="True if any exclusion is active as of last refresh. Critical red flag.",
    )

    # --- Disciplinary Actions ---
    disciplinary_actions: list[DisciplinaryAction] = Field(
        default_factory=list,
        description="State board disciplinary actions, most recent first.",
    )
    has_active_discipline: bool = Field(
        default=False,
        description="True if any disciplinary action is currently in effect.",
    )

    # --- Court Records ---
    court_cases: list[CourtCaseSummary] = Field(
        default_factory=list,
        description="Federal and state court cases involving this provider.",
    )

    # --- Hospital Affiliations ---
    hospital_affiliations: list[HospitalAffiliation] = Field(default_factory=list)
    group_practice_name: str | None = Field(
        default=None,
        max_length=300,
        description="Primary group practice name as reported by CMS.",
    )
    group_practice_pac_id: str | None = Field(default=None, max_length=20)

    # --- Insurance Participation ---
    insurance_participation: list[InsuranceParticipation] = Field(default_factory=list)
    accepts_medicare: bool | None = Field(
        default=None,
        description="True = participating, False = non-participating, None = unknown.",
    )
    opted_out_of_medicare: bool = Field(default=False)
    accepts_medicaid: bool | None = None

    # --- Research and Academic ---
    publication_count: int = Field(default=0, ge=0)
    recent_publications: list[PublicationSummary] = Field(
        default_factory=list,
        max_length=10,
        description="Most recent 10 publications (full list stored in NormalizedRecords).",
    )
    clinical_trial_count: int = Field(default=0, ge=0)

    # --- Reviews ---
    reviews: list[ReviewAggregate] = Field(
        default_factory=list,
        description="Aggregated review signals per platform.",
    )

    # --- Derived signals ---
    derived_signals: list[DerivedSignalSummary] = Field(
        default_factory=list,
        description="Computed risk/confidence/quality signals from C16 (Analytics & Anomaly Detection).",
    )
    overall_confidence: ConfidenceScore = Field(
        default=0.0,
        description="System-level confidence in the completeness and accuracy of this profile.",
    )
    report_completeness_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Fraction of expected data fields that have been populated.",
    )
    is_partial: bool = Field(
        default=True,
        description=(
            "True while source ingestion is still in progress. "
            "Reports generated from partial profiles are marked as partial."
        ),
    )

    # --- Source coverage tracking ---
    source_coverage: list[SourceCoverage] = Field(
        default_factory=list,
        description="Coverage status per source category.",
    )
    sources_attempted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_full_refresh_at: datetime | None = Field(
        default=None,
        description="Last time all enabled source adapters completed for this provider.",
    )
    schema_version: SchemaVersion = Field(default="v1")

    # --- Path B compliance fields ---
    report_disclaimer_required: bool = Field(
        default=True,
        description=(
            "Always True on Path B. Report generation must include the disclaimer that "
            "this report is for personal research only and may not be used in employment, "
            "credentialing, insurance, or credit decisions."
        ),
    )
    has_pending_corrections: bool = Field(
        default=False,
        description="True if any open Dispute records reference this profile.",
    )

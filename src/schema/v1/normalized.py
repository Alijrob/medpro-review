"""
normalized.py — NormalizedRecord base class and per-source-category subtypes.

NormalizedRecords are the output of C11 (Normalization Layer). Each record
represents a single piece of information from a single source, standardized
to a common schema. They are the write model — stored in Aurora and queried
during profile construction.

Source-specific subtypes carry typed payloads. The base NormalizedRecord
carries provenance, identity linkage, and lifecycle metadata.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import ConfigDict, Field

from .common import (
    NPI,
    Address,
    ConfidenceScore,
    DataProvenance,
    EntityType,
    ExclusionSource,
    ImmutableRecord,
    LicenseStatus,
    ProviderName,
    SchemaVersion,
    SourceCategory,
    TaxonomyCode,
    VerificationStatus,
    new_uuid,
)


# ---------------------------------------------------------------------------
# Base NormalizedRecord
# ---------------------------------------------------------------------------


class NormalizedRecord(ImmutableRecord):
    """
    Base class for all normalized source records.

    Every piece of external data that enters the system is stored as a
    NormalizedRecord. Source-specific subtypes add typed payload fields.
    The base record carries all metadata needed for provenance tracking,
    quality scoring, and lifecycle management.
    """

    record_id: UUID = Field(default_factory=new_uuid)
    entity_npi: NPI = Field(
        ...,
        description="The NPI of the provider this record pertains to.",
    )
    provenance: DataProvenance
    record_type: str = Field(
        ...,
        max_length=50,
        description="Discriminator for the record subtype (e.g., 'license', 'exclusion', 'court_case').",
    )
    status: VerificationStatus = Field(default=VerificationStatus.PENDING)
    confidence: ConfidenceScore = Field(
        default=0.8,
        description="System confidence in the accuracy of this record.",
    )
    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Data Quality Service score once C25 has run on this record.",
    )
    schema_version: SchemaVersion = Field(default="v1")


# ---------------------------------------------------------------------------
# Federal Registry Records (NPPES, OIG LEIE, SAM.gov, CMS Care Compare)
# ---------------------------------------------------------------------------


class NppesRecord(NormalizedRecord):
    """Normalized record from NPPES NPI Registry (Source F1)."""

    record_type: str = Field(default="nppes_npi", frozen=True)

    entity_type: EntityType
    name: ProviderName
    organization_name: str | None = Field(default=None, max_length=300)
    other_names: list[ProviderName] = Field(default_factory=list)
    enumeration_date: date | None = None
    last_updated_date: date | None = None
    deactivation_date: date | None = None
    reactivation_date: date | None = None
    npi_deactivation_reason: str | None = Field(default=None, max_length=100)
    sole_proprietor: bool | None = None
    addresses: list[Address] = Field(default_factory=list)
    taxonomy_codes: list[TaxonomyCode] = Field(default_factory=list)
    other_identifiers: list[dict[str, str]] = Field(
        default_factory=list,
        description="Raw other_identifier entries from NPPES (type + value pairs).",
    )


class OigLeieRecord(NormalizedRecord):
    """Normalized exclusion record from OIG LEIE (Source F2)."""

    record_type: str = Field(default="oig_leie_exclusion", frozen=True)

    exclusion_type: str = Field(..., max_length=50, description="OIG exclusion type code.")
    exclusion_date: date
    reinstatement_date: date | None = None
    waiver_date: date | None = None
    waiver_state: str | None = Field(default=None, max_length=2)
    general_exclusion: bool = Field(
        ...,
        description="True for mandatory exclusions; False for permissive exclusions.",
    )
    exclusion_description: str | None = Field(default=None, max_length=500)
    # Name as reported by OIG (may differ slightly from NPPES)
    reported_first_name: str | None = Field(default=None, max_length=100)
    reported_last_name: str | None = Field(default=None, max_length=100)
    reported_address: str | None = Field(default=None, max_length=300)
    specialty: str | None = Field(default=None, max_length=100)


class SamExclusionRecord(NormalizedRecord):
    """Normalized debarment/suspension record from SAM.gov (Source F3)."""

    record_type: str = Field(default="sam_exclusion", frozen=True)

    unique_entity_id: str = Field(..., max_length=50)
    exclusion_type: str = Field(..., max_length=100)
    exclusion_program: str | None = Field(default=None, max_length=100)
    active_exclusion: bool
    exclusion_date: date
    exclusion_expiration_date: date | None = None
    agency: str | None = Field(default=None, max_length=100)
    ct_code: str | None = Field(default=None, max_length=10)


class CmsProviderRecord(NormalizedRecord):
    """Normalized record from CMS Care Compare / Provider Data (Source F4)."""

    record_type: str = Field(default="cms_provider", frozen=True)

    group_practice_pac_id: str | None = Field(default=None, max_length=20)
    org_name: str | None = Field(default=None, max_length=300)
    num_group_practice_members: int | None = None
    graduation_year: int | None = Field(default=None, ge=1900, le=2030)
    medical_school: str | None = Field(default=None, max_length=200)
    # Hospital affiliations as reported by CMS
    hospital_affiliations: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of dicts with 'hospital_name', 'hospital_pac_id', 'hospital_ccn'.",
    )
    accepts_medicare_assignment: bool | None = None
    opted_out_of_medicare: bool | None = None
    medicare_participation_indicator: str | None = Field(default=None, max_length=10)


class MedicareEnrollmentRecord(NormalizedRecord):
    """Medicare participation record from CMS Physician Enrollment (Source I1)."""

    record_type: str = Field(default="medicare_enrollment", frozen=True)

    participation_indicator: str = Field(
        ...,
        max_length=1,
        description="'Y' = participating, 'N' = non-participating, 'O' = opted out.",
    )
    opt_out_effective_date: date | None = None
    opt_out_end_date: date | None = None
    specialty_description: str | None = Field(default=None, max_length=100)


class MedicaidEnrollmentRecord(NormalizedRecord):
    """Medicaid participation record from CMS Medicaid Enrollment (Source I2)."""

    record_type: str = Field(default="medicaid_enrollment", frozen=True)

    state: str = Field(..., max_length=2)
    enrollment_status: str = Field(..., max_length=50)
    enrollment_date: date | None = None
    termination_date: date | None = None
    provider_type: str | None = Field(default=None, max_length=100)


# ---------------------------------------------------------------------------
# State Medical Board Records
# ---------------------------------------------------------------------------


class StateBoardLicenseRecord(NormalizedRecord):
    """
    Normalized medical license record from any state medical board (Sources S1-S53).

    One record per license. A provider may hold licenses in multiple states,
    generating one StateBoardLicenseRecord per active/historical license.
    """

    record_type: str = Field(default="state_board_license", frozen=True)

    license_number: str = Field(..., max_length=50)
    state: str = Field(..., max_length=2)
    board_name: str = Field(..., max_length=200)
    license_type: str = Field(
        ...,
        max_length=100,
        description="Type of license (e.g., 'MD', 'DO', 'PA', 'NP').",
    )
    status: LicenseStatus
    issue_date: date | None = None
    expiration_date: date | None = None
    last_renewed_date: date | None = None
    # Disciplinary actions directly associated with this license
    disciplinary_actions: list["StateBoardDisciplinaryRecord"] = Field(default_factory=list)
    source_profile_url: str | None = Field(
        default=None,
        max_length=500,
        description="URL of the provider's profile on the state board website.",
    )


class StateBoardDisciplinaryRecord(NormalizedRecord):
    """
    A disciplinary action record from a state medical board.

    Separate from license record because one license may have multiple
    disciplinary actions with different effective dates and types.
    """

    model_config = ConfigDict(frozen=True)

    record_type: str = Field(default="state_board_disciplinary", frozen=True)

    state: str = Field(..., max_length=2)
    board_name: str = Field(..., max_length=200)
    action_type: str = Field(
        ...,
        max_length=100,
        description=(
            "Type of action taken (e.g., 'Revocation', 'Suspension', 'Probation', "
            "'Reprimand', 'Fine', 'License Restriction')."
        ),
    )
    effective_date: date | None = None
    expiration_date: date | None = None
    basis: str | None = Field(
        default=None,
        max_length=1000,
        description="Basis for the action as reported by the board.",
    )
    order_url: str | None = Field(
        default=None,
        max_length=500,
        description="URL to the public order document, if available.",
    )
    case_number: str | None = Field(default=None, max_length=100)
    is_active: bool = Field(
        ...,
        description="True if the action is currently in effect.",
    )


# ---------------------------------------------------------------------------
# Court Records
# ---------------------------------------------------------------------------


class CourtCaseRecord(NormalizedRecord):
    """
    Normalized federal or state court case record (Sources C1-C8).

    One record per case. A provider may be a party in multiple cases.
    """

    record_type: str = Field(default="court_case", frozen=True)

    court_type: str = Field(
        ...,
        max_length=50,
        description="'federal' or 'state'.",
        examples=["federal", "state"],
    )
    court_name: str = Field(..., max_length=200, examples=["S.D.N.Y.", "N.D. Cal."])
    case_number: str = Field(..., max_length=100)
    case_type: str = Field(
        ...,
        max_length=100,
        description="e.g., 'civil', 'criminal', 'bankruptcy', 'malpractice'.",
    )
    filing_date: date | None = None
    disposition_date: date | None = None
    disposition: str | None = Field(
        default=None,
        max_length=200,
        description="Case outcome (e.g., 'Dismissed', 'Judgment for Plaintiff', 'Settled').",
    )
    plaintiff: str | None = Field(default=None, max_length=300)
    defendant: str | None = Field(default=None, max_length=300)
    provider_party_role: str | None = Field(
        default=None,
        max_length=50,
        description="The provider's role in this case ('plaintiff', 'defendant', 'other').",
    )
    case_summary: str | None = Field(
        default=None,
        max_length=2000,
        description="Brief description of the case as extracted from the docket.",
    )
    docket_url: str | None = Field(default=None, max_length=500)
    pacer_case_id: str | None = Field(default=None, max_length=50)


# ---------------------------------------------------------------------------
# Academic / Research Records
# ---------------------------------------------------------------------------


class PubMedRecord(NormalizedRecord):
    """Publication record from PubMed / NCBI Entrez (Source A1)."""

    record_type: str = Field(default="pubmed_publication", frozen=True)

    pmid: str = Field(..., max_length=20, description="PubMed ID.")
    title: str = Field(..., max_length=1000)
    journal: str | None = Field(default=None, max_length=200)
    publication_date: date | None = None
    publication_year: int | None = Field(default=None, ge=1800, le=2100)
    doi: str | None = Field(default=None, max_length=200)
    citation_count: int | None = Field(default=None, ge=0)
    author_position: str | None = Field(
        default=None,
        max_length=50,
        description="'first', 'last', 'middle', or 'corresponding'.",
    )
    abstract_snippet: str | None = Field(
        default=None,
        max_length=500,
        description="First 500 characters of the abstract.",
    )


class ClinicalTrialRecord(NormalizedRecord):
    """Clinical trial investigator record from ClinicalTrials.gov (Source A2)."""

    record_type: str = Field(default="clinical_trial", frozen=True)

    nct_id: str = Field(..., pattern=r"^NCT\d{8}$", description="ClinicalTrials.gov identifier.")
    title: str = Field(..., max_length=1000)
    status: str = Field(..., max_length=50, description="Trial status (e.g., 'Recruiting', 'Completed').")
    sponsor: str | None = Field(default=None, max_length=200)
    investigator_role: str | None = Field(
        default=None,
        max_length=100,
        description="e.g., 'Principal Investigator', 'Sub-Investigator'.",
    )
    start_date: date | None = None
    completion_date: date | None = None
    condition: str | None = Field(default=None, max_length=200)


# ---------------------------------------------------------------------------
# Review Platform Records
# ---------------------------------------------------------------------------


class ReviewPlatformRecord(NormalizedRecord):
    """
    Aggregated review summary from a review platform (Sources R1 Google Places, R2 Yelp).

    One record per platform per provider. Updated on each refresh cycle.
    Stores the aggregate snapshot, not individual reviews (which are not stored).
    """

    record_type: str = Field(default="review_summary", frozen=True)

    platform: str = Field(
        ...,
        max_length=50,
        description="Review platform identifier (e.g., 'google_places', 'yelp').",
        examples=["google_places", "yelp"],
    )
    platform_place_id: str | None = Field(
        default=None,
        max_length=200,
        description="Platform-specific location/business ID.",
    )
    rating: float | None = Field(default=None, ge=0.0, le=5.0)
    review_count: int | None = Field(default=None, ge=0)
    platform_url: str | None = Field(default=None, max_length=500)
    as_of_date: datetime | None = Field(
        default=None,
        description="When this aggregate was fetched. Subject to platform cache windows.",
    )
    cache_expires_at: datetime | None = Field(
        default=None,
        description="When this record must be refreshed per platform ToS.",
    )


# ---------------------------------------------------------------------------
# NPDB Public Use File Record (aggregate signals only — no individual IDs)
# ---------------------------------------------------------------------------


class NpdbAggregateRecord(NormalizedRecord):
    """
    Aggregate malpractice/adverse action signal derived from the NPDB Public Use File (Source F6).

    The NPDB public file does not contain individual provider IDs. This record stores
    state/specialty-level aggregate signals that can enrich report context
    (e.g., "X% of surgeons in this state had a malpractice payment in this period").
    Not used for individual provider scoring — only for contextual benchmarking.
    """

    record_type: str = Field(default="npdb_aggregate", frozen=True)

    state: str = Field(..., max_length=2)
    specialty_group: str = Field(..., max_length=100)
    report_period_start: date
    report_period_end: date
    payment_count: int = Field(..., ge=0)
    payment_total_usd: Decimal | None = None
    adverse_action_count: int = Field(..., ge=0)
    total_practitioners_in_group: int | None = Field(default=None, ge=0)
    malpractice_payment_rate: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Fraction of practitioners in this group with at least one payment in the period.",
    )

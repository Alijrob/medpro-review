"""
models.py -- ProviderReport and its section sub-models (C17 basic).

ProviderReport is the structured output of build_report(). It is serialised as
JSON for the API response and rendered to HTML by renderer.py (Jinja2).

Design rules:
- All fields are plain Python types or nested Pydantic models (JSON-serialisable).
- No direct coupling to CanonicalProviderProfile -- builder.py performs the
  transformation so renderer.py stays template-only.
- is_partial propagates from the source profile.
- disclaimer is always set (Path B requirement).
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from schema.v1.common import MedproBaseModel, new_uuid, utc_now


# ---------------------------------------------------------------------------
# Section sub-models
# ---------------------------------------------------------------------------


class ReportProviderIdentity(MedproBaseModel):
    """Core identity block: who this provider is."""

    npi: str
    entity_type: str  # "individual" | "organization"
    display_name: str  # formatted full name or org name
    first_name: str | None = None
    last_name: str | None = None
    credentials: list[str] = Field(default_factory=list)
    primary_specialty: str | None = None
    specialty_group: str | None = None
    gender: str | None = None
    sole_proprietor: bool | None = None


class ReportAddress(MedproBaseModel):
    """A single address entry in the report."""

    address_type: str  # "practice" | "mailing"
    line1: str
    line2: str | None = None
    city: str
    state: str
    zip_code: str
    phone: str | None = None
    fax: str | None = None


class ReportLicenseEntry(MedproBaseModel):
    """One state license row in the report."""

    state: str
    board_name: str
    license_number: str
    license_type: str
    status: str  # human-readable status string
    status_is_active: bool
    expiration_date: date | None = None
    as_of_date: date | None = None
    source_id: str


class ReportExclusionEntry(MedproBaseModel):
    """One federal/state exclusion row in the report."""

    authority: str  # "OIG LEIE" | "SAM.gov" | other
    exclusion_type: str
    effective_date: date | None = None
    reinstatement_date: date | None = None
    is_active: bool
    basis: str | None = None
    source_id: str


class ReportDisciplinaryEntry(MedproBaseModel):
    """One disciplinary action row in the report."""

    state: str
    board_name: str
    action_type: str
    effective_date: date | None = None
    is_active: bool
    basis: str | None = None
    case_number: str | None = None
    source_id: str


class ReportEducationEntry(MedproBaseModel):
    """One education record row in the report."""

    institution_name: str
    degree: str | None = None
    field_of_study: str | None = None
    graduation_year: int | None = None


class ReportSection(MedproBaseModel):
    """Metadata wrapper around any report section."""

    section_name: str
    has_data: bool
    data_as_of: datetime | None = None
    sources_contributing: list[str] = Field(default_factory=list)


class ReportSourceCoverage(MedproBaseModel):
    """Per-source coverage entry shown in the report footer."""

    source_id: str
    source_category: str
    status: str  # "success" | "partial" | "failed" | "not_attempted"
    fetched_at: datetime | None = None


# ---------------------------------------------------------------------------
# Top-level report model
# ---------------------------------------------------------------------------


class ProviderReport(MedproBaseModel):
    """
    The complete structured report for a single provider (C17 basic).

    Produced by build_report(profile) from a CanonicalProviderProfile.
    Rendered to JSON (model_dump_json) and HTML (renderer.render_html).
    """

    report_id: UUID = Field(default_factory=new_uuid)
    npi: str
    generated_at: datetime = Field(default_factory=utc_now)
    schema_version: str = "v1"

    # --- Partial / completeness ---
    is_partial: bool = Field(
        default=True,
        description="Mirrors CanonicalProviderProfile.is_partial.",
    )
    report_completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    last_full_refresh_at: datetime | None = None

    # --- Provider identity ---
    identity: ReportProviderIdentity

    # --- Addresses ---
    addresses: list[ReportAddress] = Field(default_factory=list)

    # --- Licenses ---
    licenses: list[ReportLicenseEntry] = Field(default_factory=list)
    has_active_license: bool = False
    active_license_count: int = 0

    # --- Exclusions ---
    exclusions: list[ReportExclusionEntry] = Field(default_factory=list)
    has_active_exclusion: bool = False

    # --- Disciplinary ---
    disciplinary_actions: list[ReportDisciplinaryEntry] = Field(default_factory=list)
    has_active_discipline: bool = False

    # --- Education ---
    education: list[ReportEducationEntry] = Field(default_factory=list)

    # --- Insurance ---
    accepts_medicare: bool | None = None
    opted_out_of_medicare: bool = False
    accepts_medicaid: bool | None = None

    # --- Source coverage ---
    sources_attempted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    source_coverage: list[ReportSourceCoverage] = Field(default_factory=list)

    # --- Compliance (Path B -- always present) ---
    disclaimer: str
    report_disclaimer_required: bool = True
    has_pending_corrections: bool = False

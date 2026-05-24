"""
users.py — User, Report, and Dispute models.

Path B compliance is embedded here:
- UseAgreement records the user's certification at checkout that the report
  is for personal research only (not employment/credentialing/credit/insurance).
- Dispute is the simplified Path B correction workflow — no FCRA § 1681i SLA,
  but retains HitL review, audit trail, and correction tracking.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import EmailStr, Field

from .common import NPI, MedproBaseModel, VerificationStatus, new_uuid, utc_now


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class UserRole(str, Enum):
    """Platform user role."""

    CONSUMER = "consumer"       # Standard B2C user
    PROVIDER = "provider"       # A physician who has claimed their own profile
    ADMIN = "admin"             # Internal admin user
    REVIEWER = "reviewer"       # Internal HitL dispute reviewer


class ReportStatus(str, Enum):
    """Lifecycle state of a report request."""

    QUEUED = "queued"               # Accepted, not yet started
    IN_PROGRESS = "in_progress"     # Temporal workflow running
    PARTIAL = "partial"             # Completed with some sources missing
    COMPLETE = "complete"           # All attempted sources returned
    FAILED = "failed"               # Workflow failed before producing any output
    EXPIRED = "expired"             # Report TTL exceeded without delivery


class ReportType(str, Enum):
    """The type of report requested."""

    COMPREHENSIVE = "comprehensive"     # All enabled sources, 10-min SLA
    PARTIAL = "partial"                 # Fast report from P1 federal sources only, 2-min SLA
    REFRESH = "refresh"                 # Re-run on a previously generated report


class DisputeStatus(str, Enum):
    """Lifecycle state of a data correction request."""

    SUBMITTED = "submitted"         # Received, pending triage
    UNDER_REVIEW = "under_review"   # Assigned to a HitL reviewer
    RESOLVED_CORRECTED = "resolved_corrected"   # Correction confirmed and applied
    RESOLVED_UPHELD = "resolved_upheld"         # Data verified as accurate; no change
    RESOLVED_REMOVED = "resolved_removed"       # Data removed (source retracted or unverifiable)
    CLOSED_DUPLICATE = "closed_duplicate"       # Duplicate of another open dispute
    CLOSED_INSUFFICIENT = "closed_insufficient" # Insufficient information to investigate


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class UseAgreement(MedproBaseModel):
    """
    Path B: Records the user's certification at checkout that the report will
    be used for personal research only.

    This certification is required on every report purchase. The version field
    tracks which version of the ToS the user agreed to, enabling audit of any
    future ToS version upgrades.
    """

    agreement_id: UUID = Field(default_factory=new_uuid)
    tos_version: str = Field(
        ...,
        max_length=20,
        description="Version identifier of the Terms of Service agreed to.",
        examples=["tos-v1.0", "tos-v1.1"],
    )
    agreed_at: datetime = Field(default_factory=utc_now)
    ip_address: str | None = Field(
        default=None,
        max_length=45,
        description="IPv4 or IPv6 address at time of agreement. Stored for legal evidence.",
    )
    user_agent: str | None = Field(default=None, max_length=500)
    certified_personal_use_only: bool = Field(
        ...,
        description=(
            "MUST be True. User certifies the report is for personal research only and "
            "will NOT be used in employment, credentialing, licensing, insurance underwriting, "
            "or credit decisions. Per DECISIONS.md Entry 004 (Path B)."
        ),
    )


class User(MedproBaseModel):
    """A registered consumer account."""

    user_id: UUID = Field(default_factory=new_uuid)
    email: EmailStr
    role: UserRole = Field(default=UserRole.CONSUMER)
    is_active: bool = Field(default=True)
    is_email_verified: bool = Field(default=False)

    # Auth0/Okta external identifier
    auth_provider_sub: str | None = Field(
        default=None,
        max_length=200,
        description="Subject claim from the IDaaS token (Auth0 sub or Okta sub).",
    )

    # ToS agreement history (most recent last)
    use_agreements: list[UseAgreement] = Field(
        default_factory=list,
        description="History of ToS certifications. User must have at least one before purchasing.",
    )

    # Provider profile claim (if role=PROVIDER)
    claimed_provider_npi: NPI | None = Field(
        default=None,
        description="If role=PROVIDER: the NPI this user has claimed as their own profile.",
    )
    provider_claim_verified: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utc_now)
    last_login_at: datetime | None = None
    deleted_at: datetime | None = Field(
        default=None,
        description="Set on CCPA/deletion request. Soft delete — PII zeroed, record retained.",
    )

    @property
    def has_current_agreement(self) -> bool:
        """True if the user has at least one certified personal-use agreement."""
        return any(a.certified_personal_use_only for a in self.use_agreements)


class Report(MedproBaseModel):
    """
    A report request and its output metadata.

    The rendered report content (HTML, PDF, JSON) is stored in S3.
    This record tracks the request lifecycle, source coverage, and links to the S3 object.
    """

    report_id: UUID = Field(default_factory=new_uuid)
    user_id: UUID = Field(..., description="FK to User.user_id.")
    provider_npi: NPI = Field(..., description="The provider this report is about.")
    report_type: ReportType = Field(default=ReportType.COMPREHENSIVE)
    status: ReportStatus = Field(default=ReportStatus.QUEUED)

    # Path B compliance — must be populated before any report is generated
    use_agreement_id: UUID = Field(
        ...,
        description=(
            "FK to the UseAgreement record at time of purchase. "
            "Report generation fails if this is missing (Path B enforcement)."
        ),
    )
    tos_version_at_purchase: str = Field(..., max_length=20)

    # Temporal workflow tracking
    temporal_workflow_id: str | None = Field(
        default=None,
        max_length=200,
        description="Temporal workflow run ID for this report.",
    )

    # Source tracking
    sources_attempted: list[str] = Field(default_factory=list)
    sources_succeeded: list[str] = Field(default_factory=list)
    sources_failed: list[str] = Field(default_factory=list)
    is_partial: bool = Field(
        default=False,
        description="True if delivered with one or more sources still outstanding.",
    )

    # Output
    report_s3_key: str | None = Field(
        default=None,
        max_length=500,
        description="S3 object key for the stored report (HTML/PDF/JSON).",
    )
    profile_snapshot_id: UUID | None = Field(
        default=None,
        description="FK to the CanonicalProviderProfile version used to generate this report.",
    )

    # Payment
    price_paid_usd: Decimal | None = Field(default=None, ge=Decimal("0"))
    stripe_payment_intent_id: str | None = Field(default=None, max_length=100)

    # Timestamps
    requested_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime | None = Field(
        default=None,
        description="When this report link expires (for temporary signed S3 URLs).",
    )

    @property
    def duration_seconds(self) -> float | None:
        """Report generation time in seconds, or None if not yet complete."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class DisputeField(MedproBaseModel):
    """A specific field within a report that the submitter believes is inaccurate."""

    field_path: str = Field(
        ...,
        max_length=200,
        description=(
            "Dot-notation path to the field in the CanonicalProviderProfile "
            "(e.g., 'licenses[0].status', 'disciplinary_actions[1].basis')."
        ),
    )
    reported_value: str | None = Field(
        default=None,
        max_length=500,
        description="The value currently shown in the report.",
    )
    claimed_correct_value: str | None = Field(
        default=None,
        max_length=500,
        description="The value the submitter believes is correct.",
    )
    supporting_evidence_urls: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="URLs to public evidence supporting the correction (e.g., board website).",
    )


class Dispute(MedproBaseModel):
    """
    A data correction request (Path B simplified dispute workflow).

    Retains: structured submission, HitL review, audit trail, correction tracking.
    Removed: FCRA § 1681i 30-day legal SLA, mandatory adverse action retraction.
    Internal SLA target: resolve within 30 days (voluntary, not legally mandated).

    Per DECISIONS.md Entry 007.
    """

    dispute_id: UUID = Field(default_factory=new_uuid)
    report_id: UUID | None = Field(
        default=None,
        description="FK to the Report that surfaced the disputed data. Optional — providers may flag their profile directly.",
    )
    user_id: UUID | None = Field(
        default=None,
        description="FK to the User who submitted this correction. None for provider-submitted disputes.",
    )
    provider_npi: NPI = Field(..., description="The provider whose data is being disputed.")
    submitter_type: str = Field(
        default="consumer",
        max_length=20,
        description="'consumer' (user who purchased report) or 'provider' (physician about their own profile).",
    )

    status: DisputeStatus = Field(default=DisputeStatus.SUBMITTED)
    flagged_fields: list[DisputeField] = Field(
        ...,
        min_length=1,
        description="One or more specific fields the submitter believes are inaccurate.",
    )
    description: str = Field(
        ...,
        max_length=2000,
        description="Submitter's explanation of why the data is incorrect.",
    )

    # Review assignment
    reviewer_id: UUID | None = Field(
        default=None,
        description="FK to the internal User (role=REVIEWER) assigned to this dispute.",
    )
    assigned_at: datetime | None = None

    # Resolution
    resolved_at: datetime | None = None
    resolution_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Internal reviewer notes explaining the resolution decision.",
    )
    corrected_record_ids: list[UUID] = Field(
        default_factory=list,
        description="IDs of NormalizedRecords that were updated as a result of this dispute.",
    )
    correction_applied_at: datetime | None = None

    # Timestamps
    submitted_at: datetime = Field(default_factory=utc_now)
    target_resolution_date: datetime | None = Field(
        default=None,
        description="Voluntary 30-day target. Not a legal deadline on Path B.",
    )
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def is_open(self) -> bool:
        return self.status in (DisputeStatus.SUBMITTED, DisputeStatus.UNDER_REVIEW)

    @property
    def days_open(self) -> int | None:
        if self.resolved_at:
            return (self.resolved_at - self.submitted_at).days
        return (utc_now() - self.submitted_at).days

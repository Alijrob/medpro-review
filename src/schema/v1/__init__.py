"""
schema/v1 — Canonical schema v1 for Medical Professionals Review.

Import public types from here. Do not import directly from sub-modules
in application code — use this package's exports for stability.
"""

from .audit import ActorType, AuditEvent, AuditEventType, TargetType
from .common import (
    NPI,
    Address,
    ConfidenceScore,
    DataProvenance,
    EntityType,
    ExclusionSource,
    Gender,
    ImmutableRecord,
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
from .identity import OtherIdentifier, ProviderIdentity, UnifiedIdBundle
from .normalized import (
    ClinicalTrialRecord,
    CmsProviderRecord,
    CourtCaseRecord,
    MedicaidEnrollmentRecord,
    MedicareEnrollmentRecord,
    NormalizedRecord,
    NpdbAggregateRecord,
    NppesRecord,
    OigLeieRecord,
    PubMedRecord,
    ReviewPlatformRecord,
    SamExclusionRecord,
    StateBoardDisciplinaryRecord,
    StateBoardLicenseRecord,
)
from .profile import (
    CanonicalProviderProfile,
    CourtCaseSummary,
    DerivedSignalSummary,
    DisciplinaryAction,
    ExclusionRecord,
    HospitalAffiliation,
    InsuranceParticipation,
    LicenseRecord,
    PublicationSummary,
    ReviewAggregate,
    SourceCoverage,
)
from .source_health import DerivedSignal, DerivedSignalType, SourceHealthRecord, SourceStatus
from .users import (
    Dispute,
    DisputeField,
    DisputeStatus,
    Report,
    ReportStatus,
    ReportType,
    UseAgreement,
    User,
    UserRole,
)

__all__ = [
    # common
    "NPI", "Address", "ConfidenceScore", "DataProvenance", "EntityType",
    "ExclusionSource", "Gender", "ImmutableRecord", "LicenseStatus",
    "MedproBaseModel", "ProviderName", "SchemaVersion", "SourceCategory",
    "TaxonomyCode", "VerificationStatus", "new_uuid", "utc_now",
    # identity
    "OtherIdentifier", "ProviderIdentity", "UnifiedIdBundle",
    # normalized
    "NormalizedRecord", "NppesRecord", "OigLeieRecord", "SamExclusionRecord",
    "CmsProviderRecord", "MedicareEnrollmentRecord", "MedicaidEnrollmentRecord",
    "StateBoardLicenseRecord", "StateBoardDisciplinaryRecord",
    "CourtCaseRecord", "PubMedRecord", "ClinicalTrialRecord",
    "ReviewPlatformRecord", "NpdbAggregateRecord",
    # profile
    "CanonicalProviderProfile", "LicenseRecord", "DisciplinaryAction",
    "ExclusionRecord", "CourtCaseSummary", "HospitalAffiliation",
    "InsuranceParticipation", "PublicationSummary", "ReviewAggregate",
    "SourceCoverage", "DerivedSignalSummary",
    # users
    "UseAgreement", "User", "UserRole", "Report", "ReportStatus", "ReportType",
    "Dispute", "DisputeField", "DisputeStatus",
    # audit
    "AuditEvent", "AuditEventType", "ActorType", "TargetType",
    # source health + derived signals
    "SourceHealthRecord", "SourceStatus", "DerivedSignal", "DerivedSignalType",
]

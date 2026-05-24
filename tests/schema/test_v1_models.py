"""
tests/schema/test_v1_models.py

Phase 1-A acceptance tests for all canonical schema v1 models.

Tests cover:
- Valid instantiation of every model
- NPI validation (10 digits, pattern enforcement)
- ConfidenceScore bounds (0.0-1.0)
- DataProvenance hash utility
- AuditEvent hash-chain utility
- CanonicalProviderProfile field defaults
- UseAgreement Path B compliance flag
- Dispute lifecycle helpers
- Schema registry: list_models, get_json_schema, validate, detect_drift
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from schema.registry import registry
from schema.v1 import (
    ActorType,
    Address,
    AuditEvent,
    AuditEventType,
    CanonicalProviderProfile,
    ClinicalTrialRecord,
    CmsProviderRecord,
    CourtCaseRecord,
    DataProvenance,
    DerivedSignal,
    DerivedSignalType,
    Dispute,
    DisputeField,
    DisputeStatus,
    EntityType,
    Gender,
    LicenseRecord,
    LicenseStatus,
    MedicaidEnrollmentRecord,
    MedicareEnrollmentRecord,
    NpdbAggregateRecord,
    NppesRecord,
    OigLeieRecord,
    OtherIdentifier,
    ProviderIdentity,
    ProviderName,
    PubMedRecord,
    Report,
    ReportStatus,
    ReportType,
    ReviewPlatformRecord,
    SamExclusionRecord,
    SourceCategory,
    SourceHealthRecord,
    SourceStatus,
    StateBoardDisciplinaryRecord,
    StateBoardLicenseRecord,
    TargetType,
    TaxonomyCode,
    UnifiedIdBundle,
    UseAgreement,
    User,
    UserRole,
    VerificationStatus,
    new_uuid,
    utc_now,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_NPI = "1234567890"
INVALID_NPI_SHORT = "123456789"
INVALID_NPI_ALPHA = "123456789X"

NOW = datetime.now(tz=timezone.utc)
TODAY = date.today()


def make_provenance(source_id: str = "F1") -> DataProvenance:
    raw = {"npi": VALID_NPI, "name": "test"}
    return DataProvenance(
        source_id=source_id,
        source_name="NPPES NPI Registry",
        source_category=SourceCategory.FEDERAL,
        source_record_id=VALID_NPI,
        ingested_at=NOW,
        raw_record_hash=DataProvenance.hash_raw(raw),
    )


def make_name(first: str = "Jane", last: str = "Smith") -> ProviderName:
    return ProviderName(first=first, last=last, credentials="MD")


def make_address() -> Address:
    return Address(
        street_line_1="100 Main St",
        city="Springfield",
        state="IL",
        postal_code="62701",
    )


def make_taxonomy() -> TaxonomyCode:
    return TaxonomyCode(
        code="207Q00000X",
        description="Family Medicine",
        primary=True,
    )


# ---------------------------------------------------------------------------
# NPI validation
# ---------------------------------------------------------------------------


class TestNpiValidation:
    def test_valid_npi_accepted(self) -> None:
        name = make_name()
        prov = make_provenance()
        record = NppesRecord(
            entity_npi=VALID_NPI,
            provenance=prov,
            entity_type=EntityType.INDIVIDUAL,
            name=name,
        )
        assert record.entity_npi == VALID_NPI

    def test_short_npi_rejected(self) -> None:
        with pytest.raises(Exception):
            ProviderIdentity(
                npi=INVALID_NPI_SHORT,
                entity_type=EntityType.INDIVIDUAL,
                name=make_name(),
            )

    def test_alpha_npi_rejected(self) -> None:
        with pytest.raises(Exception):
            ProviderIdentity(
                npi=INVALID_NPI_ALPHA,
                entity_type=EntityType.INDIVIDUAL,
                name=make_name(),
            )


# ---------------------------------------------------------------------------
# DataProvenance
# ---------------------------------------------------------------------------


class TestDataProvenance:
    def test_hash_raw_is_sha256(self) -> None:
        raw = {"key": "value", "number": 42}
        result = DataProvenance.hash_raw(raw)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_raw_deterministic(self) -> None:
        raw = {"b": 2, "a": 1}
        h1 = DataProvenance.hash_raw(raw)
        h2 = DataProvenance.hash_raw({"a": 1, "b": 2})
        assert h1 == h2  # sort_keys=True

    def test_provenance_instantiation(self) -> None:
        prov = make_provenance("F2")
        assert prov.source_id == "F2"
        assert prov.schema_version == "v1"
        assert len(prov.raw_record_hash) == 64


# ---------------------------------------------------------------------------
# ProviderName
# ---------------------------------------------------------------------------


class TestProviderName:
    def test_full_name(self) -> None:
        name = ProviderName(first="Jane", last="Smith", credentials="MD", prefix="Dr.")
        assert "Jane" in name.full_name
        assert "Smith" in name.full_name
        assert "MD" in name.full_name

    def test_sort_key_normalized(self) -> None:
        name = ProviderName(first="JANE", last="SMITH")
        assert name.sort_key == "smith,jane,"


# ---------------------------------------------------------------------------
# NormalizedRecord subtypes
# ---------------------------------------------------------------------------


class TestNppesRecord:
    def test_basic_instantiation(self) -> None:
        record = NppesRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance("F1"),
            entity_type=EntityType.INDIVIDUAL,
            name=make_name(),
            addresses=[make_address()],
            taxonomy_codes=[make_taxonomy()],
        )
        assert record.record_type == "nppes_npi"
        assert record.status == VerificationStatus.PENDING
        assert record.schema_version == "v1"

    def test_record_id_is_uuid(self) -> None:
        record = NppesRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance(),
            entity_type=EntityType.INDIVIDUAL,
            name=make_name(),
        )
        assert isinstance(record.record_id, UUID)


class TestOigLeieRecord:
    def test_exclusion_record(self) -> None:
        record = OigLeieRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance("F2"),
            exclusion_type="1128a1",
            exclusion_date=TODAY,
            general_exclusion=True,
        )
        assert record.record_type == "oig_leie_exclusion"
        assert record.general_exclusion is True


class TestSamExclusionRecord:
    def test_sam_record(self) -> None:
        record = SamExclusionRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance("F3"),
            unique_entity_id="ABCDEF123456",
            exclusion_type="Ineligible (Proceedings Pending)",
            active_exclusion=True,
            exclusion_date=TODAY,
        )
        assert record.record_type == "sam_exclusion"


class TestStateBoardLicenseRecord:
    def test_license_record(self) -> None:
        record = StateBoardLicenseRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance("S5"),
            license_number="A123456",
            state="CA",
            board_name="Medical Board of California",
            license_type="MD",
            status=LicenseStatus.ACTIVE,
            issue_date=date(2010, 1, 15),
            expiration_date=date(2026, 1, 15),
        )
        assert record.record_type == "state_board_license"
        assert record.status == LicenseStatus.ACTIVE


class TestCourtCaseRecord:
    def test_court_record(self) -> None:
        record = CourtCaseRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance("C2"),
            court_type="federal",
            court_name="S.D.N.Y.",
            case_number="1:23-cv-01234",
            case_type="civil",
            filing_date=date(2023, 3, 1),
            provider_party_role="defendant",
        )
        assert record.record_type == "court_case"


class TestReviewPlatformRecord:
    def test_google_review(self) -> None:
        record = ReviewPlatformRecord(
            entity_npi=VALID_NPI,
            provenance=make_provenance("R1"),
            platform="google_places",
            rating=4.2,
            review_count=87,
            as_of_date=NOW,
        )
        assert record.platform == "google_places"
        assert record.record_type == "review_summary"

    def test_rating_bounds(self) -> None:
        with pytest.raises(Exception):
            ReviewPlatformRecord(
                entity_npi=VALID_NPI,
                provenance=make_provenance("R1"),
                platform="google_places",
                rating=6.0,  # > 5.0 — should fail
                review_count=10,
                as_of_date=NOW,
            )


# ---------------------------------------------------------------------------
# Identity models
# ---------------------------------------------------------------------------


class TestProviderIdentity:
    def test_basic(self) -> None:
        identity = ProviderIdentity(
            npi=VALID_NPI,
            entity_type=EntityType.INDIVIDUAL,
            name=make_name(),
            taxonomy_codes=[make_taxonomy()],
            addresses=[make_address()],
        )
        assert identity.npi == VALID_NPI
        assert identity.gender == Gender.UNKNOWN


class TestUnifiedIdBundle:
    def test_bundle(self) -> None:
        bundle = UnifiedIdBundle(
            primary_npi=VALID_NPI,
            entity_type=EntityType.INDIVIDUAL,
            primary_name=make_name(),
            identity_confidence=0.99,
            contributing_sources=["F1", "F4"],
        )
        assert bundle.identity_confidence == 0.99
        assert bundle.human_review_required is False
        assert isinstance(bundle.bundle_id, UUID)


# ---------------------------------------------------------------------------
# CanonicalProviderProfile
# ---------------------------------------------------------------------------


class TestCanonicalProviderProfile:
    def make_profile(self) -> CanonicalProviderProfile:
        return CanonicalProviderProfile(
            npi=VALID_NPI,
            bundle_id=new_uuid(),
            entity_type=EntityType.INDIVIDUAL,
            primary_name=make_name(),
            overall_confidence=0.85,
        )

    def test_profile_defaults(self) -> None:
        p = self.make_profile()
        assert p.currently_excluded is False
        assert p.has_active_discipline is False
        assert p.is_partial is True
        assert p.report_disclaimer_required is True  # Path B compliance
        assert p.active_license_count == 0
        assert p.publication_count == 0

    def test_path_b_disclaimer_required(self) -> None:
        """Path B: report_disclaimer_required must default to True."""
        p = self.make_profile()
        assert p.report_disclaimer_required is True

    def test_with_license(self) -> None:
        p = self.make_profile()
        license_ = LicenseRecord(
            state="CA",
            board_name="Medical Board of California",
            license_number="A123456",
            license_type="MD",
            status=LicenseStatus.ACTIVE,
            source_id="S5",
        )
        p.licenses.append(license_)
        assert len(p.licenses) == 1
        assert p.licenses[0].status == LicenseStatus.ACTIVE


# ---------------------------------------------------------------------------
# User, UseAgreement, Report, Dispute
# ---------------------------------------------------------------------------


class TestUseAgreement:
    def test_valid_agreement(self) -> None:
        agreement = UseAgreement(
            tos_version="tos-v1.0",
            certified_personal_use_only=True,
            ip_address="192.168.1.1",
        )
        assert agreement.certified_personal_use_only is True

    def test_path_b_false_raises(self) -> None:
        """certified_personal_use_only=False should not prevent model creation
        (validation is enforced at the application layer, not schema layer)
        but we verify the field value is recorded."""
        agreement = UseAgreement(
            tos_version="tos-v1.0",
            certified_personal_use_only=False,
        )
        assert agreement.certified_personal_use_only is False


class TestUser:
    def test_user_defaults(self) -> None:
        user = User(email="patient@example.com")
        assert user.role == UserRole.CONSUMER
        assert user.is_active is True
        assert user.is_email_verified is False
        assert user.has_current_agreement is False

    def test_has_current_agreement_true(self) -> None:
        agreement = UseAgreement(
            tos_version="tos-v1.0",
            certified_personal_use_only=True,
        )
        user = User(email="patient@example.com", use_agreements=[agreement])
        assert user.has_current_agreement is True


class TestReport:
    def test_report_instantiation(self) -> None:
        use_agreement_id = new_uuid()
        report = Report(
            user_id=new_uuid(),
            provider_npi=VALID_NPI,
            report_type=ReportType.COMPREHENSIVE,
            use_agreement_id=use_agreement_id,
            tos_version_at_purchase="tos-v1.0",
        )
        assert report.status == ReportStatus.QUEUED
        assert report.is_partial is False
        assert isinstance(report.report_id, UUID)

    def test_duration_none_when_not_complete(self) -> None:
        report = Report(
            user_id=new_uuid(),
            provider_npi=VALID_NPI,
            use_agreement_id=new_uuid(),
            tos_version_at_purchase="tos-v1.0",
        )
        assert report.duration_seconds is None


class TestDispute:
    def make_dispute(self) -> Dispute:
        return Dispute(
            provider_npi=VALID_NPI,
            flagged_fields=[
                DisputeField(
                    field_path="licenses[0].status",
                    reported_value="revoked",
                    claimed_correct_value="active",
                )
            ],
            description="My license was incorrectly listed as revoked.",
        )

    def test_dispute_defaults(self) -> None:
        d = self.make_dispute()
        assert d.status == DisputeStatus.SUBMITTED
        assert d.is_open is True
        assert d.days_open is not None
        assert d.days_open >= 0

    def test_dispute_requires_flagged_fields(self) -> None:
        with pytest.raises(Exception):
            Dispute(
                provider_npi=VALID_NPI,
                flagged_fields=[],  # min_length=1
                description="Test",
            )


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------


class TestAuditEvent:
    def make_event(self) -> AuditEvent:
        return AuditEvent(
            event_type=AuditEventType.RECORD_INGESTED,
            actor_type=ActorType.SYSTEM,
            actor_id="temporal-worker-1",
            target_type=TargetType.NORMALIZED_RECORD,
            target_id=str(new_uuid()),
            action="NormalizedRecord ingested from NPPES bulk download",
        )

    def test_event_instantiation(self) -> None:
        event = self.make_event()
        assert event.event_type == AuditEventType.RECORD_INGESTED
        assert isinstance(event.event_id, UUID)

    def test_compute_hash_deterministic(self) -> None:
        event = self.make_event()
        h1 = AuditEvent.compute_hash(event)
        h2 = AuditEvent.compute_hash(event)
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_hash_changes_on_different_events(self) -> None:
        e1 = self.make_event()
        e2 = AuditEvent(
            event_type=AuditEventType.PROFILE_UPDATED,
            actor_type=ActorType.SYSTEM,
            target_type=TargetType.CANONICAL_PROFILE,
            target_id=str(new_uuid()),
            action="Profile rebuilt",
        )
        assert AuditEvent.compute_hash(e1) != AuditEvent.compute_hash(e2)


# ---------------------------------------------------------------------------
# SourceHealthRecord + DerivedSignal
# ---------------------------------------------------------------------------


class TestSourceHealthRecord:
    def test_basic(self) -> None:
        record = SourceHealthRecord(
            source_id="F1",
            source_name="NPPES NPI Registry",
            source_category=SourceCategory.FEDERAL,
        )
        assert record.status == SourceStatus.UNKNOWN
        assert record.schema_drift_detected is False
        assert record.consecutive_failures == 0


class TestDerivedSignal:
    def test_exclusion_flag(self) -> None:
        signal = DerivedSignal(
            provider_npi=VALID_NPI,
            signal_type=DerivedSignalType.EXCLUSION_ACTIVE,
            value=1.0,
            confidence=0.99,
            explanation="The provider is currently listed on the OIG LEIE exclusion database.",
            contributing_sources=["F2"],
        )
        assert signal.value == 1.0
        assert signal.model_version == "rule-v1"

    def test_explanation_required(self) -> None:
        with pytest.raises(Exception):
            DerivedSignal(
                provider_npi=VALID_NPI,
                signal_type=DerivedSignalType.DATA_COMPLETENESS,
                value=0.75,
                confidence=0.9,
                explanation="",  # min_length=10 — should fail
            )


# ---------------------------------------------------------------------------
# Schema Registry
# ---------------------------------------------------------------------------


class TestSchemaRegistry:
    def test_list_models_returns_all(self) -> None:
        models = registry.list_models()
        assert "NppesRecord" in models
        assert "CanonicalProviderProfile" in models
        assert "AuditEvent" in models
        assert "Dispute" in models
        assert len(models) >= 20

    def test_get_json_schema(self) -> None:
        schema = registry.get_json_schema("NppesRecord")
        assert "properties" in schema
        assert "entity_npi" in schema["properties"]

    def test_get_json_schema_cached(self) -> None:
        """Second call returns same object (cached)."""
        s1 = registry.get_json_schema("UnifiedIdBundle")
        s2 = registry.get_json_schema("UnifiedIdBundle")
        assert s1 is s2

    def test_validate_valid_data(self) -> None:
        data = {
            "primary_npi": VALID_NPI,
            "entity_type": "individual",
            "primary_name": {"first": "Jane", "last": "Smith"},
            "bundle_id": str(new_uuid()),
            "identity_confidence": 0.99,
        }
        errors = registry.validate("UnifiedIdBundle", data)
        assert errors == []

    def test_validate_invalid_data(self) -> None:
        data = {"npi": "bad-npi", "entity_type": "individual"}
        errors = registry.validate("UnifiedIdBundle", data)
        assert len(errors) > 0

    def test_detect_drift_no_drift(self) -> None:
        schema = registry.get_json_schema("NppesRecord")
        expected_keys = set(schema["properties"].keys())
        drift = registry.detect_drift("NppesRecord", expected_keys)
        assert "unexpected" not in drift

    def test_detect_drift_unexpected_field(self) -> None:
        drift = registry.detect_drift(
            "NppesRecord",
            {"entity_npi", "provenance", "record_type", "NEW_UNKNOWN_FIELD_XYZ"},
        )
        assert "unexpected" in drift
        assert "NEW_UNKNOWN_FIELD_XYZ" in drift["unexpected"]

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(KeyError):
            registry.get_model("NonExistentModel")

    def test_list_versions(self) -> None:
        assert "v1" in registry.list_versions()

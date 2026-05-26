"""
_fixtures.py -- Test helpers for Phase 2-H report generation tests.

Fully self-contained: no imports from other test packages.
Builds CanonicalProviderProfile instances with various license, exclusion,
disciplinary, and education configurations for test coverage.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from schema.v1.common import (
    Address,
    EntityType,
    Gender,
    LicenseStatus,
    ProviderName,
    SourceCategory,
    TaxonomyCode,
)
from schema.v1.profile import (
    CanonicalProviderProfile,
    DerivedSignalSummary,
    DisciplinaryAction,
    ExclusionRecord,
    LicenseRecord,
    SourceCoverage,
)

# ---------------------------------------------------------------------------
# Constants (mirrors search/_fixtures.py for consistency)
# ---------------------------------------------------------------------------

NPI_ALICE = "1234567890"
NPI_ORG = "1111111111"
NPI_NO_ADDRESS = "2222222222"
NPI_LICENSED = "3333333333"
NPI_DISCIPLINED = "4444444444"
NPI_EDUCATION = "5555555555"
NPI_PARTIAL = "6666666666"

BUNDLE_ALICE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BUNDLE_ORG = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
BUNDLE_NO_ADDR = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
BUNDLE_LICENSED = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
BUNDLE_DISCIPLINED = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
BUNDLE_EDUCATION = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
BUNDLE_PARTIAL = UUID("11111111-1111-1111-1111-111111111111")

FIXED_DT = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_address(
    city: str = "Anytown",
    state: str = "CA",
    postal_code: str = "90001",
) -> Address:
    return Address(
        street_line_1="100 Main St",
        city=city,
        state=state,
        postal_code=postal_code,
    )


def make_taxonomy(
    code: str = "207Q00000X",
    description: str = "Family Medicine",
    primary: bool = True,
) -> TaxonomyCode:
    return TaxonomyCode(code=code, description=description, primary=primary)


def make_signal(
    signal_type: str,
    value: float,
    confidence: float = 0.9,
    explanation: str = "test signal",
) -> DerivedSignalSummary:
    return DerivedSignalSummary(
        signal_type=signal_type,
        value=value,
        confidence=confidence,
        explanation=explanation,
        computed_at=FIXED_DT,
    )


def make_license_record(
    state: str = "CA",
    status: LicenseStatus = LicenseStatus.ACTIVE,
    license_number: str = "G12345",
    source_id: str = "S1",
) -> LicenseRecord:
    return LicenseRecord(
        state=state,
        board_name=f"{state} Medical Board",
        license_number=license_number,
        license_type="MD",
        status=status,
        issue_date=date(2015, 1, 1),
        expiration_date=date(2027, 12, 31),
        as_of_date=FIXED_DT.date(),
        source_id=source_id,
    )


def make_disciplinary_action(
    state: str = "CA",
    action_type: str = "Probation",
    is_active: bool = True,
    case_number: str = "CASE-001",
    source_id: str = "S1",
) -> DisciplinaryAction:
    return DisciplinaryAction(
        state=state,
        board_name=f"{state} Medical Board",
        action_type=action_type,
        effective_date=date(2023, 6, 1),
        is_active=is_active,
        basis="Inadequate record keeping",
        case_number=case_number,
        source_id=source_id,
    )


def make_exclusion_record(
    source_registry: str = "OIG LEIE",
    exclusion_type: str = "Mandatory",
    is_active: bool = True,
    source_id: str = "F2",
) -> ExclusionRecord:
    return ExclusionRecord(
        source_registry=source_registry,
        exclusion_type=exclusion_type,
        exclusion_date=date(2022, 3, 15),
        reinstatement_date=None if is_active else date(2024, 3, 15),
        is_active=is_active,
        source_id=source_id,
    )


# ---------------------------------------------------------------------------
# Profile factories
# ---------------------------------------------------------------------------


def make_minimal_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith"),
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_full_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(
            first="Alice",
            last="Smith",
            middle="J",
            credentials="MD",
        ),
        name_variants=[
            ProviderName(first="Alice", last="Smith-Johnson"),
            ProviderName(first="A", last="Smith"),
        ],
        gender=Gender.FEMALE,
        primary_specialty=make_taxonomy("207Q00000X", "Family Medicine"),
        all_specialties=[
            make_taxonomy("207Q00000X", "Family Medicine", primary=True),
            make_taxonomy("2084P0800X", "Psychiatry", primary=False),
        ],
        practice_addresses=[
            make_address("Los Angeles", "CA", "90001"),
            make_address("San Francisco", "CA", "94105"),
            make_address("Portland", "OR", "97201"),
        ],
        active_license_count=2,
        license_states=["CA", "OR"],
        currently_excluded=False,
        has_active_discipline=False,
        source_coverage=[
            SourceCoverage(
                category=SourceCategory.FEDERAL,
                sources_attempted=["F1", "F2"],
                sources_succeeded=["F1", "F2"],
                coverage_confidence=0.95,
            ),
        ],
        derived_signals=[
            make_signal("identity_confidence", 0.98),
            make_signal("exclusion_flag", 0.0),
            make_signal("data_completeness", 0.75),
        ],
        overall_confidence=0.98,
        report_completeness_score=0.75,
        is_partial=False,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_org_profile(npi: str = NPI_ORG) -> CanonicalProviderProfile:
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_ORG,
        entity_type=EntityType.ORGANIZATION,
        primary_name=ProviderName(first="Acme", last="Medical Group"),
        organization_name="Acme Medical Group LLC",
        practice_addresses=[make_address("Chicago", "IL", "60601")],
        active_license_count=0,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_no_address_profile(npi: str = NPI_NO_ADDRESS) -> CanonicalProviderProfile:
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_NO_ADDR,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Bob", last="Jones"),
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_licensed_profile() -> CanonicalProviderProfile:
    """Provider with 2 active licenses (CA and OR) and one inactive (WA)."""
    return CanonicalProviderProfile(
        npi=NPI_LICENSED,
        bundle_id=BUNDLE_LICENSED,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Carol", last="Davis", credentials="DO"),
        gender=Gender.FEMALE,
        primary_specialty=make_taxonomy("207Q00000X", "Family Medicine"),
        practice_addresses=[make_address("Sacramento", "CA", "95814")],
        licenses=[
            make_license_record("CA", LicenseStatus.ACTIVE, "CA99001", "S1"),
            make_license_record("OR", LicenseStatus.ACTIVE, "OR55001", "S2"),
            make_license_record("WA", LicenseStatus.INACTIVE, "WA12345", "S3"),
        ],
        active_license_count=2,
        license_states=["CA", "OR", "WA"],
        currently_excluded=False,
        has_active_discipline=False,
        is_partial=False,
        overall_confidence=0.95,
        report_completeness_score=0.80,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_disciplined_profile() -> CanonicalProviderProfile:
    """Provider with active disciplinary action and a revoked license."""
    return CanonicalProviderProfile(
        npi=NPI_DISCIPLINED,
        bundle_id=BUNDLE_DISCIPLINED,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="David", last="Evans", credentials="MD"),
        gender=Gender.MALE,
        practice_addresses=[make_address("Miami", "FL", "33101")],
        licenses=[
            make_license_record("FL", LicenseStatus.REVOKED, "FL88001", "S4"),
        ],
        active_license_count=0,
        license_states=["FL"],
        disciplinary_actions=[
            make_disciplinary_action("FL", "License Revocation", True, "FL-2023-001", "S4"),
            make_disciplinary_action("FL", "Fine", False, "FL-2019-005", "S4"),
        ],
        has_active_discipline=True,
        currently_excluded=False,
        is_partial=False,
        overall_confidence=0.97,
        report_completeness_score=0.70,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_education_profile() -> CanonicalProviderProfile:
    """Provider with medical school and graduation year."""
    return CanonicalProviderProfile(
        npi=NPI_EDUCATION,
        bundle_id=BUNDLE_EDUCATION,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Ellen", last="Foster", credentials="MD, PhD"),
        medical_school="Johns Hopkins University School of Medicine",
        graduation_year=2005,
        practice_addresses=[make_address("Baltimore", "MD", "21201")],
        currently_excluded=False,
        has_active_discipline=False,
        is_partial=False,
        overall_confidence=0.90,
        report_completeness_score=0.65,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_partial_profile() -> CanonicalProviderProfile:
    """Partial profile (sources still in progress)."""
    return CanonicalProviderProfile(
        npi=NPI_PARTIAL,
        bundle_id=BUNDLE_PARTIAL,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Frank", last="Grant"),
        is_partial=True,
        sources_attempted=["F1", "F2", "F3"],
        sources_succeeded=["F1"],
        sources_failed=["F2", "F3"],
        overall_confidence=0.50,
        report_completeness_score=0.30,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_excluded_active_profile() -> CanonicalProviderProfile:
    """Provider with active OIG LEIE + SAM.gov exclusions."""
    return CanonicalProviderProfile(
        npi=NPI_ALICE,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="George", last="Harris", credentials="MD"),
        currently_excluded=True,
        exclusions=[
            make_exclusion_record("OIG LEIE", "Mandatory", True, "F2"),
            make_exclusion_record("SAM.gov", "Excluded", True, "F3"),
        ],
        has_active_discipline=False,
        is_partial=False,
        overall_confidence=0.99,
        report_completeness_score=0.60,
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_medicare_opted_out_profile() -> CanonicalProviderProfile:
    """Provider who opted out of Medicare."""
    profile = make_full_profile()
    return profile.model_copy(update={
        "accepts_medicare": False,
        "opted_out_of_medicare": True,
        "accepts_medicaid": None,
    })

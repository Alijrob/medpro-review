"""
_fixtures.py -- Shared test helpers for Phase 2-G Provider Search tests.

Builds minimal CanonicalProviderProfile instances without going through
the full connector + normalizer + identity + entity_linker stack.
All records are deterministic (fixed UUIDs and timestamps via seed strings).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from schema.v1.common import (
    Address,
    ConfidenceScore,
    EntityType,
    Gender,
    MedproBaseModel,
    ProviderName,
    SourceCategory,
    TaxonomyCode,
    utc_now,
)
from schema.v1.profile import (
    CanonicalProviderProfile,
    DerivedSignalSummary,
    ExclusionRecord,
    HospitalAffiliation,
    LicenseRecord,
    SourceCoverage,
)
from schema.v1.common import LicenseStatus

# ---------------------------------------------------------------------------
# Test NPI constants
# ---------------------------------------------------------------------------

NPI_ALICE = "1234567890"
NPI_ORG = "1111111111"
NPI_NO_ADDRESS = "2222222222"

# Fixed bundle IDs for deterministic tests
BUNDLE_ALICE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
BUNDLE_ORG = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
BUNDLE_NO_ADDR = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

FIXED_DT = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Address helpers
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


# ---------------------------------------------------------------------------
# Taxonomy code helpers
# ---------------------------------------------------------------------------


def make_taxonomy(
    code: str = "207Q00000X",
    description: str = "Family Medicine",
    primary: bool = True,
) -> TaxonomyCode:
    return TaxonomyCode(code=code, description=description, primary=primary)


# ---------------------------------------------------------------------------
# Derived signal helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Core profile factory
# ---------------------------------------------------------------------------


def make_minimal_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    """
    Minimal valid CanonicalProviderProfile -- individual provider, no optional
    fields set beyond what's required by the schema.
    """
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith"),
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )


def make_full_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    """
    Full CanonicalProviderProfile with addresses, specialty, signals,
    exclusion, license, and source coverage -- suitable for document
    builder tests.
    """
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


def make_excluded_profile(npi: str = NPI_ALICE) -> CanonicalProviderProfile:
    """Profile with an active OIG exclusion."""
    profile = make_full_profile(npi)
    return profile.model_copy(
        update={
            "currently_excluded": True,
            "exclusions": [
                ExclusionRecord(
                    source_registry="OIG LEIE",
                    exclusion_type="Mandatory",
                    exclusion_date=FIXED_DT.date(),
                    is_active=True,
                    source_id="F2",
                )
            ],
        }
    )


def make_org_profile(npi: str = NPI_ORG) -> CanonicalProviderProfile:
    """Organization (not individual) profile."""
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
    """Profile with no practice addresses."""
    return CanonicalProviderProfile(
        npi=npi,
        bundle_id=BUNDLE_NO_ADDR,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Bob", last="Jones"),
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )

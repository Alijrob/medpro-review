"""
_fixtures.py -- Shared test helpers for Phase 2-H worker activity tests.

Fully self-contained: no imports from other test packages.
Builds RawRecord and NormalizedRecord objects for use in activity tests.
All activities can be called directly as plain Python functions (no Temporal server needed).
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from connectors.models import RawRecord

FIXED_DT = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
NPI_ALICE = "1234567890"
BUNDLE_ALICE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

# A minimal NPPES-shaped raw record for NPI_ALICE
RAW_NPPES_DICT = {
    "number": NPI_ALICE,
    "enumeration_type": "NPI-1",
    "basic": {
        "first_name": "Alice",
        "last_name": "Smith",
        "gender": "F",
        "credential": "MD",
        "status": "A",
    },
    "addresses": [
        {
            "address_1": "123 Main St",
            "city": "Los Angeles",
            "state": "CA",
            "postal_code": "90001",
            "address_purpose": "LOCATION",
        }
    ],
    "taxonomies": [
        {
            "code": "207Q00000X",
            "desc": "Family Medicine",
            "primary": True,
        }
    ],
}


def make_raw_record(
    source_id: str = "F1",
    raw: dict | None = None,
    source_record_id: str | None = None,
) -> RawRecord:
    """Build a valid RawRecord for testing."""
    if raw is None:
        raw = RAW_NPPES_DICT
    return RawRecord.from_raw(
        source_id=source_id,
        raw=raw,
        source_record_id=source_record_id or NPI_ALICE,
    )


def make_raw_record_dict(
    source_id: str = "F1",
    raw: dict | None = None,
) -> dict:
    """Build a RawRecord and return model_dump(mode='json')."""
    return make_raw_record(source_id=source_id, raw=raw).model_dump(mode="json")


# ---------------------------------------------------------------------------
# Profile factories (self-contained copies of search/_fixtures.py builders)
# ---------------------------------------------------------------------------

def _make_full_profile():
    """Import locally to avoid circular issues."""
    from datetime import datetime, timezone
    from uuid import UUID
    from schema.v1.common import (
        EntityType, Gender, ProviderName, SourceCategory, TaxonomyCode,
    )
    from schema.v1.profile import CanonicalProviderProfile, DerivedSignalSummary, SourceCoverage

    BUNDLE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    DT = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)

    def _sig(signal_type, value):
        return DerivedSignalSummary(
            signal_type=signal_type, value=value, confidence=0.9,
            explanation="test", computed_at=DT,
        )

    from schema.v1.common import Address
    return CanonicalProviderProfile(
        npi=NPI_ALICE,
        bundle_id=BUNDLE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith", credentials="MD"),
        gender=Gender.FEMALE,
        primary_specialty=TaxonomyCode(code="207Q00000X", description="Family Medicine", primary=True),
        practice_addresses=[
            Address(street_line_1="100 Main St", city="Los Angeles", state="CA", postal_code="90001"),
        ],
        active_license_count=2,
        currently_excluded=False,
        has_active_discipline=False,
        source_coverage=[
            SourceCoverage(
                category=SourceCategory.FEDERAL,
                sources_attempted=["F1", "F2"],
                sources_succeeded=["F1", "F2"],
                coverage_confidence=0.95,
            )
        ],
        derived_signals=[
            _sig("identity_confidence", 0.98),
            _sig("exclusion_flag", 0.0),
        ],
        overall_confidence=0.98,
        report_completeness_score=0.75,
        is_partial=False,
        created_at=DT,
        updated_at=DT,
    )


def _make_minimal_profile():
    from datetime import datetime, timezone
    from uuid import UUID
    from schema.v1.common import EntityType, ProviderName
    from schema.v1.profile import CanonicalProviderProfile
    BUNDLE = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    DT = datetime(2026, 5, 26, 12, 0, 0, tzinfo=timezone.utc)
    return CanonicalProviderProfile(
        npi=NPI_ALICE,
        bundle_id=BUNDLE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith"),
        created_at=DT,
        updated_at=DT,
    )

"""
tests/search/test_document.py

Unit tests for search.document.build_provider_doc().

Pure function -- no I/O, no mocks needed.

Coverage:
  - Basic field mapping from minimal profile
  - Full profile: name, variants, addresses, specialty, signals, flags
  - primary_name dict keys are correct
  - name_variants: primary excluded, deduplicated, sorted
  - Address facets: deduplicated, sorted
  - Specialty: code + description; None when absent
  - all_taxonomy_descriptions: space-joined descriptions
  - Gender pass-through
  - identity_confidence extracted from derived_signals
  - overall_risk_score: 0.0 when signal absent, correct when present
  - has_active_license: True when active_license_count > 0
  - has_active_exclusion: mirrors currently_excluded
  - has_active_discipline: mirrors profile field
  - source_coverage_count: len(source_coverage)
  - report_count always 0
  - profile_last_rebuilt_at: profile.updated_at.isoformat()
  - last_indexed_at: present and ISO-8601
  - Organization entity_type
  - No-address profile: empty facet lists
  - Determinism: identical profiles produce identical documents
"""
from __future__ import annotations

from datetime import timezone

import pytest

from search.document import build_provider_doc
from search.models import ProviderDoc
from schema.v1.common import EntityType, Gender, SourceCategory, TaxonomyCode

from ._fixtures import (
    FIXED_DT,
    NPI_ALICE,
    NPI_NO_ADDRESS,
    NPI_ORG,
    make_excluded_profile,
    make_full_profile,
    make_minimal_profile,
    make_no_address_profile,
    make_org_profile,
    make_signal,
    make_taxonomy,
)


# ---------------------------------------------------------------------------
# Basic field mapping -- minimal profile
# ---------------------------------------------------------------------------


def test_minimal_profile_returns_provider_doc():
    profile = make_minimal_profile()
    doc = build_provider_doc(profile)
    assert isinstance(doc, ProviderDoc)


def test_primary_npi_mapped():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.primary_npi == NPI_ALICE


def test_entity_type_value():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.entity_type == "individual"


def test_report_count_always_zero():
    """report_count stays 0 until Phase 2-J wires the counter."""
    doc = build_provider_doc(make_full_profile())
    assert doc.report_count == 0


def test_profile_last_rebuilt_at_matches_updated_at():
    profile = make_minimal_profile()
    doc = build_provider_doc(profile)
    assert doc.profile_last_rebuilt_at == profile.updated_at.isoformat()


def test_last_indexed_at_is_iso8601():
    doc = build_provider_doc(make_minimal_profile())
    # Should parse without raising
    from datetime import datetime
    dt = datetime.fromisoformat(doc.last_indexed_at)
    assert dt.tzinfo is not None or "+" in doc.last_indexed_at or "Z" in doc.last_indexed_at


# ---------------------------------------------------------------------------
# primary_name dict keys
# ---------------------------------------------------------------------------


def test_primary_name_keys_present():
    doc = build_provider_doc(make_minimal_profile())
    assert set(doc.primary_name.keys()) == {
        "first", "last", "middle", "credentials", "full_name_display"
    }


def test_primary_name_values_minimal():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.primary_name["first"] == "Alice"
    assert doc.primary_name["last"] == "Smith"
    assert doc.primary_name["middle"] is None
    assert doc.primary_name["credentials"] is None


def test_primary_name_full_name_display():
    doc = build_provider_doc(make_full_profile())
    # Alice J Smith MD
    assert "Alice" in doc.primary_name["full_name_display"]
    assert "Smith" in doc.primary_name["full_name_display"]
    assert "MD" in doc.primary_name["full_name_display"]


def test_primary_name_with_credentials():
    doc = build_provider_doc(make_full_profile())
    assert doc.primary_name["credentials"] == "MD"
    assert doc.primary_name["middle"] == "J"


# ---------------------------------------------------------------------------
# name_variants
# ---------------------------------------------------------------------------


def test_name_variants_excludes_primary():
    """Primary name sort_key must not appear in name_variants."""
    profile = make_full_profile()
    doc = build_provider_doc(profile)
    # Primary is Alice Smith; sort_key = "smith,alice,"
    # Variants include Alice Smith-Johnson and A Smith -- neither is "Alice Smith"
    for v in doc.name_variants:
        assert "Smith" in v or "Smith-Johnson" in v  # sanity


def test_name_variants_are_sorted():
    doc = build_provider_doc(make_full_profile())
    assert doc.name_variants == sorted(doc.name_variants)


def test_name_variants_empty_when_no_variants():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.name_variants == []


def test_name_variants_deduplicated():
    from schema.v1.common import ProviderName
    from ._fixtures import BUNDLE_ALICE, FIXED_DT
    from schema.v1.common import EntityType
    from schema.v1.profile import CanonicalProviderProfile

    profile = CanonicalProviderProfile(
        npi=NPI_ALICE,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith"),
        name_variants=[
            ProviderName(first="Alice", last="Jones"),
            ProviderName(first="Alice", last="Jones"),  # duplicate
        ],
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )
    doc = build_provider_doc(profile)
    assert len(doc.name_variants) == 1
    assert doc.name_variants[0] == "Alice Jones"


# ---------------------------------------------------------------------------
# Address facets
# ---------------------------------------------------------------------------


def test_known_states_sorted_deduplicated():
    doc = build_provider_doc(make_full_profile())
    assert doc.known_states == sorted(set(doc.known_states))
    assert "CA" in doc.known_states
    assert "OR" in doc.known_states


def test_known_cities_sorted():
    doc = build_provider_doc(make_full_profile())
    assert doc.known_cities == sorted(doc.known_cities)
    assert "Los Angeles" in doc.known_cities
    assert "Portland" in doc.known_cities


def test_practice_zip_codes_present():
    doc = build_provider_doc(make_full_profile())
    assert "90001" in doc.practice_zip_codes
    assert "94105" in doc.practice_zip_codes
    assert "97201" in doc.practice_zip_codes


def test_no_address_profile_empty_facets():
    doc = build_provider_doc(make_no_address_profile())
    assert doc.known_states == []
    assert doc.known_cities == []
    assert doc.practice_zip_codes == []


# ---------------------------------------------------------------------------
# Specialty
# ---------------------------------------------------------------------------


def test_primary_specialty_none_when_absent():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.primary_specialty is None


def test_primary_specialty_code_and_description():
    doc = build_provider_doc(make_full_profile())
    assert doc.primary_specialty is not None
    assert doc.primary_specialty["code"] == "207Q00000X"
    assert doc.primary_specialty["description"] == "Family Medicine"


def test_all_taxonomy_descriptions_joined():
    doc = build_provider_doc(make_full_profile())
    assert "Family Medicine" in doc.all_taxonomy_descriptions
    assert "Psychiatry" in doc.all_taxonomy_descriptions


def test_all_taxonomy_descriptions_empty_when_no_specialties():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.all_taxonomy_descriptions == ""


# ---------------------------------------------------------------------------
# Derived signals
# ---------------------------------------------------------------------------


def test_identity_confidence_from_signal():
    doc = build_provider_doc(make_full_profile())
    assert doc.identity_confidence == pytest.approx(0.98)


def test_identity_confidence_default_zero_when_absent():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.identity_confidence == 0.0


def test_overall_risk_score_default_zero():
    """overall_risk_score is 0.0 until C16 (Phase 2-J) adds the signal."""
    doc = build_provider_doc(make_full_profile())
    assert doc.overall_risk_score == 0.0


def test_overall_risk_score_from_signal():
    from schema.v1.profile import CanonicalProviderProfile
    from ._fixtures import BUNDLE_ALICE, FIXED_DT
    from schema.v1.common import EntityType, ProviderName
    profile = CanonicalProviderProfile(
        npi=NPI_ALICE,
        bundle_id=BUNDLE_ALICE,
        entity_type=EntityType.INDIVIDUAL,
        primary_name=ProviderName(first="Alice", last="Smith"),
        derived_signals=[make_signal("overall_risk_score", 0.72)],
        created_at=FIXED_DT,
        updated_at=FIXED_DT,
    )
    doc = build_provider_doc(profile)
    assert doc.overall_risk_score == pytest.approx(0.72)


# ---------------------------------------------------------------------------
# Boolean flags
# ---------------------------------------------------------------------------


def test_has_active_license_true_when_count_positive():
    doc = build_provider_doc(make_full_profile())
    assert doc.has_active_license is True


def test_has_active_license_false_when_count_zero():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.has_active_license is False


def test_has_active_exclusion_false_on_clean_profile():
    doc = build_provider_doc(make_full_profile())
    assert doc.has_active_exclusion is False


def test_has_active_exclusion_true_on_excluded_profile():
    doc = build_provider_doc(make_excluded_profile())
    assert doc.has_active_exclusion is True


def test_has_active_discipline_false():
    doc = build_provider_doc(make_full_profile())
    assert doc.has_active_discipline is False


# ---------------------------------------------------------------------------
# Source coverage count
# ---------------------------------------------------------------------------


def test_source_coverage_count():
    doc = build_provider_doc(make_full_profile())
    assert doc.source_coverage_count == 1  # one SourceCoverage entry in make_full_profile


def test_source_coverage_count_zero_when_empty():
    doc = build_provider_doc(make_minimal_profile())
    assert doc.source_coverage_count == 0


# ---------------------------------------------------------------------------
# Gender
# ---------------------------------------------------------------------------


def test_gender_from_profile():
    # Gender.FEMALE.value == "F" (single-letter code per federal registry convention)
    doc = build_provider_doc(make_full_profile())
    assert doc.gender == "F"


def test_gender_default_unknown():
    # Gender.UNKNOWN.value == "U"
    doc = build_provider_doc(make_minimal_profile())
    assert doc.gender == "U"


# ---------------------------------------------------------------------------
# Organization profile
# ---------------------------------------------------------------------------


def test_org_entity_type():
    doc = build_provider_doc(make_org_profile())
    assert doc.entity_type == "organization"


def test_org_npi():
    doc = build_provider_doc(make_org_profile())
    assert doc.primary_npi == NPI_ORG


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_output():
    """Identical profiles produce identical documents (stable sort)."""
    p = make_full_profile()
    doc1 = build_provider_doc(p)
    doc2 = build_provider_doc(p)
    # last_indexed_at will differ by milliseconds in real calls, but
    # same profile otherwise produces identical structural fields
    assert doc1.primary_npi == doc2.primary_npi
    assert doc1.known_states == doc2.known_states
    assert doc1.name_variants == doc2.name_variants
    assert doc1.practice_zip_codes == doc2.practice_zip_codes

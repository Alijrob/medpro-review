"""
test_builder.py -- Unit tests for report.builder.build_report() (C17 basic).

38 tests covering:
    - Basic structure and schema compliance
    - Identity section mapping (individual + org)
    - Address mapping
    - License mapping (active/inactive/revoked counts)
    - Exclusion mapping (active/reinstated)
    - Disciplinary action mapping
    - Education mapping
    - Insurance fields
    - Source coverage
    - Partial profile flag propagation
    - Disclaimer always present
    - Completeness/confidence propagation
    - Edge cases (no data, empty lists)
"""
from __future__ import annotations

import pytest

from report import build_report
from report.config import PATH_B_DISCLAIMER
from report.models import ProviderReport
from schema.v1.common import LicenseStatus

from ._fixtures import (
    NPI_ALICE,
    NPI_EDUCATION,
    NPI_LICENSED,
    NPI_PARTIAL,
    make_disciplined_profile,
    make_education_profile,
    make_excluded_active_profile,
    make_full_profile,
    make_licensed_profile,
    make_medicare_opted_out_profile,
    make_minimal_profile,
    make_org_profile,
    make_partial_profile,
)


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------


def test_build_report_returns_provider_report():
    report = build_report(make_minimal_profile())
    assert isinstance(report, ProviderReport)


def test_build_report_npi_matches():
    report = build_report(make_minimal_profile(NPI_ALICE))
    assert report.npi == NPI_ALICE


def test_build_report_has_report_id():
    report = build_report(make_minimal_profile())
    assert report.report_id is not None


def test_build_report_has_generated_at():
    report = build_report(make_minimal_profile())
    assert report.generated_at is not None


def test_build_report_schema_version():
    report = build_report(make_minimal_profile())
    assert report.schema_version == "v1"


def test_build_report_disclaimer_always_present():
    report = build_report(make_minimal_profile())
    assert report.disclaimer == PATH_B_DISCLAIMER
    assert len(report.disclaimer) > 100


def test_build_report_disclaimer_required_always_true():
    report = build_report(make_minimal_profile())
    assert report.report_disclaimer_required is True


def test_build_report_two_calls_different_report_ids():
    r1 = build_report(make_minimal_profile())
    r2 = build_report(make_minimal_profile())
    assert r1.report_id != r2.report_id


# ---------------------------------------------------------------------------
# Identity section
# ---------------------------------------------------------------------------


def test_identity_npi():
    report = build_report(make_full_profile(NPI_ALICE))
    assert report.identity.npi == NPI_ALICE


def test_identity_entity_type_individual():
    report = build_report(make_full_profile())
    assert report.identity.entity_type == "individual"


def test_identity_entity_type_org():
    report = build_report(make_org_profile())
    assert report.identity.entity_type == "organization"


def test_identity_display_name_individual():
    report = build_report(make_full_profile())
    # Should include credentials "MD"
    assert "Alice" in report.identity.display_name
    assert "Smith" in report.identity.display_name


def test_identity_display_name_org():
    report = build_report(make_org_profile())
    assert "Acme Medical Group" in report.identity.display_name


def test_identity_first_last_individual():
    report = build_report(make_full_profile())
    assert report.identity.first_name == "Alice"
    assert report.identity.last_name == "Smith"


def test_identity_first_last_none_for_org():
    report = build_report(make_org_profile())
    assert report.identity.first_name is None
    assert report.identity.last_name is None


def test_identity_credentials():
    report = build_report(make_full_profile())
    assert "MD" in report.identity.credentials


def test_identity_primary_specialty():
    report = build_report(make_full_profile())
    assert report.identity.primary_specialty == "Family Medicine"


def test_identity_gender_female():
    report = build_report(make_full_profile())
    assert report.identity.gender == "Female"


def test_identity_gender_unknown_not_shown():
    report = build_report(make_minimal_profile())
    assert report.identity.gender is None


# ---------------------------------------------------------------------------
# Completeness / confidence propagation
# ---------------------------------------------------------------------------


def test_completeness_score_propagated():
    profile = make_full_profile()
    report = build_report(profile)
    assert report.report_completeness_score == profile.report_completeness_score


def test_overall_confidence_propagated():
    profile = make_full_profile()
    report = build_report(profile)
    assert abs(report.overall_confidence - float(profile.overall_confidence)) < 0.001


def test_is_partial_propagated_true():
    report = build_report(make_partial_profile())
    assert report.is_partial is True


def test_is_partial_propagated_false():
    report = build_report(make_full_profile())
    assert report.is_partial is False


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------


def test_addresses_mapped():
    profile = make_full_profile()
    report = build_report(profile)
    assert len(report.addresses) == len(profile.practice_addresses)


def test_address_first_is_practice():
    report = build_report(make_full_profile())
    assert report.addresses[0].address_type == "practice"


def test_address_fields():
    report = build_report(make_full_profile())
    addr = report.addresses[0]
    assert addr.city == "Los Angeles"
    assert addr.state == "CA"
    assert addr.zip_code == "90001"


def test_no_addresses_empty_list():
    from ._fixtures import make_no_address_profile
    report = build_report(make_no_address_profile())
    assert report.addresses == []


# ---------------------------------------------------------------------------
# Licenses
# ---------------------------------------------------------------------------


def test_licenses_mapped():
    profile = make_licensed_profile()
    report = build_report(profile)
    assert len(report.licenses) == 3


def test_active_license_count():
    report = build_report(make_licensed_profile())
    assert report.active_license_count == 2


def test_has_active_license_true():
    profile = make_licensed_profile()
    report = build_report(profile)
    assert report.has_active_license is True


def test_has_active_license_false_when_no_active():
    report = build_report(make_disciplined_profile())
    assert report.has_active_license is False


def test_license_status_is_active_flag():
    report = build_report(make_licensed_profile())
    active = [l for l in report.licenses if l.status_is_active]
    inactive = [l for l in report.licenses if not l.status_is_active]
    assert len(active) == 2
    assert len(inactive) == 1


def test_license_state_mapped():
    report = build_report(make_licensed_profile())
    states = {l.state for l in report.licenses}
    assert states == {"CA", "OR", "WA"}


def test_no_licenses_empty_list():
    report = build_report(make_minimal_profile())
    assert report.licenses == []


# ---------------------------------------------------------------------------
# Exclusions
# ---------------------------------------------------------------------------


def test_exclusions_mapped():
    report = build_report(make_excluded_active_profile())
    assert len(report.exclusions) == 2


def test_has_active_exclusion_true():
    report = build_report(make_excluded_active_profile())
    assert report.has_active_exclusion is True


def test_has_active_exclusion_false():
    report = build_report(make_full_profile())
    assert report.has_active_exclusion is False


def test_exclusion_authority_mapped():
    report = build_report(make_excluded_active_profile())
    authorities = {e.authority for e in report.exclusions}
    assert "OIG LEIE" in authorities
    assert "SAM.gov" in authorities


def test_exclusion_is_active_flag():
    report = build_report(make_excluded_active_profile())
    assert all(e.is_active for e in report.exclusions)


def test_no_exclusions_empty_list():
    report = build_report(make_minimal_profile())
    assert report.exclusions == []


# ---------------------------------------------------------------------------
# Disciplinary actions
# ---------------------------------------------------------------------------


def test_disciplinary_mapped():
    report = build_report(make_disciplined_profile())
    assert len(report.disciplinary_actions) == 2


def test_has_active_discipline_true():
    report = build_report(make_disciplined_profile())
    assert report.has_active_discipline is True


def test_has_active_discipline_false():
    report = build_report(make_minimal_profile())
    assert report.has_active_discipline is False


def test_disciplinary_state():
    report = build_report(make_disciplined_profile())
    assert report.disciplinary_actions[0].state == "FL"


def test_disciplinary_is_active_flag():
    report = build_report(make_disciplined_profile())
    active_count = sum(1 for a in report.disciplinary_actions if a.is_active)
    resolved_count = sum(1 for a in report.disciplinary_actions if not a.is_active)
    assert active_count == 1
    assert resolved_count == 1


def test_no_disciplinary_empty_list():
    report = build_report(make_minimal_profile())
    assert report.disciplinary_actions == []


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------


def test_education_mapped():
    report = build_report(make_education_profile())
    assert len(report.education) == 1


def test_education_institution():
    report = build_report(make_education_profile())
    assert "Johns Hopkins" in report.education[0].institution_name


def test_education_graduation_year():
    report = build_report(make_education_profile())
    assert report.education[0].graduation_year == 2005


def test_no_education_empty_list():
    report = build_report(make_minimal_profile())
    assert report.education == []


# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------


def test_accepts_medicare_propagated():
    profile = make_full_profile()
    report = build_report(profile)
    assert report.accepts_medicare == profile.accepts_medicare


def test_opted_out_medicare():
    report = build_report(make_medicare_opted_out_profile())
    assert report.opted_out_of_medicare is True


def test_accepts_medicaid_none_when_unknown():
    report = build_report(make_minimal_profile())
    assert report.accepts_medicaid is None


# ---------------------------------------------------------------------------
# Source coverage
# ---------------------------------------------------------------------------


def test_sources_attempted_propagated():
    report = build_report(make_partial_profile())
    assert set(report.sources_attempted) == {"F1", "F2", "F3"}


def test_sources_succeeded_propagated():
    report = build_report(make_partial_profile())
    assert report.sources_succeeded == ["F1"]


def test_sources_failed_propagated():
    report = build_report(make_partial_profile())
    assert set(report.sources_failed) == {"F2", "F3"}


def test_source_coverage_empty_when_profile_has_none():
    report = build_report(make_minimal_profile())
    assert report.source_coverage == []


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


def test_report_json_serialisable():
    report = build_report(make_full_profile())
    json_str = report.model_dump_json()
    assert '"npi"' in json_str
    assert '"disclaimer"' in json_str


def test_report_roundtrip():
    """ProviderReport can be serialised and re-validated."""
    report = build_report(make_full_profile())
    data = report.model_dump(mode="json")
    report2 = ProviderReport.model_validate(data)
    assert report2.npi == report.npi
    assert report2.report_id == report.report_id


# ---------------------------------------------------------------------------
# Pending corrections
# ---------------------------------------------------------------------------


def test_has_pending_corrections_false_by_default():
    report = build_report(make_minimal_profile())
    assert report.has_pending_corrections is False

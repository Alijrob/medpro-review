"""
test_entity_linker_integration.py -- Integration tests for the Entity Linker (C13).

Tests end-to-end profile construction from realistic multi-source record sets.
These tests cross module boundaries but require no network, DB, or external state.
"""
from __future__ import annotations

import pytest
from datetime import date

from ._fixtures import (
    NPI_ALICE,
    make_bundle, make_nppes_record, make_oig_record, make_sam_record,
    make_cms_record, make_medicare_record, make_medicaid_record,
    make_pubmed_record, make_trial_record,
)
from entity_linker import EntityLinker
from schema.v1.common import EntityType, Gender


class TestFullP1Bundle:
    """A provider with all 8 P1 P1 source records should produce a complete profile."""

    def setup_method(self):
        self.bundle = make_bundle(
            contributing_sources=["F1", "F2", "F3", "F4", "I1", "I2", "A1", "A2"],
            confidence=0.980,
        )
        self.records = [
            make_nppes_record(),
            make_oig_record(active=False),      # historical -- not active
            make_sam_record(active=False),       # historical -- not active
            make_cms_record(),
            make_medicare_record(indicator="Y"),
            make_medicaid_record(),
            make_pubmed_record(pmid="11111111", year=2023, suffix="int"),
            make_trial_record(),
        ]
        self.result = EntityLinker().build_profile(self.bundle, self.records)

    def test_completeness_is_1(self):
        assert self.result.profile.report_completeness_score == pytest.approx(1.0, abs=1e-4)

    def test_not_partial(self):
        assert self.result.profile.is_partial is False

    def test_no_active_exclusions(self):
        assert self.result.profile.currently_excluded is False
        assert len(self.result.profile.exclusions) == 2  # 1 OIG + 1 SAM (both historical)

    def test_accepts_medicare_true(self):
        assert self.result.profile.accepts_medicare is True

    def test_accepts_medicaid_true(self):
        assert self.result.profile.accepts_medicaid is True

    def test_publication_and_trial_counts(self):
        assert self.result.profile.publication_count == 1
        assert self.result.profile.clinical_trial_count == 1

    def test_specialty_group_in_result(self):
        # Taxonomy code 207Q00000X maps to "Family Medicine"
        assert self.result.specialty_group == "Family Medicine"

    def test_four_derived_signals(self):
        assert len(self.result.profile.derived_signals) == 4

    def test_identity_confidence_signal_matches_bundle(self):
        sig = next(
            s for s in self.result.profile.derived_signals
            if s.signal_type == "identity_confidence"
        )
        assert sig.value == pytest.approx(0.980, abs=1e-4)

    def test_source_coverage_built(self):
        assert len(self.result.profile.source_coverage) > 0
        categories = {c.category.value for c in self.result.profile.source_coverage}
        assert "federal" in categories
        assert "academic" in categories

    def test_specialty_classification_signal_value_1(self):
        sig = next(
            s for s in self.result.profile.derived_signals
            if s.signal_type == "specialty_classification"
        )
        assert sig.value == 1.0
        assert "Family Medicine" in sig.explanation


class TestActiveExclusionPropagation:
    """When a provider has an active exclusion, all relevant fields must reflect it."""

    def test_currently_excluded_true_propagates_to_flag_signal(self):
        bundle = make_bundle(contributing_sources=["F1", "F2"])
        records = [make_oig_record(active=True)]
        result = EntityLinker().build_profile(bundle, records)

        assert result.profile.currently_excluded is True

        flag = next(
            s for s in result.profile.derived_signals
            if s.signal_type == "exclusion_flag"
        )
        assert flag.value == 1.0
        assert "ALERT" in flag.explanation

    def test_both_oig_and_sam_active(self):
        bundle = make_bundle(contributing_sources=["F1", "F2", "F3"])
        records = [make_oig_record(active=True), make_sam_record(active=True)]
        result = EntityLinker().build_profile(bundle, records)
        assert result.profile.currently_excluded is True
        registries = {e.source_registry for e in result.profile.exclusions}
        assert "OIG LEIE" in registries
        assert "SAM.gov" in registries


class TestPublicationCap:
    """Publication cap at max_recent_publications; total count still accurate."""

    def test_publications_capped_at_10_recent(self):
        bundle = make_bundle(contributing_sources=["F1", "A1"])
        records = [
            make_pubmed_record(pmid=str(10000000 + i), year=2020, suffix=str(i))
            for i in range(15)
        ]
        result = EntityLinker().build_profile(bundle, records)
        assert result.profile.publication_count == 15
        assert len(result.profile.recent_publications) == 10

    def test_custom_max_recent_via_settings(self):
        from entity_linker import LinkerSettings
        settings = LinkerSettings(max_recent_publications=3)
        linker = EntityLinker(settings=settings)
        bundle = make_bundle(contributing_sources=["F1", "A1"])
        records = [
            make_pubmed_record(pmid=str(20000000 + i), year=2021, suffix=str(i))
            for i in range(5)
        ]
        result = linker.build_profile(bundle, records)
        assert result.profile.publication_count == 5
        assert len(result.profile.recent_publications) == 3


class TestMultiStateMedicaid:
    """Provider enrolled in Medicaid in multiple states."""

    def test_multi_state_insurance_participation(self):
        bundle = make_bundle(contributing_sources=["F1", "I2"])
        records = [
            make_medicaid_record(state="CA", status="enrolled"),
            make_medicaid_record(state="TX", status="enrolled"),
            make_medicaid_record(state="NY", status="terminated"),
        ]
        result = EntityLinker().build_profile(bundle, records)
        programs = {p.program for p in result.profile.insurance_participation}
        assert "Medicaid-CA" in programs
        assert "Medicaid-TX" in programs
        assert "Medicaid-NY" in programs
        assert result.profile.accepts_medicaid is True


class TestGenderPassthrough:
    """Gender from bundle propagates to profile; UNKNOWN is valid."""

    def test_gender_unknown_default(self):
        bundle = make_bundle(gender=Gender.UNKNOWN)
        result = EntityLinker().build_profile(bundle, [])
        assert result.profile.gender == Gender.UNKNOWN

    def test_gender_female_from_bundle(self):
        bundle = make_bundle(gender=Gender.FEMALE)
        result = EntityLinker().build_profile(bundle, [])
        assert result.profile.gender == Gender.FEMALE

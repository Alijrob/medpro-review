"""
test_signals.py -- Unit tests for entity_linker.signals (Phase 2-F, C13).

Tests each signal builder independently: exclusion_flag, identity_confidence,
specialty_classification, data_completeness.
"""
from __future__ import annotations

import pytest
from datetime import date

from ._fixtures import (
    NPI_ALICE,
    make_bundle,
    make_oig_record,
    make_oig_historical,
    make_sam_record,
)
from entity_linker.signals import (
    COMPLETENESS_WEIGHTS,
    compute_data_completeness,
    compute_derived_signals,
    compute_exclusion_flag,
    compute_identity_confidence,
    compute_specialty_classification,
)
from entity_linker.extractors import extract_oig_exclusions, extract_sam_exclusions


# ===========================================================================
# COMPLETENESS_WEIGHTS invariants
# ===========================================================================

class TestCompletenessWeights:

    def test_weights_sum_to_one(self):
        total = sum(COMPLETENESS_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9

    def test_all_keys_present(self):
        expected = {
            "identity_anchor", "exclusion_checked", "medicare_status",
            "address_present", "hospital_affiliation", "medicaid_status",
            "publications_checked", "clinical_trials_checked",
        }
        assert set(COMPLETENESS_WEIGHTS.keys()) == expected

    def test_identity_anchor_is_largest_weight(self):
        max_key = max(COMPLETENESS_WEIGHTS, key=COMPLETENESS_WEIGHTS.get)
        assert max_key == "identity_anchor"


# ===========================================================================
# exclusion_flag signal
# ===========================================================================

class TestComputeExclusionFlag:

    def test_active_oig_exclusion_gives_value_1(self):
        exclusions = extract_oig_exclusions([make_oig_record(active=True)])
        sig = compute_exclusion_flag(exclusions, ["F1", "F2"])
        assert sig.signal_type == "exclusion_flag"
        assert sig.value == 1.0
        assert sig.confidence == pytest.approx(0.95)
        assert "ALERT" in sig.explanation

    def test_historical_exclusion_gives_value_0(self):
        exclusions = extract_oig_exclusions([make_oig_historical()])
        sig = compute_exclusion_flag(exclusions, ["F1", "F2"])
        assert sig.value == 0.0
        assert sig.confidence == pytest.approx(0.95)

    def test_no_exclusions_checked_value_0_confidence_0(self):
        sig = compute_exclusion_flag([], ["F1"])  # F2/F3 not in sources
        assert sig.value == 0.0
        assert sig.confidence == 0.0

    def test_no_exclusions_both_sources_checked(self):
        sig = compute_exclusion_flag([], ["F1", "F2", "F3"])
        assert sig.value == 0.0
        assert sig.confidence == pytest.approx(0.95)
        assert "F2" in sig.contributing_sources
        assert "F3" in sig.contributing_sources

    def test_sam_exclusion_active(self):
        exclusions = extract_sam_exclusions([make_sam_record(active=True)])
        sig = compute_exclusion_flag(exclusions, ["F1", "F3"])
        assert sig.value == 1.0
        assert "SAM.gov" in sig.explanation


# ===========================================================================
# identity_confidence signal
# ===========================================================================

class TestComputeIdentityConfidence:

    def test_high_confidence_bundle(self):
        bundle = make_bundle(
            contributing_sources=["F1", "F4", "I1"],
            confidence=0.980,
        )
        sig = compute_identity_confidence(bundle)
        assert sig.signal_type == "identity_confidence"
        assert sig.value == pytest.approx(0.980, abs=1e-4)
        assert sig.confidence == pytest.approx(0.980, abs=1e-4)
        assert "high" in sig.explanation
        assert "3 contributing sources" in sig.explanation

    def test_low_confidence_bundle(self):
        bundle = make_bundle(confidence=0.750, contributing_sources=["I1"])
        sig = compute_identity_confidence(bundle)
        assert "low" in sig.explanation

    def test_contributing_sources_in_signal(self):
        bundle = make_bundle(contributing_sources=["F1", "F2"])
        sig = compute_identity_confidence(bundle)
        assert "F1" in sig.contributing_sources
        assert "F2" in sig.contributing_sources


# ===========================================================================
# specialty_classification signal
# ===========================================================================

class TestComputeSpecialtyClassification:

    def test_known_specialty_group_value_1(self):
        sig = compute_specialty_classification("Family Medicine", ["F1"])
        assert sig.signal_type == "specialty_classification"
        assert sig.value == 1.0
        assert "Family Medicine" in sig.explanation
        assert sig.confidence == pytest.approx(0.95)

    def test_unknown_specialty_value_0(self):
        sig = compute_specialty_classification(None, ["F1"])
        assert sig.value == 0.0
        assert sig.confidence == 0.0

    def test_specialty_without_f1_lower_confidence(self):
        sig = compute_specialty_classification("Internal Medicine", ["I1"])
        assert sig.value == 1.0
        assert sig.confidence == pytest.approx(0.5)


# ===========================================================================
# data_completeness signal
# ===========================================================================

class TestComputeDataCompleteness:

    def test_all_p1_sources_gives_near_full_score(self):
        sources = ["F1", "F2", "F3", "F4", "I1", "I2", "A1", "A2"]
        sig = compute_data_completeness(sources, known_address_count=1)
        assert sig.signal_type == "data_completeness"
        assert sig.value == pytest.approx(1.0, abs=1e-4)

    def test_f1_only_completeness(self):
        # F1 = identity_anchor (0.30) + address_present (0.10) = 0.40
        sig = compute_data_completeness(["F1"], known_address_count=1)
        assert sig.value == pytest.approx(0.40, abs=1e-4)

    def test_no_sources_zero_score(self):
        sig = compute_data_completeness([], known_address_count=0)
        assert sig.value == pytest.approx(0.0, abs=1e-4)

    def test_exclusion_checked_requires_f2_or_f3(self):
        # F1 + F2 = 0.30 + 0.20 = 0.50 (no address)
        sig = compute_data_completeness(["F1", "F2"], known_address_count=0)
        assert sig.value == pytest.approx(0.50, abs=1e-4)

    def test_address_count_matters(self):
        sig_with = compute_data_completeness(["F1"], known_address_count=2)
        sig_without = compute_data_completeness(["F1"], known_address_count=0)
        assert sig_with.value > sig_without.value


# ===========================================================================
# compute_derived_signals (composite builder)
# ===========================================================================

class TestComputeDerivedSignals:

    def test_returns_four_signals(self):
        bundle = make_bundle(contributing_sources=["F1"])
        signals = compute_derived_signals(
            exclusions=[],
            bundle=bundle,
            specialty_group="Family Medicine",
            known_address_count=1,
        )
        assert len(signals) == 4

    def test_signal_types_in_order(self):
        bundle = make_bundle(contributing_sources=["F1"])
        signals = compute_derived_signals(
            exclusions=[],
            bundle=bundle,
            specialty_group=None,
            known_address_count=0,
        )
        types = [s.signal_type for s in signals]
        assert types == [
            "exclusion_flag",
            "identity_confidence",
            "specialty_classification",
            "data_completeness",
        ]

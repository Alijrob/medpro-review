"""
test_identity_integration.py -- End-to-end identity resolution tests (Phase 2-E, C12).

Exercises the full P1 source pipeline: F1 seed -> corroborating merges ->
confidence target validation. Uses the same record builders as unit tests
(no network, no DB) but tests the complete resolution flow.
"""
import pytest

from identity import IdentityResolver, ResolutionAction
from schema.v1.common import EntityType

from ._fixtures import (
    NPI_ALICE,
    NPI_BOB,
    NPI_ORG,
    make_clinical_trial_record,
    make_cms_provider_record,
    make_medicaid_record,
    make_medicare_record,
    make_nppes_record,
    make_oig_record,
    make_pubmed_record,
    make_sam_record,
)


def test_f1_f4_i1_meets_architecture_precision_target():
    """
    Core architecture acceptance criterion: F1 + F4 + I1 >= 0.98 precision.

    DECISIONS.md Entry 026 / architecture-lock.md: '>98% identity precision'.
    """
    r = IdentityResolver()
    r.resolve(make_nppes_record(NPI_ALICE))
    r.resolve(make_cms_provider_record(NPI_ALICE))
    r.resolve(make_medicare_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.identity_confidence >= 0.980
    assert not bundle.human_review_required
    assert set(bundle.contributing_sources) == {"F1", "F4", "I1"}


def test_all_p1_sources_full_bundle():
    """All 8 P1 sources build a complete, near-max confidence bundle."""
    r = IdentityResolver()
    records = [
        make_nppes_record(NPI_ALICE),
        make_oig_record(NPI_ALICE),
        make_sam_record(NPI_ALICE),
        make_cms_provider_record(NPI_ALICE),
        make_medicare_record(NPI_ALICE),
        make_medicaid_record(NPI_ALICE),
        make_pubmed_record(NPI_ALICE),
        make_clinical_trial_record(NPI_ALICE),
    ]
    summary = r.resolve_batch(records)
    bundle = r.store.get(NPI_ALICE)

    assert bundle.identity_confidence >= 0.980
    assert not bundle.human_review_required
    assert set(bundle.contributing_sources) == {"F1", "F2", "F3", "F4", "I1", "I2", "A1", "A2"}
    assert summary.total_records == 8


def test_f2_first_then_f1_upgrades_bundle():
    """
    F2 (OIG LEIE) arrives before F1. The stub bundle is created, then F1
    upgrades it to full identity. The F2 name hint should be preserved as
    a name variant if it differs from the F1 name.
    """
    r = IdentityResolver()
    # F2 first: exclusion record (name "Alice Smith" from reported fields)
    r.resolve(make_oig_record(NPI_ALICE, first="Alice", last="Smith"))
    stub = r.store.get(NPI_ALICE)
    assert stub.human_review_required

    # F1 arrives with same name (Alice Smith): no variant added
    r.resolve(make_nppes_record(NPI_ALICE, first="Alice", last="Smith"))
    upgraded = r.store.get(NPI_ALICE)
    assert upgraded.primary_name.first == "Alice"
    assert upgraded.entity_type == EntityType.INDIVIDUAL
    # confidence is now F1 + F2 level
    assert upgraded.identity_confidence > stub.identity_confidence
    assert not upgraded.human_review_required


def test_two_providers_independent_bundles():
    """Records for different NPIs must produce fully independent bundles."""
    r = IdentityResolver()
    r.resolve(make_nppes_record(NPI_ALICE, first="Alice", last="Smith"))
    r.resolve(make_nppes_record(NPI_BOB, first="Bob", last="Jones"))
    r.resolve(make_medicare_record(NPI_ALICE))
    r.resolve(make_cms_provider_record(NPI_BOB))

    alice = r.store.get(NPI_ALICE)
    bob = r.store.get(NPI_BOB)

    assert alice.primary_name.first == "Alice"
    assert bob.primary_name.first == "Bob"
    assert "I1" in alice.contributing_sources
    assert "I1" not in bob.contributing_sources
    assert "F4" in bob.contributing_sources
    assert "F4" not in alice.contributing_sources
    assert len(r.store) == 2


def test_organization_npi_entity_type():
    """Organization NPI (NPI-2) gets entity_type=ORGANIZATION from F1."""
    r = IdentityResolver()
    r.resolve(make_nppes_record(NPI_ORG, first="",
                                last="Memorial Hospital",
                                entity_type=EntityType.ORGANIZATION))
    bundle = r.store.get(NPI_ORG)
    assert bundle.entity_type == EntityType.ORGANIZATION


def test_caller_npi_sources_contribute_without_confidence_boost():
    """
    F3, A1, A2 appear in contributing_sources but do not raise confidence.
    The bundle still correctly tracks these sources for downstream C13 use.
    """
    r = IdentityResolver()
    r.resolve(make_nppes_record(NPI_ALICE))
    base_confidence = r.store.get(NPI_ALICE).identity_confidence

    r.resolve(make_sam_record(NPI_ALICE))
    r.resolve(make_pubmed_record(NPI_ALICE))
    r.resolve(make_clinical_trial_record(NPI_ALICE))

    bundle = r.store.get(NPI_ALICE)
    assert bundle.identity_confidence == pytest.approx(base_confidence)
    assert "F3" in bundle.contributing_sources
    assert "A1" in bundle.contributing_sources
    assert "A2" in bundle.contributing_sources

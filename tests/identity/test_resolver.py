"""
test_resolver.py -- Unit tests for IdentityResolver (Phase 2-E, C12).

Validates bundle creation, merging, idempotency, batch ordering, and
the confidence/human-review logic at the resolver layer.
"""
import pytest

from identity import IdentityResolver, IdentityStore, ResolutionAction
from schema.v1.common import Address, EntityType, ProviderName, TaxonomyCode

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


def fresh() -> IdentityResolver:
    return IdentityResolver()


# ---------------------------------------------------------------------------
# Bundle creation from F1 (NppesRecord)
# ---------------------------------------------------------------------------

def test_create_from_nppes_action():
    r = fresh()
    result = r.resolve(make_nppes_record(NPI_ALICE))
    assert result.action == ResolutionAction.CREATED
    assert result.provider_npi == NPI_ALICE
    assert result.source_id == "F1"
    assert result.confidence_before is None


def test_create_from_nppes_populates_identity_fields():
    r = fresh()
    rec = make_nppes_record(NPI_ALICE, first="Alice", last="Smith",
                             entity_type=EntityType.INDIVIDUAL)
    r.resolve(rec)
    bundle = r.store.get(NPI_ALICE)
    assert bundle is not None
    assert bundle.primary_name.first == "Alice"
    assert bundle.primary_name.last == "Smith"
    assert bundle.entity_type == EntityType.INDIVIDUAL
    assert bundle.primary_npi == NPI_ALICE


def test_create_from_nppes_sets_addresses():
    r = fresh()
    addr = Address(street_line_1="42 Oak Ave", city="Springfield", state="IL", postal_code="62701")
    r.resolve(make_nppes_record(NPI_ALICE, addresses=[addr]))
    bundle = r.store.get(NPI_ALICE)
    assert len(bundle.known_addresses) == 1
    assert bundle.known_addresses[0].street_line_1 == "42 Oak Ave"


def test_create_from_nppes_sets_primary_taxonomy():
    r = fresh()
    tc = TaxonomyCode(code="207Q00000X", description="Family Medicine", primary=True)
    r.resolve(make_nppes_record(NPI_ALICE, taxonomy_codes=[tc]))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.primary_specialty is not None
    assert bundle.primary_specialty.code == "207Q00000X"


def test_create_from_nppes_name_variants():
    r = fresh()
    variants = [ProviderName(first="Ali", last="Smith-Jones")]
    r.resolve(make_nppes_record(NPI_ALICE, other_names=variants))
    bundle = r.store.get(NPI_ALICE)
    assert len(bundle.name_variants) == 1
    assert bundle.name_variants[0].last == "Smith-Jones"


def test_create_from_nppes_converts_other_identifiers():
    r = fresh()
    raw_ids = [{"type": "DEA", "identifier": "AS1234567", "state": "CA", "issuer": "DEA"}]
    r.resolve(make_nppes_record(NPI_ALICE, other_identifiers=raw_ids))
    bundle = r.store.get(NPI_ALICE)
    assert len(bundle.other_identifiers) == 1
    assert bundle.other_identifiers[0].identifier_type == "DEA"
    assert bundle.other_identifiers[0].identifier_value == "AS1234567"


def test_create_from_nppes_confidence_above_threshold():
    r = fresh()
    result = r.resolve(make_nppes_record(NPI_ALICE))
    assert result.confidence_after >= 0.850
    bundle = r.store.get(NPI_ALICE)
    assert not bundle.human_review_required


# ---------------------------------------------------------------------------
# Bundle creation from non-F1 records
# ---------------------------------------------------------------------------

def test_create_from_non_f1_flags_human_review():
    """Non-F1 first record: F1 not yet seen -> human_review_required = True."""
    r = fresh()
    r.resolve(make_cms_provider_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.human_review_required


def test_create_from_oig_extracts_name_hint():
    """F2 (OIG LEIE) has reported_first_name / reported_last_name -> used as name hint."""
    r = fresh()
    r.resolve(make_oig_record(NPI_ALICE, first="Alice", last="Smith"))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.primary_name.first == "Alice"
    assert bundle.primary_name.last == "Smith"


def test_create_from_caller_npi_source_uses_stub_name():
    """F3/A1/A2 carry no name info -> stub name (last=UNKNOWN)."""
    r = fresh()
    r.resolve(make_sam_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.primary_name.last == "UNKNOWN"
    assert bundle.human_review_required


def test_create_from_non_f1_defaults_entity_type_individual():
    r = fresh()
    r.resolve(make_medicare_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.entity_type == EntityType.INDIVIDUAL


# ---------------------------------------------------------------------------
# Merging records into existing bundles
# ---------------------------------------------------------------------------

def test_merge_adds_to_contributing_sources():
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    r.resolve(make_cms_provider_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert "F1" in bundle.contributing_sources
    assert "F4" in bundle.contributing_sources


def test_merge_raises_confidence_with_corroborating_source():
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    before = r.store.get(NPI_ALICE).identity_confidence
    r.resolve(make_medicare_record(NPI_ALICE))
    after = r.store.get(NPI_ALICE).identity_confidence
    assert after > before


def test_merge_f4_i1_reaches_architecture_target():
    """F1 + F4 + I1 must reach >= 0.98 (architecture acceptance criterion)."""
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    r.resolve(make_cms_provider_record(NPI_ALICE))
    r.resolve(make_medicare_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.identity_confidence >= 0.980
    assert not bundle.human_review_required


def test_merge_caller_npi_source_no_confidence_boost():
    """F3/A1/A2 do not raise identity_confidence."""
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    before = r.store.get(NPI_ALICE).identity_confidence
    r.resolve(make_sam_record(NPI_ALICE))
    after = r.store.get(NPI_ALICE).identity_confidence
    assert after == pytest.approx(before)


def test_merge_f1_into_non_f1_bundle_upgrades_identity():
    """F1 arriving after a non-F1 seed should upgrade name, entity_type, addresses."""
    r = fresh()
    r.resolve(make_cms_provider_record(NPI_ALICE))
    stub_bundle = r.store.get(NPI_ALICE)
    assert stub_bundle.human_review_required  # before F1

    r.resolve(make_nppes_record(NPI_ALICE, first="Alice", last="Smith"))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.primary_name.first == "Alice"
    assert bundle.primary_name.last == "Smith"
    assert bundle.entity_type == EntityType.INDIVIDUAL
    # confidence should now reflect F1 + F4
    assert bundle.identity_confidence > stub_bundle.identity_confidence


def test_merge_f1_clears_human_review_when_confidence_above_threshold():
    r = fresh()
    r.resolve(make_medicare_record(NPI_ALICE))
    assert r.store.get(NPI_ALICE).human_review_required

    r.resolve(make_nppes_record(NPI_ALICE))
    assert not r.store.get(NPI_ALICE).human_review_required


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_same_source_twice_is_skipped():
    """Resolving the same source_id twice returns SKIPPED on the second call."""
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    result2 = r.resolve(make_nppes_record(NPI_ALICE))
    assert result2.action == ResolutionAction.SKIPPED


def test_skipped_does_not_change_confidence():
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    bundle_before = r.store.get(NPI_ALICE)
    r.resolve(make_nppes_record(NPI_ALICE))
    bundle_after = r.store.get(NPI_ALICE)
    assert bundle_before.identity_confidence == bundle_after.identity_confidence


def test_skipped_does_not_duplicate_contributing_sources():
    r = fresh()
    r.resolve(make_nppes_record(NPI_ALICE))
    r.resolve(make_nppes_record(NPI_ALICE))
    bundle = r.store.get(NPI_ALICE)
    assert bundle.contributing_sources.count("F1") == 1


# ---------------------------------------------------------------------------
# Batch resolution
# ---------------------------------------------------------------------------

def test_resolve_batch_creates_multiple_bundles():
    r = fresh()
    records = [
        make_nppes_record(NPI_ALICE),
        make_nppes_record(NPI_BOB, first="Bob", last="Jones"),
    ]
    summary = r.resolve_batch(records)
    assert summary.created == 2
    assert summary.unique_npis == 2
    assert r.store.get(NPI_ALICE) is not None
    assert r.store.get(NPI_BOB) is not None


def test_resolve_batch_f1_processed_first():
    """
    When a non-F1 record is submitted before F1 in the batch, F1 should still
    be processed first (batch sorts F1 to front), so the resulting bundle
    has the full NPPES identity immediately.
    """
    r = fresh()
    # Deliberately put F4 first in the list
    records = [
        make_cms_provider_record(NPI_ALICE),
        make_nppes_record(NPI_ALICE, first="Alice", last="Smith"),
    ]
    summary = r.resolve_batch(records)
    bundle = r.store.get(NPI_ALICE)
    # F1 was processed first, so primary_name should be from NPPES
    assert bundle.primary_name.first == "Alice"
    assert "F1" in bundle.contributing_sources
    assert "F4" in bundle.contributing_sources


def test_resolve_batch_summary_counts():
    r = fresh()
    records = [
        make_nppes_record(NPI_ALICE),
        make_cms_provider_record(NPI_ALICE),  # merge
        make_nppes_record(NPI_ALICE),          # skip (F1 already in)
        make_nppes_record(NPI_BOB),            # create
    ]
    summary = r.resolve_batch(records)
    assert summary.created == 2     # NPI_ALICE + NPI_BOB
    assert summary.merged == 1      # F4 merge into NPI_ALICE
    assert summary.skipped == 1     # second F1 for NPI_ALICE
    assert summary.total_records == 4


def test_resolve_batch_human_review_count():
    r = fresh()
    # NPI_BOB only gets a non-F1 record -> human_review_required
    records = [
        make_nppes_record(NPI_ALICE),
        make_medicare_record(NPI_BOB),
    ]
    summary = r.resolve_batch(records)
    assert summary.bundles_requiring_review == 1

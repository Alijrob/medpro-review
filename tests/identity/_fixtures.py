"""
_fixtures.py -- Shared test helpers for Phase 2-E identity tests.

Provides factory functions for building NormalizedRecord objects without
going through the full connector + normalizer stack. All records have
entity_npi set (as guaranteed by C11 in production).

SHA-256 pattern: tests use zero-padded 64-char hex strings as fake hashes.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from schema.v1.common import (
    Address,
    DataProvenance,
    EntityType,
    ProviderName,
    SourceCategory,
    TaxonomyCode,
    utc_now,
)
from schema.v1.identity import OtherIdentifier
from schema.v1.normalized import (
    ClinicalTrialRecord,
    CmsProviderRecord,
    MedicaidEnrollmentRecord,
    MedicareEnrollmentRecord,
    NppesRecord,
    OigLeieRecord,
    PubMedRecord,
    SamExclusionRecord,
)

# ---------------------------------------------------------------------------
# Test NPI constants
# ---------------------------------------------------------------------------
NPI_ALICE = "1234567890"   # Individual physician
NPI_BOB   = "0987654321"   # Another individual physician
NPI_ORG   = "1111111111"   # Organization NPI


def _fake_hash(seed: str) -> str:
    """Deterministic 64-char SHA-256 hex string for test provenance."""
    return hashlib.sha256(seed.encode()).hexdigest()


def _provenance(source_id: str, source_name: str, category: SourceCategory,
                npi: str, suffix: str = "") -> DataProvenance:
    return DataProvenance(
        source_id=source_id,
        source_name=source_name,
        source_category=category,
        source_record_id=npi,
        ingested_at=utc_now(),
        raw_record_hash=_fake_hash(f"{source_id}:{npi}:{suffix}"),
    )


# ---------------------------------------------------------------------------
# NppesRecord (F1) builders
# ---------------------------------------------------------------------------

def make_nppes_record(
    npi: str = NPI_ALICE,
    first: str = "Alice",
    last: str = "Smith",
    entity_type: EntityType = EntityType.INDIVIDUAL,
    addresses: list[Address] | None = None,
    taxonomy_codes: list[TaxonomyCode] | None = None,
    other_names: list[ProviderName] | None = None,
    other_identifiers: list[dict[str, str]] | None = None,
) -> NppesRecord:
    prov = _provenance("F1", "NPPES NPI Registry", SourceCategory.FEDERAL, npi)
    if addresses is None:
        addresses = [_default_address()]
    if taxonomy_codes is None:
        taxonomy_codes = [_default_taxonomy()]
    return NppesRecord(
        entity_npi=npi,
        provenance=prov,
        entity_type=entity_type,
        name=ProviderName(first=first, last=last),
        other_names=other_names or [],
        addresses=addresses,
        taxonomy_codes=taxonomy_codes,
        other_identifiers=other_identifiers or [],
    )


def _default_address() -> Address:
    return Address(
        street_line_1="100 Main St",
        city="Anytown",
        state="CA",
        postal_code="90001",
    )


def _default_taxonomy() -> TaxonomyCode:
    return TaxonomyCode(
        code="207Q00000X",
        description="Family Medicine",
        primary=True,
    )


# ---------------------------------------------------------------------------
# OigLeieRecord (F2) builder
# ---------------------------------------------------------------------------

def make_oig_record(
    npi: str = NPI_ALICE,
    first: str = "Alice",
    last: str = "Smith",
) -> OigLeieRecord:
    from datetime import date
    prov = _provenance("F2", "OIG LEIE", SourceCategory.FEDERAL, npi)
    return OigLeieRecord(
        entity_npi=npi,
        provenance=prov,
        exclusion_type="1128a1",
        exclusion_date=date(2020, 1, 15),
        general_exclusion=True,
        reported_first_name=first,
        reported_last_name=last,
    )


# ---------------------------------------------------------------------------
# SamExclusionRecord (F3) builder
# ---------------------------------------------------------------------------

def make_sam_record(npi: str = NPI_ALICE) -> SamExclusionRecord:
    from datetime import date
    prov = _provenance("F3", "SAM.gov Exclusions", SourceCategory.FEDERAL, npi)
    return SamExclusionRecord(
        entity_npi=npi,
        provenance=prov,
        unique_entity_id="UEI123456",
        exclusion_type="Ineligible (Proceedings Complete)",
        active_exclusion=True,
        exclusion_date=date(2021, 6, 1),
    )


# ---------------------------------------------------------------------------
# CmsProviderRecord (F4) builder
# ---------------------------------------------------------------------------

def make_cms_provider_record(npi: str = NPI_ALICE) -> CmsProviderRecord:
    prov = _provenance("F4", "CMS Care Compare", SourceCategory.FEDERAL, npi)
    return CmsProviderRecord(
        entity_npi=npi,
        provenance=prov,
        accepts_medicare_assignment=True,
    )


# ---------------------------------------------------------------------------
# MedicareEnrollmentRecord (I1) builder
# ---------------------------------------------------------------------------

def make_medicare_record(npi: str = NPI_ALICE) -> MedicareEnrollmentRecord:
    prov = _provenance("I1", "CMS Medicare Enrollment", SourceCategory.FEDERAL, npi)
    return MedicareEnrollmentRecord(
        entity_npi=npi,
        provenance=prov,
        participation_indicator="Y",
    )


# ---------------------------------------------------------------------------
# MedicaidEnrollmentRecord (I2) builder
# ---------------------------------------------------------------------------

def make_medicaid_record(npi: str = NPI_ALICE) -> MedicaidEnrollmentRecord:
    prov = _provenance("I2", "CMS Medicaid Enrollment", SourceCategory.FEDERAL, npi)
    return MedicaidEnrollmentRecord(
        entity_npi=npi,
        provenance=prov,
        state="CA",
        enrollment_status="enrolled",
    )


# ---------------------------------------------------------------------------
# PubMedRecord (A1) builder
# ---------------------------------------------------------------------------

def make_pubmed_record(npi: str = NPI_ALICE) -> PubMedRecord:
    prov = _provenance("A1", "PubMed / Entrez", SourceCategory.ACADEMIC, npi)
    return PubMedRecord(
        entity_npi=npi,
        provenance=prov,
        pmid="12345678",
        title="Test Publication",
        publication_year=2023,
    )


# ---------------------------------------------------------------------------
# ClinicalTrialRecord (A2) builder
# ---------------------------------------------------------------------------

def make_clinical_trial_record(npi: str = NPI_ALICE) -> ClinicalTrialRecord:
    prov = _provenance("A2", "ClinicalTrials.gov", SourceCategory.ACADEMIC, npi)
    return ClinicalTrialRecord(
        entity_npi=npi,
        provenance=prov,
        nct_id="NCT00000001",
        title="Test Clinical Trial",
        status="Completed",
    )

"""
_fixtures.py -- Shared test helpers for Phase 2-F entity linker tests.

Extends the identity test fixtures (tests/identity/_fixtures.py) with
builders for a UnifiedIdBundle and additional NormalizedRecord variants
needed for merger and extractor tests.

All records are built without going through the full connector + normalizer
stack.  entity_npi is always set (C11 guarantee).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from uuid import uuid4

from schema.v1.common import (
    Address,
    DataProvenance,
    EntityType,
    Gender,
    ProviderName,
    SourceCategory,
    TaxonomyCode,
    utc_now,
)
from schema.v1.identity import OtherIdentifier, UnifiedIdBundle
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
NPI_ALICE = "1234567890"
NPI_BOB   = "0987654321"
NPI_ORG   = "1111111111"


def _fake_hash(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


def _prov(
    source_id: str,
    source_name: str,
    category: SourceCategory,
    npi: str,
    suffix: str = "",
) -> DataProvenance:
    return DataProvenance(
        source_id=source_id,
        source_name=source_name,
        source_category=category,
        source_record_id=npi,
        ingested_at=utc_now(),
        raw_record_hash=_fake_hash(f"{source_id}:{npi}:{suffix}"),
    )


# ---------------------------------------------------------------------------
# Default helpers
# ---------------------------------------------------------------------------

def _default_address() -> Address:
    return Address(
        street_line_1="100 Main St",
        city="Anytown",
        state="CA",
        postal_code="90001",
    )


def _default_taxonomy(primary: bool = True) -> TaxonomyCode:
    return TaxonomyCode(
        code="207Q00000X",
        description="Family Medicine",
        primary=primary,
    )


def _default_name(first: str = "Alice", last: str = "Smith") -> ProviderName:
    return ProviderName(first=first, last=last)


# ---------------------------------------------------------------------------
# UnifiedIdBundle builder
# ---------------------------------------------------------------------------

def make_bundle(
    npi: str = NPI_ALICE,
    first: str = "Alice",
    last: str = "Smith",
    entity_type: EntityType = EntityType.INDIVIDUAL,
    contributing_sources: list[str] | None = None,
    confidence: float = 0.950,
    human_review_required: bool = False,
    addresses: list[Address] | None = None,
    taxonomy: TaxonomyCode | None = None,
    gender: Gender = Gender.UNKNOWN,
) -> UnifiedIdBundle:
    if contributing_sources is None:
        contributing_sources = ["F1"]
    if addresses is None:
        addresses = [_default_address()]
    if taxonomy is None:
        taxonomy = _default_taxonomy()

    return UnifiedIdBundle(
        primary_npi=npi,
        entity_type=entity_type,
        primary_name=_default_name(first, last),
        gender=gender,
        primary_specialty=taxonomy,
        all_taxonomies=[taxonomy],
        known_addresses=addresses,
        identity_confidence=confidence,
        contributing_sources=contributing_sources,
        human_review_required=human_review_required,
    )


def make_org_bundle(npi: str = NPI_ORG) -> UnifiedIdBundle:
    return UnifiedIdBundle(
        primary_npi=npi,
        entity_type=EntityType.ORGANIZATION,
        primary_name=ProviderName(first="Acme", last="Medical Group"),
        identity_confidence=0.950,
        contributing_sources=["F1"],
    )


# ---------------------------------------------------------------------------
# NppesRecord (F1) builders
# ---------------------------------------------------------------------------

def make_nppes_record(
    npi: str = NPI_ALICE,
    first: str = "Alice",
    last: str = "Smith",
    entity_type: EntityType = EntityType.INDIVIDUAL,
    organization_name: str | None = None,
) -> NppesRecord:
    prov = _prov("F1", "NPPES NPI Registry", SourceCategory.FEDERAL, npi)
    return NppesRecord(
        entity_npi=npi,
        provenance=prov,
        entity_type=entity_type,
        name=ProviderName(first=first, last=last),
        addresses=[_default_address()],
        taxonomy_codes=[_default_taxonomy()],
        organization_name=organization_name,
    )


# ---------------------------------------------------------------------------
# OigLeieRecord (F2) builders
# ---------------------------------------------------------------------------

def make_oig_record(
    npi: str = NPI_ALICE,
    active: bool = True,
    exclusion_date: date = date(2020, 1, 15),
    reinstatement_date: date | None = None,
) -> OigLeieRecord:
    prov = _prov("F2", "OIG LEIE", SourceCategory.FEDERAL, npi)
    return OigLeieRecord(
        entity_npi=npi,
        provenance=prov,
        exclusion_type="1128a1",
        exclusion_date=exclusion_date,
        reinstatement_date=None if active else (reinstatement_date or date(2022, 6, 1)),
        general_exclusion=True,
        reported_first_name="Alice",
        reported_last_name="Smith",
    )


def make_oig_historical(npi: str = NPI_ALICE) -> OigLeieRecord:
    """An OIG record that has been reinstated (not active)."""
    return make_oig_record(npi=npi, active=False, reinstatement_date=date(2022, 6, 1))


# ---------------------------------------------------------------------------
# SamExclusionRecord (F3) builders
# ---------------------------------------------------------------------------

def make_sam_record(
    npi: str = NPI_ALICE,
    active: bool = True,
) -> SamExclusionRecord:
    prov = _prov("F3", "SAM.gov Exclusions", SourceCategory.FEDERAL, npi)
    return SamExclusionRecord(
        entity_npi=npi,
        provenance=prov,
        unique_entity_id="UEI123456",
        exclusion_type="Ineligible (Proceedings Complete)",
        active_exclusion=active,
        exclusion_date=date(2021, 6, 1),
        exclusion_expiration_date=None if active else date(2023, 1, 1),
        exclusion_program="Federal Health Care Programs",
    )


# ---------------------------------------------------------------------------
# CmsProviderRecord (F4) builders
# ---------------------------------------------------------------------------

def make_cms_record(
    npi: str = NPI_ALICE,
    accepts_medicare: bool | None = True,
    opted_out: bool | None = None,
    graduation_year: int | None = 2005,
    medical_school: str | None = "State University Medical School",
    org_name: str | None = "Anytown Medical Group",
    group_pac_id: str | None = "1234567890",
    hospital_affiliations: list[dict] | None = None,
) -> CmsProviderRecord:
    if hospital_affiliations is None:
        hospital_affiliations = [
            {
                "hospital_name": "City General Hospital",
                "hospital_pac_id": "PAC001",
                "hospital_ccn": "CCN001",
            }
        ]
    prov = _prov("F4", "CMS Care Compare", SourceCategory.FEDERAL, npi)
    return CmsProviderRecord(
        entity_npi=npi,
        provenance=prov,
        accepts_medicare_assignment=accepts_medicare,
        opted_out_of_medicare=opted_out,
        graduation_year=graduation_year,
        medical_school=medical_school,
        org_name=org_name,
        group_practice_pac_id=group_pac_id,
        hospital_affiliations=hospital_affiliations,
    )


# ---------------------------------------------------------------------------
# MedicareEnrollmentRecord (I1) builders
# ---------------------------------------------------------------------------

def make_medicare_record(
    npi: str = NPI_ALICE,
    indicator: str = "Y",
    opt_out_date: date | None = None,
) -> MedicareEnrollmentRecord:
    prov = _prov("I1", "CMS Medicare Enrollment", SourceCategory.FEDERAL, npi)
    return MedicareEnrollmentRecord(
        entity_npi=npi,
        provenance=prov,
        participation_indicator=indicator,
        opt_out_effective_date=opt_out_date,
    )


# ---------------------------------------------------------------------------
# MedicaidEnrollmentRecord (I2) builders
# ---------------------------------------------------------------------------

def make_medicaid_record(
    npi: str = NPI_ALICE,
    state: str = "CA",
    status: str = "enrolled",
) -> MedicaidEnrollmentRecord:
    prov = _prov("I2", "CMS Medicaid Enrollment", SourceCategory.FEDERAL, npi)
    return MedicaidEnrollmentRecord(
        entity_npi=npi,
        provenance=prov,
        state=state,
        enrollment_status=status,
    )


# ---------------------------------------------------------------------------
# PubMedRecord (A1) builders
# ---------------------------------------------------------------------------

def make_pubmed_record(
    npi: str = NPI_ALICE,
    pmid: str = "12345678",
    year: int | None = 2023,
    suffix: str = "",
) -> PubMedRecord:
    prov = _prov("A1", "PubMed / Entrez", SourceCategory.ACADEMIC, npi, suffix)
    return PubMedRecord(
        entity_npi=npi,
        provenance=prov,
        pmid=pmid,
        title=f"Test Publication {pmid}",
        publication_year=year,
        journal="Journal of Medicine",
    )


# ---------------------------------------------------------------------------
# ClinicalTrialRecord (A2) builders
# ---------------------------------------------------------------------------

def make_trial_record(
    npi: str = NPI_ALICE,
    nct_id: str = "NCT00000001",
) -> ClinicalTrialRecord:
    prov = _prov("A2", "ClinicalTrials.gov", SourceCategory.ACADEMIC, npi)
    return ClinicalTrialRecord(
        entity_npi=npi,
        provenance=prov,
        nct_id=nct_id,
        title="Test Clinical Trial",
        status="Completed",
        investigator_role="Principal Investigator",
    )

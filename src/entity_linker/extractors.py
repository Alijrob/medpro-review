"""
extractors.py -- Per-record-type extraction functions for C13 (Phase 2-F).

Each function takes a list of one NormalizedRecord subtype and returns
the corresponding CanonicalProviderProfile sub-models.

All functions are stateless pure functions: no network, no DB, no side effects.
They are independently testable and ordered by source priority tier.

Routing by record_type discriminator (not isinstance checks) keeps this
extensible: Phase 3 state-board records simply require adding new extractor
functions; no existing code changes.
"""
from __future__ import annotations

from datetime import date

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
from schema.v1.profile import (
    ExclusionRecord,
    HospitalAffiliation,
    InsuranceParticipation,
    PublicationSummary,
)


# ---------------------------------------------------------------------------
# OIG LEIE (F2) -- federal exclusion records
# ---------------------------------------------------------------------------


def extract_oig_exclusions(records: list[OigLeieRecord]) -> list[ExclusionRecord]:
    """
    Convert OigLeieRecord objects into ExclusionRecord profile sub-models.

    is_active is True when no reinstatement_date is set (the exclusion is
    ongoing). When reinstatement_date is present the exclusion is historical.
    """
    result: list[ExclusionRecord] = []
    for r in records:
        is_active = r.reinstatement_date is None
        result.append(
            ExclusionRecord(
                source_registry="OIG LEIE",
                exclusion_type=r.exclusion_type,
                exclusion_date=r.exclusion_date,
                reinstatement_date=r.reinstatement_date,
                is_active=is_active,
                general_exclusion=r.general_exclusion,
                description=r.exclusion_description,
                source_id="F2",
            )
        )
    return result


# ---------------------------------------------------------------------------
# SAM.gov (F3) -- federal debarment records
# ---------------------------------------------------------------------------


def extract_sam_exclusions(records: list[SamExclusionRecord]) -> list[ExclusionRecord]:
    """
    Convert SamExclusionRecord objects into ExclusionRecord profile sub-models.

    active_exclusion maps directly from the SamExclusionRecord. The
    exclusion_expiration_date (if set) is treated as the reinstatement_date
    (the date after which the provider is no longer excluded).
    """
    result: list[ExclusionRecord] = []
    for r in records:
        result.append(
            ExclusionRecord(
                source_registry="SAM.gov",
                exclusion_type=r.exclusion_type,
                exclusion_date=r.exclusion_date,
                reinstatement_date=r.exclusion_expiration_date,
                is_active=r.active_exclusion,
                general_exclusion=None,  # SAM.gov does not use this classification
                description=r.exclusion_program,
                source_id="F3",
            )
        )
    return result


# ---------------------------------------------------------------------------
# CMS Care Compare (F4) -- hospital affiliations and practice context
# ---------------------------------------------------------------------------


def extract_hospital_affiliations(
    records: list[CmsProviderRecord],
) -> list[HospitalAffiliation]:
    """
    Build a deduplicated list of HospitalAffiliation objects from F4 records.

    CMS Care Compare reports one row per NPI per practice address; many rows
    share the same hospital affiliations. Deduplication is by
    (hospital_name.lower(), hospital_pac_id) to avoid listing the same
    hospital multiple times from different F4 rows.
    """
    seen: set[tuple[str, str]] = set()
    result: list[HospitalAffiliation] = []
    for r in records:
        for aff in r.hospital_affiliations:
            name: str = aff.get("hospital_name", "").strip()
            if not name:
                continue
            pac_id: str = (aff.get("hospital_pac_id") or "").strip()
            key = (name.lower(), pac_id)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                HospitalAffiliation(
                    hospital_name=name,
                    hospital_pac_id=pac_id or None,
                    hospital_ccn=(aff.get("hospital_ccn") or "").strip() or None,
                    affiliation_type="admitting privileges",
                    source_id="F4",
                )
            )
    return result


def extract_cms_practice_context(
    records: list[CmsProviderRecord],
) -> dict:
    """
    Extract practice-context scalar fields from F4 records.

    Returns a dict with keys: graduation_year, medical_school,
    group_practice_name, group_practice_pac_id, accepts_medicare,
    opted_out_of_medicare.

    First non-None value wins across multiple F4 rows (they describe the same
    provider from different locations; the practice context fields are identical
    across rows for a given NPI).
    """
    graduation_year: int | None = None
    medical_school: str | None = None
    group_practice_name: str | None = None
    group_practice_pac_id: str | None = None
    accepts_medicare: bool | None = None
    opted_out: bool | None = None

    for r in records:
        if graduation_year is None and r.graduation_year is not None:
            graduation_year = r.graduation_year
        if medical_school is None and r.medical_school:
            medical_school = r.medical_school.strip() or None
        if group_practice_name is None and r.org_name:
            group_practice_name = r.org_name.strip() or None
        if group_practice_pac_id is None and r.group_practice_pac_id:
            group_practice_pac_id = r.group_practice_pac_id.strip() or None
        if accepts_medicare is None and r.accepts_medicare_assignment is not None:
            accepts_medicare = r.accepts_medicare_assignment
        if opted_out is None and r.opted_out_of_medicare is not None:
            opted_out = r.opted_out_of_medicare

    return {
        "graduation_year": graduation_year,
        "medical_school": medical_school,
        "group_practice_name": group_practice_name,
        "group_practice_pac_id": group_practice_pac_id,
        "accepts_medicare_from_f4": accepts_medicare,
        "opted_out_from_f4": opted_out,
    }


# ---------------------------------------------------------------------------
# CMS Medicare Enrollment (I1) -- Medicare participation status
# ---------------------------------------------------------------------------


def extract_medicare_participation(
    records: list[MedicareEnrollmentRecord],
) -> tuple[list[InsuranceParticipation], bool | None, bool]:
    """
    Build InsuranceParticipation entries from I1 records.

    Returns (participations, accepts_medicare, opted_out_of_medicare).

    accepts_medicare:
      True   -- at least one "Y" (participating) record found.
      False  -- only "N" or "O" records found.
      None   -- no I1 records at all.

    opted_out_of_medicare:
      True   -- at least one "O" (opted out) record found.
      False  -- no opt-out records (default).

    Participation indicator semantics (from CMS Physician Enrollment):
      "Y" = participating (accepts Medicare assignment)
      "N" = non-participating (can bill Medicare but not at assigned rate)
      "O" = opted out (may not bill Medicare at all)
    """
    if not records:
        return [], None, False

    participations: list[InsuranceParticipation] = []
    accepts_medicare: bool | None = None
    opted_out = False

    for r in records:
        ind = r.participation_indicator.upper()
        if ind == "Y":
            participations.append(
                InsuranceParticipation(
                    program="Medicare",
                    status="participating",
                    opted_out=False,
                    accepts_assignment=True,
                    opt_out_effective_date=None,
                    source_id="I1",
                )
            )
            accepts_medicare = True  # "Y" beats any "N" found earlier
        elif ind == "N":
            participations.append(
                InsuranceParticipation(
                    program="Medicare",
                    status="non-participating",
                    opted_out=False,
                    accepts_assignment=False,
                    source_id="I1",
                )
            )
            if accepts_medicare is None:
                accepts_medicare = False
        elif ind == "O":
            participations.append(
                InsuranceParticipation(
                    program="Medicare",
                    status="opted_out",
                    opted_out=True,
                    opt_out_effective_date=r.opt_out_effective_date,
                    accepts_assignment=False,
                    source_id="I1",
                )
            )
            opted_out = True
            if accepts_medicare is None:
                accepts_medicare = False

    return participations, accepts_medicare, opted_out


# ---------------------------------------------------------------------------
# CMS Medicaid Enrollment (I2) -- Medicaid participation status
# ---------------------------------------------------------------------------


def extract_medicaid_participation(
    records: list[MedicaidEnrollmentRecord],
) -> tuple[list[InsuranceParticipation], bool | None]:
    """
    Build InsuranceParticipation entries from I2 records.

    Returns (participations, accepts_medicaid).

    accepts_medicaid:
      True   -- at least one record with enrollment_status indicating active.
      False  -- records exist but none indicate active enrollment.
      None   -- no I2 records at all.

    Program name is per-state (e.g., "Medicaid-CA") since Medicaid is
    state-administered. A provider may appear in multiple states.
    """
    if not records:
        return [], None

    participations: list[InsuranceParticipation] = []
    accepts_medicaid: bool | None = False  # default False if records exist

    _ACTIVE_STATUSES = frozenset({"enrolled", "active", "participating", "approved"})

    for r in records:
        status_lower = r.enrollment_status.lower().strip()
        prog = f"Medicaid-{r.state}" if r.state else "Medicaid"
        participations.append(
            InsuranceParticipation(
                program=prog,
                status=r.enrollment_status,
                opted_out=False,
                source_id="I2",
            )
        )
        if status_lower in _ACTIVE_STATUSES:
            accepts_medicaid = True

    return participations, accepts_medicaid


# ---------------------------------------------------------------------------
# PubMed (A1) -- research publications
# ---------------------------------------------------------------------------


def extract_publications(
    records: list[PubMedRecord],
    max_recent: int = 10,
) -> tuple[list[PublicationSummary], int]:
    """
    Build PublicationSummary list and total count from A1 records.

    Returns (recent_publications, total_count).

    recent_publications contains at most max_recent entries, sorted by
    publication_year descending (most recent first). Full publication
    list is retained in the original NormalizedRecords.
    """
    total = len(records)
    if total == 0:
        return [], 0

    sorted_recs = sorted(
        records,
        key=lambda r: r.publication_year or 0,
        reverse=True,
    )

    recent: list[PublicationSummary] = []
    for r in sorted_recs[:max_recent]:
        recent.append(
            PublicationSummary(
                pmid=r.pmid,
                title=r.title,
                journal=r.journal,
                publication_year=r.publication_year,
                doi=r.doi,
                citation_count=r.citation_count,
                author_position=r.author_position,
            )
        )

    return recent, total

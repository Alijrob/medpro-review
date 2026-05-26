"""
test_extractors.py -- Unit tests for entity_linker.extractors (Phase 2-F, C13).

Tests each extractor function independently with typed NormalizedRecord inputs.
No DB, no network, no side effects.
"""
from __future__ import annotations

import pytest
from datetime import date

from ._fixtures import (
    NPI_ALICE,
    make_cms_record,
    make_medicaid_record,
    make_medicare_record,
    make_oig_historical,
    make_oig_record,
    make_pubmed_record,
    make_sam_record,
    make_trial_record,
)
from entity_linker.extractors import (
    extract_cms_practice_context,
    extract_hospital_affiliations,
    extract_medicaid_participation,
    extract_medicare_participation,
    extract_oig_exclusions,
    extract_publications,
    extract_sam_exclusions,
)


# ===========================================================================
# OIG LEIE (F2) extractors
# ===========================================================================

class TestExtractOigExclusions:

    def test_empty_list_returns_empty(self):
        result = extract_oig_exclusions([])
        assert result == []

    def test_active_exclusion_has_is_active_true(self):
        rec = make_oig_record(active=True)
        [ex] = extract_oig_exclusions([rec])
        assert ex.is_active is True

    def test_reinstated_exclusion_has_is_active_false(self):
        rec = make_oig_historical()
        [ex] = extract_oig_exclusions([rec])
        assert ex.is_active is False

    def test_exclusion_fields_mapped_correctly(self):
        rec = make_oig_record(
            npi=NPI_ALICE,
            exclusion_date=date(2020, 3, 10),
        )
        [ex] = extract_oig_exclusions([rec])
        assert ex.source_registry == "OIG LEIE"
        assert ex.source_id == "F2"
        assert ex.exclusion_date == date(2020, 3, 10)
        assert ex.general_exclusion is True
        assert ex.exclusion_type == "1128a1"

    def test_multiple_records_produces_multiple_exclusions(self):
        recs = [make_oig_record(), make_oig_historical()]
        result = extract_oig_exclusions(recs)
        assert len(result) == 2
        active = [e for e in result if e.is_active]
        inactive = [e for e in result if not e.is_active]
        assert len(active) == 1
        assert len(inactive) == 1

    def test_reinstatement_date_preserved(self):
        rec = make_oig_historical()
        [ex] = extract_oig_exclusions([rec])
        assert ex.reinstatement_date == date(2022, 6, 1)


# ===========================================================================
# SAM.gov (F3) extractors
# ===========================================================================

class TestExtractSamExclusions:

    def test_empty_list_returns_empty(self):
        assert extract_sam_exclusions([]) == []

    def test_active_sam_exclusion(self):
        rec = make_sam_record(active=True)
        [ex] = extract_sam_exclusions([rec])
        assert ex.source_registry == "SAM.gov"
        assert ex.source_id == "F3"
        assert ex.is_active is True

    def test_inactive_sam_exclusion(self):
        rec = make_sam_record(active=False)
        [ex] = extract_sam_exclusions([rec])
        assert ex.is_active is False
        assert ex.reinstatement_date == date(2023, 1, 1)

    def test_general_exclusion_is_none_for_sam(self):
        rec = make_sam_record()
        [ex] = extract_sam_exclusions([rec])
        assert ex.general_exclusion is None


# ===========================================================================
# CMS Care Compare (F4) extractors
# ===========================================================================

class TestExtractHospitalAffiliations:

    def test_empty_cms_records(self):
        assert extract_hospital_affiliations([]) == []

    def test_cms_record_with_no_affiliations(self):
        rec = make_cms_record(hospital_affiliations=[])
        result = extract_hospital_affiliations([rec])
        assert result == []

    def test_single_hospital_affiliation(self):
        rec = make_cms_record()
        [aff] = extract_hospital_affiliations([rec])
        assert aff.hospital_name == "City General Hospital"
        assert aff.hospital_pac_id == "PAC001"
        assert aff.hospital_ccn == "CCN001"
        assert aff.source_id == "F4"

    def test_deduplication_across_cms_rows(self):
        """Same hospital in two F4 rows (same NPI, different address) deduped."""
        hosp = {"hospital_name": "City General Hospital", "hospital_pac_id": "PAC001"}
        rec1 = make_cms_record(hospital_affiliations=[hosp])
        rec2 = make_cms_record(hospital_affiliations=[hosp])
        result = extract_hospital_affiliations([rec1, rec2])
        assert len(result) == 1

    def test_two_different_hospitals(self):
        rec = make_cms_record(
            hospital_affiliations=[
                {"hospital_name": "Hospital A", "hospital_pac_id": "PAC001"},
                {"hospital_name": "Hospital B", "hospital_pac_id": "PAC002"},
            ]
        )
        result = extract_hospital_affiliations([rec])
        assert len(result) == 2
        names = {a.hospital_name for a in result}
        assert names == {"Hospital A", "Hospital B"}

    def test_blank_hospital_name_skipped(self):
        rec = make_cms_record(
            hospital_affiliations=[{"hospital_name": "", "hospital_pac_id": "PAC001"}]
        )
        result = extract_hospital_affiliations([rec])
        assert result == []


class TestExtractCmsPracticeContext:

    def test_returns_all_fields(self):
        rec = make_cms_record()
        ctx = extract_cms_practice_context([rec])
        assert ctx["graduation_year"] == 2005
        assert ctx["medical_school"] == "State University Medical School"
        assert ctx["group_practice_name"] == "Anytown Medical Group"
        assert ctx["group_practice_pac_id"] == "1234567890"
        assert ctx["accepts_medicare_from_f4"] is True
        assert ctx["opted_out_from_f4"] is None

    def test_empty_records_returns_nones(self):
        ctx = extract_cms_practice_context([])
        assert ctx["graduation_year"] is None
        assert ctx["medical_school"] is None

    def test_first_non_none_value_wins(self):
        rec1 = make_cms_record(graduation_year=2001, medical_school=None)
        rec2 = make_cms_record(graduation_year=2005, medical_school="Other School")
        ctx = extract_cms_practice_context([rec1, rec2])
        assert ctx["graduation_year"] == 2001
        assert ctx["medical_school"] == "Other School"  # rec1 has None, rec2 wins

    def test_opted_out_flag_captured(self):
        rec = make_cms_record(accepts_medicare=None, opted_out=True)
        ctx = extract_cms_practice_context([rec])
        assert ctx["opted_out_from_f4"] is True


# ===========================================================================
# Medicare Enrollment (I1) extractors
# ===========================================================================

class TestExtractMedicareParticipation:

    def test_empty_list(self):
        parts, accepts, opted_out = extract_medicare_participation([])
        assert parts == []
        assert accepts is None
        assert opted_out is False

    def test_participating_indicator_y(self):
        rec = make_medicare_record(indicator="Y")
        parts, accepts, opted_out = extract_medicare_participation([rec])
        assert len(parts) == 1
        assert parts[0].status == "participating"
        assert parts[0].accepts_assignment is True
        assert accepts is True
        assert opted_out is False

    def test_non_participating_indicator_n(self):
        rec = make_medicare_record(indicator="N")
        parts, accepts, opted_out = extract_medicare_participation([rec])
        assert parts[0].status == "non-participating"
        assert parts[0].accepts_assignment is False
        assert accepts is False
        assert opted_out is False

    def test_opted_out_indicator_o(self):
        rec = make_medicare_record(indicator="O", opt_out_date=date(2021, 1, 1))
        parts, accepts, opted_out = extract_medicare_participation([rec])
        assert parts[0].status == "opted_out"
        assert parts[0].opted_out is True
        assert parts[0].opt_out_effective_date == date(2021, 1, 1)
        assert opted_out is True
        assert accepts is False

    def test_y_beats_n_in_multi_record(self):
        """If provider has both Y and N records, accepts_medicare = True."""
        recs = [make_medicare_record(indicator="N"), make_medicare_record(indicator="Y")]
        _, accepts, _ = extract_medicare_participation(recs)
        assert accepts is True

    def test_source_id_is_i1(self):
        rec = make_medicare_record()
        parts, _, _ = extract_medicare_participation([rec])
        assert parts[0].source_id == "I1"


# ===========================================================================
# Medicaid Enrollment (I2) extractors
# ===========================================================================

class TestExtractMedicaidParticipation:

    def test_empty_list(self):
        parts, accepts = extract_medicaid_participation([])
        assert parts == []
        assert accepts is None

    def test_enrolled_status(self):
        rec = make_medicaid_record(state="CA", status="enrolled")
        parts, accepts = extract_medicaid_participation([rec])
        assert len(parts) == 1
        assert parts[0].program == "Medicaid-CA"
        assert accepts is True

    def test_terminated_status(self):
        rec = make_medicaid_record(status="terminated")
        parts, accepts = extract_medicaid_participation([rec])
        assert len(parts) == 1
        assert accepts is False

    def test_multi_state_medicaid(self):
        recs = [
            make_medicaid_record(state="CA", status="enrolled"),
            make_medicaid_record(state="TX", status="enrolled"),
        ]
        parts, accepts = extract_medicaid_participation(recs)
        assert len(parts) == 2
        programs = {p.program for p in parts}
        assert programs == {"Medicaid-CA", "Medicaid-TX"}
        assert accepts is True


# ===========================================================================
# Publications (A1) extractor
# ===========================================================================

class TestExtractPublications:

    def test_empty_list(self):
        recent, total = extract_publications([])
        assert recent == []
        assert total == 0

    def test_single_publication(self):
        rec = make_pubmed_record(pmid="11111111", year=2023)
        recent, total = extract_publications([rec])
        assert total == 1
        assert len(recent) == 1
        assert recent[0].pmid == "11111111"

    def test_sorted_by_year_descending(self):
        recs = [
            make_pubmed_record(pmid="10000001", year=2019, suffix="a"),
            make_pubmed_record(pmid="10000002", year=2023, suffix="b"),
            make_pubmed_record(pmid="10000003", year=2021, suffix="c"),
        ]
        recent, total = extract_publications(recs)
        assert total == 3
        assert recent[0].pmid == "10000002"  # most recent
        assert recent[1].pmid == "10000003"
        assert recent[2].pmid == "10000001"

    def test_max_recent_cap_applied(self):
        recs = [
            make_pubmed_record(pmid=str(10000000 + i), year=2020 - i, suffix=str(i))
            for i in range(15)
        ]
        recent, total = extract_publications(recs, max_recent=10)
        assert total == 15
        assert len(recent) == 10

    def test_none_year_sorts_last(self):
        recs = [
            make_pubmed_record(pmid="10000001", year=None, suffix="a"),
            make_pubmed_record(pmid="10000002", year=2023, suffix="b"),
        ]
        recent, _ = extract_publications(recs)
        assert recent[0].pmid == "10000002"  # known year first

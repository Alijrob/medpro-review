"""
test_f4_cms_care_compare.py -- Tests for CmsCareCompareNormalizer (F4).

Coverage:
  - Happy path: core fields extracted
  - NPI from raw["npi"], source_record_id set
  - graduation_year integer parsed from string
  - medical_school extracted
  - hospital_affiliations: up to 5 slots collected
  - accepts_medicare_assignment: Y/N mapping
  - org_name and group_practice_pac_id
  - Missing npi raises NormalizationError
  - Invalid/missing graduation year returns None
"""
from __future__ import annotations

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from schema.v1.normalized import CmsProviderRecord

_normalizer = get_normalizer("F4")


def _make_raw(**overrides) -> RawRecord:
    base = {
        "npi": "1234567890",
        "ind_pac_id": "002345678901",
        "last_name": "DOE",
        "first_name": "JOHN",
        "pri_spec": "INTERNAL MEDICINE",
        "med_sch": "JOHNS HOPKINS UNIVERSITY",
        "grd_yr": "1995",
        "org_nm": "DOE MEDICAL GROUP",
        "num_org_mem": "5",
        "assgn": "Y",
        "cty": "BALTIMORE",
        "st": "MD",
        "hosp_afl_1": "030001",
        "hosp_afl_lbn_1": "JOHNS HOPKINS HOSPITAL",
        "pac_org_1": "002345678111",
        "hosp_afl_2": "",
        "hosp_afl_lbn_2": "",
    }
    base.update(overrides)
    return RawRecord.from_raw("F4", base)


def test_happy_path_returns_cms_provider_record():
    rec = _normalizer.normalize(_make_raw())
    assert isinstance(rec, CmsProviderRecord)


def test_npi_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert rec.entity_npi == "1234567890"


def test_source_record_id_is_npi():
    rec = _normalizer.normalize(_make_raw())
    assert rec.provenance.source_record_id == "1234567890"


def test_graduation_year_parsed():
    rec = _normalizer.normalize(_make_raw())
    assert rec.graduation_year == 1995


def test_graduation_year_invalid_returns_none():
    rec = _normalizer.normalize(_make_raw(grd_yr="not-a-year"))
    assert rec.graduation_year is None


def test_medical_school_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert rec.medical_school == "JOHNS HOPKINS UNIVERSITY"


def test_accepts_medicare_assignment_true():
    rec = _normalizer.normalize(_make_raw(assgn="Y"))
    assert rec.accepts_medicare_assignment is True


def test_accepts_medicare_assignment_false():
    rec = _normalizer.normalize(_make_raw(assgn="N"))
    assert rec.accepts_medicare_assignment is False


def test_hospital_affiliation_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert len(rec.hospital_affiliations) >= 1
    aff = rec.hospital_affiliations[0]
    assert aff["hospital_ccn"] == "030001"
    assert aff["hospital_name"] == "JOHNS HOPKINS HOSPITAL"
    assert aff["hospital_pac_id"] == "002345678111"


def test_empty_hospital_slots_not_included():
    """Slots 2-5 with empty values should not appear in the list."""
    rec = _normalizer.normalize(_make_raw())
    # Only slot 1 has data in the fixture
    assert len(rec.hospital_affiliations) == 1


def test_org_name_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert rec.org_name == "DOE MEDICAL GROUP"


def test_missing_npi_raises():
    raw = _make_raw(npi="")
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[F4]" in str(exc_info.value)

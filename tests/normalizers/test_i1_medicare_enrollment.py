"""
test_i1_medicare_enrollment.py -- Tests for MedicareEnrollmentNormalizer (I1).

Coverage:
  - enrollment record: participation_indicator="Y", specialty_description set
  - opt_out record: participation_indicator="O", opt_out_effective_date parsed
  - opt_out_end_date parsed when present, None when absent
  - source_record_id set to NPI
  - Unknown _record_type raises NormalizationError
  - Missing NPI raises NormalizationError
  - Missing optout_effective_date on opt_out record raises NormalizationError
"""
from __future__ import annotations

from datetime import date

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from schema.v1.normalized import MedicareEnrollmentRecord

_normalizer = get_normalizer("I1")


def _make_enrollment_raw(npi: str = "1234567890") -> RawRecord:
    return RawRecord.from_raw("I1", {
        "_record_type": "enrollment",
        "npi": npi,
        "last_name": "DOE",
        "first_name": "JOHN",
        "enroll_id": "I20040201000012",
        "provider_type_desc": "GENERAL PRACTICE",
        "state_cd": "MD",
    })


def _make_opt_out_raw(npi: str = "1234567890", eff_date: str = "2020-01-15",
                      end_date: str = "") -> RawRecord:
    return RawRecord.from_raw("I1", {
        "_record_type": "opt_out",
        "npi": npi,
        "last_name": "DOE",
        "first_name": "JOHN",
        "optout_effective_date": eff_date,
        "optout_end_date": end_date,
        "order_refer_flag": "N",
    })


# ------------------------------------------------------------------
# Enrollment record
# ------------------------------------------------------------------


def test_enrollment_record_type():
    rec = _normalizer.normalize(_make_enrollment_raw())
    assert isinstance(rec, MedicareEnrollmentRecord)
    assert rec.participation_indicator == "Y"


def test_enrollment_specialty_description():
    rec = _normalizer.normalize(_make_enrollment_raw())
    assert rec.specialty_description == "GENERAL PRACTICE"


def test_enrollment_opt_out_dates_are_none():
    rec = _normalizer.normalize(_make_enrollment_raw())
    assert rec.opt_out_effective_date is None
    assert rec.opt_out_end_date is None


# ------------------------------------------------------------------
# Opt-out record
# ------------------------------------------------------------------


def test_opt_out_participation_indicator():
    rec = _normalizer.normalize(_make_opt_out_raw())
    assert rec.participation_indicator == "O"


def test_opt_out_effective_date_parsed():
    rec = _normalizer.normalize(_make_opt_out_raw(eff_date="2020-01-15"))
    assert rec.opt_out_effective_date == date(2020, 1, 15)


def test_opt_out_end_date_none_when_absent():
    rec = _normalizer.normalize(_make_opt_out_raw(end_date=""))
    assert rec.opt_out_end_date is None


def test_opt_out_end_date_parsed_when_present():
    rec = _normalizer.normalize(_make_opt_out_raw(end_date="2024-12-31"))
    assert rec.opt_out_end_date == date(2024, 12, 31)


# ------------------------------------------------------------------
# Provenance
# ------------------------------------------------------------------


def test_source_record_id_is_npi():
    rec = _normalizer.normalize(_make_enrollment_raw())
    assert rec.provenance.source_record_id == "1234567890"


# ------------------------------------------------------------------
# Error cases
# ------------------------------------------------------------------


def test_unknown_record_type_raises():
    raw = RawRecord.from_raw("I1", {"_record_type": "unknown", "npi": "1234567890"})
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[I1]" in str(exc_info.value)


def test_missing_npi_raises():
    raw = RawRecord.from_raw("I1", {"_record_type": "enrollment", "npi": ""})
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[I1]" in str(exc_info.value)


def test_opt_out_missing_effective_date_raises():
    raw = RawRecord.from_raw("I1", {
        "_record_type": "opt_out",
        "npi": "1234567890",
        "optout_effective_date": "not-a-date",
        "optout_end_date": "",
        "order_refer_flag": "N",
    })
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[I1]" in str(exc_info.value)

"""
test_i2_medicaid_enrollment.py -- Tests for MedicaidEnrollmentNormalizer (I2).

Coverage:
  - Happy path: state, enrollment_status, provider_type
  - enrollment_status always "enrolled"
  - NPI extracted from raw
  - source_record_id set to NPI
  - Missing NPI raises NormalizationError
  - Missing/invalid state_cd raises NormalizationError
  - state normalized to uppercase
"""
from __future__ import annotations

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from schema.v1.normalized import MedicaidEnrollmentRecord

_normalizer = get_normalizer("I2")


def _make_raw(npi: str = "1234567890", state_cd: str = "CA",
               provider_type: str = "PHYSICIAN") -> RawRecord:
    return RawRecord.from_raw("I2", {
        "npi": npi,
        "last_name": "DOE",
        "first_name": "JOHN",
        "state_cd": state_cd,
        "provider_type_desc": provider_type,
    })


def test_happy_path_returns_medicaid_enrollment_record():
    rec = _normalizer.normalize(_make_raw())
    assert isinstance(rec, MedicaidEnrollmentRecord)


def test_npi_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert rec.entity_npi == "1234567890"


def test_source_record_id_is_npi():
    rec = _normalizer.normalize(_make_raw())
    assert rec.provenance.source_record_id == "1234567890"


def test_enrollment_status_always_enrolled():
    rec = _normalizer.normalize(_make_raw())
    assert rec.enrollment_status == "enrolled"


def test_state_extracted():
    rec = _normalizer.normalize(_make_raw(state_cd="TX"))
    assert rec.state == "TX"


def test_state_normalized_to_uppercase():
    rec = _normalizer.normalize(_make_raw(state_cd="ca"))
    assert rec.state == "CA"


def test_provider_type_extracted():
    rec = _normalizer.normalize(_make_raw(provider_type="FAMILY PRACTICE"))
    assert rec.provider_type == "FAMILY PRACTICE"


def test_missing_npi_raises():
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(_make_raw(npi=""))
    assert "[I2]" in str(exc_info.value)


def test_invalid_state_raises():
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(_make_raw(state_cd=""))
    assert "[I2]" in str(exc_info.value)

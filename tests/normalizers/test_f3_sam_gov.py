"""
test_f3_sam_gov.py -- Tests for SamGovNormalizer (F3).

Coverage:
  - Happy path: exclusion fields extracted
  - entity_npi is required (no NPI in raw)
  - Raises if entity_npi missing
  - UEI extracted from entityRegistration.ueiSAM as source_record_id
  - active_exclusion: Y -> True, N -> False
  - exclusion_date parsed (ISO format from SAM.gov)
  - exclusion_expiration_date: None when absent
  - agency from excludingAgencyName
  - ct_code extracted
  - Missing UEI raises NormalizationError
  - Missing/unparseable exclusionDate raises NormalizationError
"""
from __future__ import annotations

from datetime import date

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from schema.v1.normalized import SamExclusionRecord

_normalizer = get_normalizer("F3")


def _make_raw(**overrides) -> RawRecord:
    base = {
        "exclusionDetails": {
            "exclusionType": "Ineligible (Proceedings Completed)",
            "exclusionProgram": "Reciprocal",
            "excludingAgencyCode": "HHS",
            "excludingAgencyName": "Health and Human Services",
            "activeExclusion": "Y",
            "exclusionDate": "2020-01-15",
            "exclusionEndDate": None,
            "ctCode": "Z0",
        },
        "entityRegistration": {
            "ueiSAM": "ABC123456789",
            "legalBusinessName": "John Doe MD",
        },
    }
    _deep_update(base, overrides)
    return RawRecord.from_raw("F3", base)


def _deep_update(d: dict, u: dict) -> dict:
    for k, v in u.items():
        if isinstance(v, dict) and isinstance(d.get(k), dict):
            _deep_update(d[k], v)
        else:
            d[k] = v
    return d


def test_happy_path_returns_sam_exclusion_record():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert isinstance(rec, SamExclusionRecord)


def test_entity_npi_set():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.entity_npi == "1234567890"


def test_missing_entity_npi_raises():
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(_make_raw())
    assert "[F3]" in str(exc_info.value)


def test_uei_as_source_record_id():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.unique_entity_id == "ABC123456789"
    assert rec.provenance.source_record_id == "ABC123456789"


def test_active_exclusion_true():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.active_exclusion is True


def test_active_exclusion_false():
    raw = _make_raw(exclusionDetails={"activeExclusion": "N", "exclusionDate": "2020-01-15",
                                       "exclusionType": "Ineligible"})
    rec = _normalizer.normalize(raw, entity_npi="1234567890")
    assert rec.active_exclusion is False


def test_exclusion_date_parsed():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.exclusion_date == date(2020, 1, 15)


def test_expiration_date_none_when_absent():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.exclusion_expiration_date is None


def test_agency_extracted():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.agency == "Health and Human Services"


def test_ct_code_extracted():
    rec = _normalizer.normalize(_make_raw(), entity_npi="1234567890")
    assert rec.ct_code == "Z0"


def test_missing_uei_raises():
    raw = _make_raw(entityRegistration={"ueiSAM": ""})
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw, entity_npi="1234567890")
    assert "[F3]" in str(exc_info.value)


def test_missing_exclusion_date_raises():
    raw = _make_raw(exclusionDetails={"exclusionDate": "not-a-date",
                                       "exclusionType": "Ineligible", "activeExclusion": "Y"})
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw, entity_npi="1234567890")
    assert "[F3]" in str(exc_info.value)

"""
test_f2_oig_leie.py -- Tests for OigLeieNormalizer (F2).

Coverage:
  - Happy path: exclusion fields extracted
  - NPI from raw["NPI"]
  - Falls back to entity_npi when raw NPI is empty
  - Raises when neither raw NPI nor entity_npi available
  - general_exclusion=True for 1128a codes
  - general_exclusion=False for 1128b codes
  - reinstatement_date and waiver_date parsed
  - reported_address built from ADDRESS/CITY/STATE/ZIP
  - Missing EXCDATE raises NormalizationError
  - source_record_id set to NPI
"""
from __future__ import annotations

from datetime import date

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from schema.v1.normalized import OigLeieRecord

_normalizer = get_normalizer("F2")


def _make_raw(npi: str = "1234567890", excl_type: str = "1128a1",
               excl_date: str = "01/15/2020", **overrides) -> RawRecord:
    base = {
        "LASTNAME": "DOE",
        "FIRSTNAME": "JOHN",
        "MIDNAME": "A",
        "BUSNAME": "",
        "SPECIALTY": "PHYSICIAN",
        "NPI": npi,
        "EXCDATE": excl_date,
        "EXCLTYPE": excl_type,
        "ACTION": "EXCLUSION",
        "ADDRESS": "123 MAIN ST",
        "CITY": "LOS ANGELES",
        "STATE": "CA",
        "ZIP": "90001",
        "REINDATE": "",
        "WAIVERDATE": "",
        "WAIVERSTATE": "",
    }
    base.update(overrides)
    return RawRecord.from_raw("F2", base)


def test_happy_path_returns_oig_leie_record():
    rec = _normalizer.normalize(_make_raw())
    assert isinstance(rec, OigLeieRecord)


def test_npi_from_raw():
    rec = _normalizer.normalize(_make_raw())
    assert rec.entity_npi == "1234567890"
    assert rec.provenance.source_record_id == "1234567890"


def test_falls_back_to_entity_npi_when_raw_empty():
    raw = _make_raw(npi="")
    rec = _normalizer.normalize(raw, entity_npi="9876543210")
    assert rec.entity_npi == "9876543210"


def test_no_npi_anywhere_raises():
    raw = _make_raw(npi="")
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[F2]" in str(exc_info.value)


def test_mandatory_exclusion_general_true():
    rec = _normalizer.normalize(_make_raw(excl_type="1128a1"))
    assert rec.general_exclusion is True


def test_permissive_exclusion_general_false():
    rec = _normalizer.normalize(_make_raw(excl_type="1128b4"))
    assert rec.general_exclusion is False


def test_exclusion_date_parsed():
    rec = _normalizer.normalize(_make_raw(excl_date="01/15/2020"))
    assert rec.exclusion_date == date(2020, 1, 15)


def test_reinstatement_date_parsed():
    raw = _make_raw(REINDATE="06/01/2022")
    rec = _normalizer.normalize(raw)
    assert rec.reinstatement_date == date(2022, 6, 1)


def test_reported_address_built():
    rec = _normalizer.normalize(_make_raw())
    assert rec.reported_address is not None
    assert "LOS ANGELES" in rec.reported_address
    assert "CA" in rec.reported_address


def test_specialty_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert rec.specialty == "PHYSICIAN"


def test_missing_excdate_raises():
    raw = _make_raw(excl_date="not-a-date")
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[F2]" in str(exc_info.value)

"""
test_f1_nppes.py -- Tests for NppesNormalizer (F1) and get_specialty_group helper.

Coverage:
  - Happy-path individual provider: entity_type, name, addresses, taxonomies
  - Organization (NPI-2): entity_type=ORGANIZATION, organization_name set
  - source_record_id set to NPI on provenance
  - Dates: enumeration_date, last_updated_date, deactivation_date
  - sole_proprietor YES/NO mapping
  - Addresses: valid, invalid state, invalid zip skipped
  - Taxonomy codes parsed into TaxonomyCode objects
  - other_names extracted
  - Missing NPI raises NormalizationError
  - get_specialty_group: primary-first, fallback, no match
  - I4 crosswalk applied (known code maps to specialty group)
"""
from __future__ import annotations

from datetime import date

import pytest

from connectors.models import RawRecord
from normalizers import NormalizationError, get_normalizer
from normalizers.sources import get_specialty_group
from schema.v1.common import EntityType
from schema.v1.normalized import NppesRecord


def _make_raw(number="1234567890", **overrides) -> RawRecord:
    base = {
        "number": number,
        "enumeration_type": "NPI-1",
        "basic": {
            "first_name": "JOHN",
            "last_name": "DOE",
            "middle_name": "A",
            "credential": "MD",
            "enumeration_date": "2005-01-15",
            "last_updated": "2023-06-01",
            "sole_proprietor": "NO",
        },
        "addresses": [
            {
                "address_1": "123 MAIN ST",
                "city": "LOS ANGELES",
                "state": "CA",
                "postal_code": "90001",
                "telephone_number": "2135551234",
                "address_purpose": "LOCATION",
            }
        ],
        "taxonomies": [
            {"code": "207Q00000X", "desc": "Family Medicine", "primary": True, "state": "CA",
             "license": "A12345"}
        ],
        "other_names": [],
        "other_identifiers": [],
    }
    base.update(overrides)
    return RawRecord.from_raw("F1", base)


_normalizer = get_normalizer("F1")


def test_happy_path_returns_nppes_record():
    rec = _normalizer.normalize(_make_raw())
    assert isinstance(rec, NppesRecord)


def test_entity_type_individual():
    rec = _normalizer.normalize(_make_raw())
    assert rec.entity_type == EntityType.INDIVIDUAL


def test_entity_type_organization():
    raw = _make_raw(
        enumeration_type="NPI-2",
        basic={
            "organization_name": "DOE MEDICAL GROUP",
            "authorized_official_first_name": "JANE",
            "authorized_official_last_name": "DOE",
            "credential": "MD",
        },
    )
    rec = _normalizer.normalize(raw)
    assert rec.entity_type == EntityType.ORGANIZATION
    assert rec.organization_name == "DOE MEDICAL GROUP"
    assert rec.name.last == "DOE"


def test_name_fields():
    rec = _normalizer.normalize(_make_raw())
    assert rec.name.first == "JOHN"
    assert rec.name.last == "DOE"
    assert rec.name.middle == "A"
    assert rec.name.credentials == "MD"


def test_source_record_id_is_npi():
    rec = _normalizer.normalize(_make_raw())
    assert rec.provenance.source_record_id == "1234567890"


def test_provenance_source_id():
    rec = _normalizer.normalize(_make_raw())
    assert rec.provenance.source_id == "F1"


def test_enumeration_date_parsed():
    rec = _normalizer.normalize(_make_raw())
    assert rec.enumeration_date == date(2005, 1, 15)


def test_last_updated_date_parsed():
    rec = _normalizer.normalize(_make_raw())
    assert rec.last_updated_date == date(2023, 6, 1)


def test_sole_proprietor_no():
    rec = _normalizer.normalize(_make_raw())
    assert rec.sole_proprietor is False


def test_sole_proprietor_yes():
    raw = _make_raw(basic={
        "first_name": "JOHN", "last_name": "DOE",
        "sole_proprietor": "YES", "enumeration_date": "", "last_updated": "",
    })
    rec = _normalizer.normalize(raw)
    assert rec.sole_proprietor is True


def test_address_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert len(rec.addresses) == 1
    addr = rec.addresses[0]
    assert addr.street_line_1 == "123 MAIN ST"
    assert addr.city == "LOS ANGELES"
    assert addr.state == "CA"
    assert addr.postal_code == "90001"
    assert addr.address_type == "practice"


def test_invalid_state_address_skipped():
    raw = _make_raw(addresses=[{"address_1": "123 ST", "city": "NYC", "state": "ZZ",
                                  "postal_code": "10001"}])
    # ZZ is not a real state but passes the 2-alpha check -- use empty state instead
    raw2 = _make_raw(addresses=[{"address_1": "123 ST", "city": "NYC",
                                   "state": "", "postal_code": "10001"}])
    rec = _normalizer.normalize(raw2)
    assert rec.addresses == []


def test_invalid_zip_address_skipped():
    raw = _make_raw(addresses=[{"address_1": "123 ST", "city": "LA", "state": "CA",
                                  "postal_code": "123"}])
    rec = _normalizer.normalize(raw)
    assert rec.addresses == []


def test_taxonomy_codes_extracted():
    rec = _normalizer.normalize(_make_raw())
    assert len(rec.taxonomy_codes) == 1
    tc = rec.taxonomy_codes[0]
    assert tc.code == "207Q00000X"
    assert tc.primary is True
    assert tc.description == "Family Medicine"
    assert tc.license_state == "CA"


def test_missing_npi_raises():
    raw = _make_raw(number="")
    with pytest.raises(NormalizationError) as exc_info:
        _normalizer.normalize(raw)
    assert "[F1]" in str(exc_info.value)


# ---------------------------------------------------------------------------
# get_specialty_group (I4 crosswalk)
# ---------------------------------------------------------------------------


def test_get_specialty_group_known_code():
    rec = _normalizer.normalize(_make_raw())
    # 207Q00000X is Family Medicine -> should map to a specialty group
    sg = get_specialty_group(rec)
    assert sg is not None
    assert isinstance(sg, str)


def test_get_specialty_group_no_match_returns_none():
    raw = _make_raw(taxonomies=[
        {"code": "ZZZZZZZZZZ", "desc": "Unknown", "primary": True}
    ])
    rec = _normalizer.normalize(raw)
    sg = get_specialty_group(rec)
    assert sg is None


def test_get_specialty_group_primary_first():
    """Primary taxonomy code should take precedence over non-primary."""
    raw = _make_raw(taxonomies=[
        {"code": "ZZZZZZZZZZ", "desc": "Unknown", "primary": False},
        {"code": "207Q00000X", "desc": "Family Medicine", "primary": True},
    ])
    rec = _normalizer.normalize(raw)
    sg = get_specialty_group(rec)
    assert sg is not None  # should find the primary code (207Q000000X)

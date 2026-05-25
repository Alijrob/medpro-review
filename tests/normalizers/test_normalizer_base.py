"""
test_normalizer_base.py -- Tests for SourceNormalizer base class, registry, and helpers.

Coverage:
  - NormalizationError message format
  - get_normalizer() happy path and unknown source_id
  - registered_source_ids() completeness
  - normalize() top-level dispatch
  - _parse_date() for all supported formats + edge cases
  - _extract_npi() valid and invalid inputs
  - _clean_phone(), _clean_zip()
  - _require_npi() pass and raise
"""
from __future__ import annotations

from datetime import date

import pytest

from normalizers import (
    P1_NORMALIZER_SOURCE_IDS,
    NormalizationError,
    get_normalizer,
    registered_source_ids,
)
from normalizers.base import SourceNormalizer


# ---------------------------------------------------------------------------
# NormalizationError
# ---------------------------------------------------------------------------


def test_normalization_error_message():
    err = NormalizationError("F1", "test error")
    assert "[F1]" in str(err)
    assert "test error" in str(err)
    assert err.source_id == "F1"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_all_p1_normalizers_registered():
    ids = set(registered_source_ids())
    for source_id in P1_NORMALIZER_SOURCE_IDS:
        assert source_id in ids, f"normalizer for {source_id} not registered"


def test_get_normalizer_returns_correct_type():
    n = get_normalizer("F1")
    assert isinstance(n, SourceNormalizer)
    assert n.source_id == "F1"


def test_get_normalizer_unknown_raises():
    with pytest.raises(NormalizationError) as exc_info:
        get_normalizer("XX_DOES_NOT_EXIST")
    assert "XX_DOES_NOT_EXIST" in str(exc_info.value)


def test_registered_source_ids_returns_sorted_list():
    ids = registered_source_ids()
    assert ids == sorted(ids)
    assert len(ids) >= 8  # at least the 8 P1 normalizers


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class _AnyNormalizer(SourceNormalizer):
    """Minimal concrete subclass to exercise base helpers."""

    source_id = "_TEST"
    source_name = "Test"
    source_category = None  # type: ignore[assignment]

    def normalize(self, raw, *, entity_npi=None):
        raise NotImplementedError


_N = _AnyNormalizer()


def test_parse_date_iso():
    assert _N._parse_date("2020-01-15") == date(2020, 1, 15)


def test_parse_date_us_slash():
    assert _N._parse_date("01/15/2020") == date(2020, 1, 15)


def test_parse_date_us_dash():
    assert _N._parse_date("01-15-2020") == date(2020, 1, 15)


def test_parse_date_year_month_abbr():
    assert _N._parse_date("2022 Jan") == date(2022, 1, 1)
    assert _N._parse_date("2022 Dec") == date(2022, 12, 1)


def test_parse_date_year_month_iso():
    assert _N._parse_date("2022-01") == date(2022, 1, 1)


def test_parse_date_year_only():
    assert _N._parse_date("2022") == date(2022, 1, 1)


def test_parse_date_none_or_empty():
    assert _N._parse_date(None) is None
    assert _N._parse_date("") is None
    assert _N._parse_date("   ") is None


def test_parse_date_unparseable_returns_none():
    assert _N._parse_date("not-a-date") is None
    assert _N._parse_date("13/45/2020") is None  # invalid month/day


# ---------------------------------------------------------------------------
# _extract_npi
# ---------------------------------------------------------------------------


def test_extract_npi_valid():
    assert _N._extract_npi({"npi": "1234567890"}, "npi") == "1234567890"


def test_extract_npi_wrong_length():
    assert _N._extract_npi({"npi": "12345"}, "npi") is None


def test_extract_npi_missing_key():
    assert _N._extract_npi({}, "npi") is None


def test_extract_npi_non_digit():
    assert _N._extract_npi({"npi": "123456789A"}, "npi") is None


def test_extract_npi_strips_whitespace():
    assert _N._extract_npi({"npi": " 1234567890 "}, "npi") == "1234567890"


# ---------------------------------------------------------------------------
# _clean_phone / _clean_zip
# ---------------------------------------------------------------------------


def test_clean_phone_strips_formatting():
    assert _N._clean_phone("(213) 555-1234") == "2135551234"


def test_clean_phone_too_short_returns_none():
    assert _N._clean_phone("12345") is None


def test_clean_phone_none_returns_none():
    assert _N._clean_phone(None) is None


def test_clean_zip_5digit():
    assert _N._clean_zip("90001") == "90001"


def test_clean_zip_9digit_no_hyphen():
    assert _N._clean_zip("900011234") == "90001-1234"


def test_clean_zip_already_formatted():
    assert _N._clean_zip("90001-1234") == "90001-1234"


def test_clean_zip_too_short():
    assert _N._clean_zip("123") is None


# ---------------------------------------------------------------------------
# _require_npi
# ---------------------------------------------------------------------------


def test_require_npi_valid():
    assert _N._require_npi("1234567890", "F1") == "1234567890"


def test_require_npi_none_raises():
    with pytest.raises(NormalizationError) as exc_info:
        _N._require_npi(None, "F3")
    assert "[F3]" in str(exc_info.value)


def test_require_npi_invalid_raises():
    with pytest.raises(NormalizationError):
        _N._require_npi("12345", "A1")

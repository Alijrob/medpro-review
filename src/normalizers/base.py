"""
base.py -- SourceNormalizer ABC for C11 Normalization Layer (Phase 2-D).

The normalizer library (src/normalizers/) is a pure transformation library:
RawRecord objects (C10 output) -> typed NormalizedRecord subclasses (C11 output).
No network I/O, no state, no side effects.

Each source has one SourceNormalizer subclass. normalize() is deterministic:
same RawRecord always produces the same NormalizedRecord (modulo UUID generation).

NPI source routing
------------------
Different sources embed the NPI differently:

  F1 NPPES (raw["number"]):         extracted from raw; entity_npi param ignored
  F2 OIG LEIE (raw["NPI"]):         raw NPI tried first; falls back to entity_npi
  F3 SAM.gov:                        no NPI in raw; entity_npi required
  F4 CMS Care Compare (raw["npi"]): extracted from raw; entity_npi param ignored
  I1 Medicare Enrollment (raw["npi"]): extracted from raw; entity_npi param ignored
  I2 Medicaid Enrollment (raw["npi"]): extracted from raw; entity_npi param ignored
  A1 PubMed:                         no NPI in raw; entity_npi required
  A2 ClinicalTrials.gov:             no NPI in raw; entity_npi required
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from schema.v1.common import DataProvenance, SourceCategory
from connectors.models import RawRecord
from schema.v1.normalized import NormalizedRecord

# Abbreviated month name to integer mapping for date parsing.
_MONTH_ABBRS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


class NormalizationError(Exception):
    """Raised when a RawRecord cannot be normalized to a typed NormalizedRecord."""

    def __init__(self, source_id: str, message: str) -> None:
        self.source_id = source_id
        super().__init__(f"[{source_id}] {message}")


class SourceNormalizer(ABC):
    """
    Base class for all per-source normalizers (C11).

    Subclasses declare source_id / source_name / source_category as class
    attributes and implement normalize().
    """

    source_id: str
    source_name: str
    source_category: SourceCategory

    @abstractmethod
    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> NormalizedRecord:
        """Transform a RawRecord into a typed NormalizedRecord."""
        ...

    # ------------------------------------------------------------------
    # Provenance helper
    # ------------------------------------------------------------------

    def _make_provenance(
        self,
        raw: RawRecord,
        *,
        source_record_id: str | None = None,
        source_as_of: date | None = None,
    ) -> DataProvenance:
        """Build DataProvenance from a RawRecord and optional context fields."""
        return DataProvenance(
            source_id=self.source_id,
            source_name=self.source_name,
            source_category=self.source_category,
            source_record_id=source_record_id,
            ingested_at=raw.fetched_at,
            source_as_of=source_as_of,
            raw_record_hash=raw.raw_record_hash,
        )

    # ------------------------------------------------------------------
    # Static parsing helpers (used by all normalizers)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(s: str | None) -> date | None:
        """
        Parse a date string in common source formats. Returns None for blank/None/unparseable.

        Supported formats:
          "2020-01-15"   -> date(2020, 1, 15)   (ISO full date)
          "01/15/2020"   -> date(2020, 1, 15)   (US slash)
          "01-15-2020"   -> date(2020, 1, 15)   (US dash)
          "2022 Jan"     -> date(2022, 1, 1)    (year + abbr month)
          "2022-01"      -> date(2022, 1, 1)    (year-month only)
          "2022"         -> date(2022, 1, 1)    (year only)
        """
        if not s or not s.strip():
            return None
        s = s.strip()

        # ISO: YYYY-MM-DD
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None

        # US slash: MM/DD/YYYY
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None

        # US dash: MM-DD-YYYY
        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", s)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None

        # Year + abbreviated month: "2022 Jan"
        m = re.fullmatch(r"(\d{4})\s+([A-Za-z]{3})", s)
        if m:
            month = _MONTH_ABBRS.get(m.group(2).lower())
            if month:
                return date(int(m.group(1)), month, 1)
            return None

        # Year-month: "YYYY-MM"
        m = re.fullmatch(r"(\d{4})-(\d{2})", s)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), 1)
            except ValueError:
                return None

        # Year only: "YYYY"
        m = re.fullmatch(r"(\d{4})", s)
        if m:
            return date(int(m.group(1)), 1, 1)

        return None

    @staticmethod
    def _extract_npi(raw_dict: dict[str, Any], key: str = "npi") -> str | None:
        """Extract a 10-digit NPI from raw_dict[key]. Returns None if missing or invalid."""
        val = raw_dict.get(key)
        if isinstance(val, str) and re.fullmatch(r"\d{10}", val.strip()):
            return val.strip()
        return None

    @staticmethod
    def _clean_phone(s: str | None) -> str | None:
        """Strip non-digits; return exactly 10 digits or None."""
        if not s:
            return None
        digits = re.sub(r"\D", "", s)
        return digits[:10] if len(digits) >= 10 else None

    @staticmethod
    def _clean_zip(s: str | None) -> str | None:
        """
        Normalize a ZIP code to XXXXX or XXXXX-XXXX.

        Handles NPPES 9-digit ZIPs without hyphens ("900011234") and
        ZIP+4 strings ("90001-1234"). Returns None if fewer than 5 digits.
        """
        if not s:
            return None
        digits = re.sub(r"\D", "", s)
        if len(digits) >= 9:
            return f"{digits[:5]}-{digits[5:9]}"
        if len(digits) >= 5:
            return digits[:5]
        return None

    @staticmethod
    def _require_npi(npi: str | None, source_id: str) -> str:
        """Assert NPI is present and valid; raise NormalizationError otherwise."""
        if npi and re.fullmatch(r"\d{10}", npi):
            return npi
        raise NormalizationError(source_id, f"missing or invalid entity_npi: {npi!r}")

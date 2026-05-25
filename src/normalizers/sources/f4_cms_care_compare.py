"""
f4_cms_care_compare.py -- CMS Care Compare normalizer (source F4, C11).

Transforms a RawRecord from the CMS Care Compare adapter (SODA Doctors and
Clinicians dataset) into a typed CmsProviderRecord.

CMS Care Compare yields one row per NPI per practice address. The normalizer
produces one CmsProviderRecord per row; C13 (Entity Linking) de-duplicates
and merges rows for the same NPI into a canonical profile.

Hospital affiliations: CMS encodes up to 5 affiliations in hosp_afl_1..5
(CCN), hosp_afl_lbn_1..5 (names), pac_org_1..5 (PAC IDs). The normalizer
collects all non-empty slots into hospital_affiliations.
"""
from __future__ import annotations

from typing import Any

from schema.v1.common import SourceCategory
from schema.v1.normalized import CmsProviderRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register

# Number of hospital affiliation slots in the CMS dataset
_MAX_HOSP_AFFL = 5


@register
class CmsCareCompareNormalizer(SourceNormalizer):
    """Normalizer for CMS Care Compare raw records (F4)."""

    source_id = "F4"
    source_name = "CMS Care Compare"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> CmsProviderRecord:
        r = raw.raw
        npi = self._extract_npi(r, "npi")
        if not npi:
            raise NormalizationError(self.source_id, f"missing or invalid npi in raw: {r.get('npi')!r}")

        provenance = self._make_provenance(raw, source_record_id=npi)

        return CmsProviderRecord(
            entity_npi=npi,
            provenance=provenance,
            group_practice_pac_id=_trunc(r.get("ind_pac_id"), 20),
            org_name=_trunc(r.get("org_nm"), 300),
            num_group_practice_members=_parse_int(r.get("num_org_mem")),
            graduation_year=_parse_year(r.get("grd_yr")),
            medical_school=_trunc(r.get("med_sch"), 200),
            hospital_affiliations=_extract_affiliations(r),
            accepts_medicare_assignment=_parse_yes_no(r.get("assgn")),
            opted_out_of_medicare=None,  # Care Compare doesn't carry opt-out flag
            medicare_participation_indicator=_trunc(r.get("assgn"), 10),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None


def _parse_int(s: object) -> int | None:
    if s is None:
        return None
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return None


def _parse_year(s: object) -> int | None:
    v = _parse_int(s)
    if v is not None and 1900 <= v <= 2030:
        return v
    return None


def _parse_yes_no(s: object) -> bool | None:
    if not isinstance(s, str):
        return None
    v = s.strip().upper()
    if v == "Y":
        return True
    if v == "N":
        return False
    return None


def _extract_affiliations(r: dict[str, Any]) -> list[dict[str, str]]:
    """Collect up to 5 hospital affiliation slots into a list of dicts."""
    affiliations: list[dict[str, str]] = []
    for i in range(1, _MAX_HOSP_AFFL + 1):
        ccn = _trunc(r.get(f"hosp_afl_{i}"), 10)
        name = _trunc(r.get(f"hosp_afl_lbn_{i}"), 300)
        pac = _trunc(r.get(f"pac_org_{i}"), 20)
        if ccn or name:
            entry: dict[str, str] = {}
            if ccn:
                entry["hospital_ccn"] = ccn
            if name:
                entry["hospital_name"] = name
            if pac:
                entry["hospital_pac_id"] = pac
            affiliations.append(entry)
    return affiliations

"""
f2_oig_leie.py -- OIG LEIE exclusion normalizer (source F2, C11).

Transforms a RawRecord from the OIG LEIE adapter into a typed OigLeieRecord.

NPI handling:
  Tries raw["NPI"] first. Falls back to entity_npi parameter if raw NPI is
  empty (pre-NPI-era exclusions). Raises NormalizationError if neither
  source provides a valid 10-digit NPI -- such records cannot be linked to
  a provider profile in the current phase. (Identity-resolution by name
  matching is a Phase 3+ concern.)

Mandatory vs permissive exclusion:
  OIG defines mandatory exclusions under section 1128(a) (EXCLTYPE codes
  starting with "1128a") and permissive exclusions under 1128(b) / 1156.
  general_exclusion=True corresponds to mandatory.
"""
from __future__ import annotations

from schema.v1.common import SourceCategory
from schema.v1.normalized import OigLeieRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register


@register
class OigLeieNormalizer(SourceNormalizer):
    """Normalizer for OIG LEIE bulk-download raw records (F2)."""

    source_id = "F2"
    source_name = "OIG LEIE"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> OigLeieRecord:
        r = raw.raw

        # NPI: prefer raw column, fall back to caller-supplied entity_npi
        npi = self._extract_npi(r, "NPI") or entity_npi
        npi = self._require_npi(npi, self.source_id)

        excl_type = (r.get("EXCLTYPE") or "").strip()
        excl_date = self._parse_date(r.get("EXCDATE"))
        if excl_date is None:
            raise NormalizationError(self.source_id, f"unparseable EXCDATE: {r.get('EXCDATE')!r}")

        provenance = self._make_provenance(raw, source_record_id=npi)

        return OigLeieRecord(
            entity_npi=npi,
            provenance=provenance,
            exclusion_type=excl_type[:50] if excl_type else "UNKNOWN",
            exclusion_date=excl_date,
            reinstatement_date=self._parse_date(r.get("REINDATE")),
            waiver_date=self._parse_date(r.get("WAIVERDATE")),
            waiver_state=_state_or_none(r.get("WAIVERSTATE")),
            general_exclusion=excl_type.lower().startswith("1128a"),
            exclusion_description=None,  # full lookup table is a Phase 3 enhancement
            reported_first_name=_trunc(r.get("FIRSTNAME"), 100),
            reported_last_name=_trunc(r.get("LASTNAME"), 100),
            reported_address=_trunc(_build_address(r), 300),
            specialty=_trunc(r.get("SPECIALTY"), 100),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None


def _state_or_none(s: object) -> str | None:
    if isinstance(s, str) and len(s.strip()) == 2 and s.strip().isalpha():
        return s.strip().upper()
    return None


def _build_address(r: dict) -> str | None:
    parts = [r.get("ADDRESS"), r.get("CITY"), r.get("STATE"), r.get("ZIP")]
    parts_clean = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    return ", ".join(parts_clean) if parts_clean else None

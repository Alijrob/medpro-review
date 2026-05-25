"""
f1_nppes.py -- NPPES NPI Registry normalizer (source F1, C11).

Transforms a RawRecord from the NPPES connector into a typed NppesRecord.

NPI is extracted from raw["number"]. The entity_npi parameter is ignored
(F1 is the NPI identity source -- the NPI is always in the raw).

I4 taxonomy crosswalk (DECISIONS.md Entry 021):
  The module exports get_specialty_group(nppes_record) which C13 (Entity
  Linking & Merge) calls when building the CanonicalProviderProfile. It
  applies the I4 crosswalk to the NppesRecord's taxonomy codes and returns
  the primary specialty group string (e.g., "Allopathic & Osteopathic
  Physicians"). NppesRecord itself stores typed TaxonomyCode objects; the
  crosswalk lookup is done against their code strings.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError

from schema.v1.common import Address, EntityType, ProviderName, SourceCategory, TaxonomyCode
from schema.v1.normalized import NppesRecord
from connectors.models import RawRecord
from connectors.sources.nppes_taxonomy import crosswalk_taxonomy_code

from ..base import NormalizationError, SourceNormalizer
from ..registry import register

# NPPES address_purpose -> address_type label
_ADDRESS_PURPOSE_MAP: dict[str, str] = {
    "LOCATION": "practice",
    "MAILING": "mailing",
}


@register
class NppesNormalizer(SourceNormalizer):
    """Normalizer for NPPES NPI Registry raw records (F1)."""

    source_id = "F1"
    source_name = "NPPES NPI Registry"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> NppesRecord:
        r = raw.raw
        npi = self._extract_npi(r, "number")
        if not npi:
            raise NormalizationError(self.source_id, f"missing or invalid NPI in raw: {r.get('number')!r}")

        basic: dict[str, Any] = r.get("basic") or {}
        enum_type = r.get("enumeration_type", "NPI-1")
        entity_type = EntityType.ORGANIZATION if enum_type == "NPI-2" else EntityType.INDIVIDUAL

        provenance = self._make_provenance(raw, source_record_id=npi)

        return NppesRecord(
            entity_npi=npi,
            provenance=provenance,
            entity_type=entity_type,
            name=self._extract_name(basic, entity_type),
            organization_name=_nonempty(basic.get("organization_name")),
            other_names=self._extract_other_names(r.get("other_names") or []),
            enumeration_date=self._parse_date(basic.get("enumeration_date")),
            last_updated_date=self._parse_date(basic.get("last_updated")),
            deactivation_date=self._parse_date(_nonempty(basic.get("deactivation_date"))),
            reactivation_date=self._parse_date(_nonempty(basic.get("reactivation_date"))),
            npi_deactivation_reason=_nonempty(basic.get("deactivation_reason"))[:100]
            if _nonempty(basic.get("deactivation_reason")) else None,
            sole_proprietor=_parse_yes_no(basic.get("sole_proprietor")),
            addresses=self._extract_addresses(r.get("addresses") or []),
            taxonomy_codes=self._extract_taxonomies(r.get("taxonomies") or []),
            other_identifiers=self._extract_other_identifiers(r.get("other_identifiers") or []),
        )

    # ------------------------------------------------------------------
    # Private extraction helpers
    # ------------------------------------------------------------------

    def _extract_name(self, basic: dict[str, Any], entity_type: EntityType) -> ProviderName:
        if entity_type == EntityType.ORGANIZATION:
            # Use authorized official if present; fall back to org name stub.
            first = _nonempty(basic.get("authorized_official_first_name")) or ""
            last = (
                _nonempty(basic.get("authorized_official_last_name"))
                or _nonempty(basic.get("organization_name"))
                or "UNKNOWN"
            )
            middle = _nonempty(basic.get("authorized_official_middle_name"))
            credential = _nonempty(basic.get("authorized_official_credential"))
        else:
            first = _nonempty(basic.get("first_name")) or ""
            last = _nonempty(basic.get("last_name")) or "UNKNOWN"
            middle = _nonempty(basic.get("middle_name"))
            credential = _nonempty(basic.get("credential"))

        return ProviderName(
            first=first[:100],
            last=last[:100],
            middle=middle[:100] if middle else None,
            prefix=_nonempty(basic.get("name_prefix")),
            suffix=_nonempty(basic.get("name_suffix")),
            credentials=credential[:100] if credential else None,
        )

    def _extract_other_names(self, other_names: list[dict[str, Any]]) -> list[ProviderName]:
        result: list[ProviderName] = []
        for entry in other_names:
            last = _nonempty(entry.get("last_name"))
            if not last:
                continue
            first = _nonempty(entry.get("first_name")) or ""
            try:
                result.append(ProviderName(
                    first=first[:100],
                    last=last[:100],
                    middle=_nonempty(entry.get("middle_name")),
                    prefix=_nonempty(entry.get("prefix")),
                    suffix=_nonempty(entry.get("suffix")),
                    credentials=_nonempty(entry.get("credential")),
                ))
            except (ValidationError, ValueError):
                continue
        return result

    def _extract_addresses(self, addresses: list[dict[str, Any]]) -> list[Address]:
        result: list[Address] = []
        for addr in addresses:
            state = _nonempty(addr.get("state"))
            if not state or len(state) != 2 or not state.isalpha():
                continue
            zip_code = self._clean_zip(addr.get("postal_code"))
            if not zip_code:
                continue
            street = _nonempty(addr.get("address_1"))
            if not street:
                continue
            city = _nonempty(addr.get("city"))
            if not city:
                continue
            purpose = (addr.get("address_purpose") or "").upper()
            try:
                result.append(Address(
                    street_line_1=street[:200],
                    street_line_2=_nonempty(addr.get("address_2")),
                    city=city[:100],
                    state=state.upper(),
                    postal_code=zip_code,
                    phone=self._clean_phone(addr.get("telephone_number")),
                    fax=self._clean_phone(addr.get("fax_number")),
                    address_type=_ADDRESS_PURPOSE_MAP.get(purpose),
                ))
            except (ValidationError, ValueError):
                continue
        return result

    def _extract_taxonomies(self, taxonomies: list[dict[str, Any]]) -> list[TaxonomyCode]:
        result: list[TaxonomyCode] = []
        for t in taxonomies:
            code = t.get("code") or ""
            desc = t.get("desc") or ""
            if not code or not desc:
                continue
            state = _nonempty(t.get("state"))
            try:
                result.append(TaxonomyCode(
                    code=code.upper()[:10],
                    description=desc[:300],
                    primary=bool(t.get("primary")),
                    license_number=_nonempty(t.get("license")),
                    license_state=state.upper() if state and len(state) == 2 else None,
                ))
            except (ValidationError, ValueError):
                continue
        return result

    @staticmethod
    def _extract_other_identifiers(idents: list[dict[str, Any]]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for entry in idents:
            if isinstance(entry, dict):
                result.append({str(k): str(v) for k, v in entry.items() if v is not None})
        return result


# ---------------------------------------------------------------------------
# I4 specialty-group helper (C13 uses this to populate CanonicalProviderProfile)
# ---------------------------------------------------------------------------


def get_specialty_group(nppes_record: NppesRecord) -> str | None:
    """
    Derive the primary specialty group string from a NppesRecord using the I4 crosswalk.

    Applies the NPPES Specialty Crosswalk (DECISIONS.md Entry 021):
      - Tries the primary taxonomy code first.
      - Falls back to the first taxonomy code with a known crosswalk mapping.
      - Returns None if no taxonomy code matches the crosswalk.

    Called by C13 (Entity Linking & Merge) when building CanonicalProviderProfile.
    """
    # Primary-first pass
    for tc in nppes_record.taxonomy_codes:
        if tc.primary:
            sg = crosswalk_taxonomy_code(tc.code)
            if sg is not None:
                return sg
    # Fallback: first matching code
    for tc in nppes_record.taxonomy_codes:
        sg = crosswalk_taxonomy_code(tc.code)
        if sg is not None:
            return sg
    return None


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _nonempty(s: Any) -> str | None:
    """Return s if it is a non-empty string, else None."""
    if isinstance(s, str) and s.strip():
        return s.strip()
    return None


def _parse_yes_no(s: Any) -> bool | None:
    """Map "Y"/"YES"/"X" -> True, "N"/"NO" -> False, else None."""
    if not isinstance(s, str):
        return None
    v = s.strip().upper()
    if v in ("Y", "YES", "X"):
        return True
    if v in ("N", "NO"):
        return False
    return None

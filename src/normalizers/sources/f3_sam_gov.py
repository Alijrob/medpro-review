"""
f3_sam_gov.py -- SAM.gov Exclusions normalizer (source F3, C11).

Transforms a RawRecord from the SAM.gov adapter into a typed SamExclusionRecord.

NPI handling:
  SAM.gov exclusion records contain no NPI field -- the registry covers all
  federal contractors, not only healthcare providers. entity_npi is therefore
  REQUIRED as a caller-supplied parameter; the normalizer raises NormalizationError
  if it is absent or invalid. Identity-linking (SAM.gov UEI -> NPI) is done by
  C12 (Identity Resolution) upstream of normalization. C11 receives the resolved
  NPI via the entity_npi argument.

Raw structure (DECISIONS.md Entry 017):
  raw["exclusionDetails"]   -- type, program, agency, dates, ctCode, activeExclusion
  raw["entityRegistration"] -- ueiSAM (Unique Entity Identifier), legal name
"""
from __future__ import annotations

from schema.v1.common import SourceCategory
from schema.v1.normalized import SamExclusionRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register


@register
class SamGovNormalizer(SourceNormalizer):
    """Normalizer for SAM.gov Exclusions raw records (F3)."""

    source_id = "F3"
    source_name = "SAM.gov Exclusions"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> SamExclusionRecord:
        npi = self._require_npi(entity_npi, self.source_id)

        r = raw.raw
        details: dict = r.get("exclusionDetails") or {}
        registration: dict = r.get("entityRegistration") or {}

        uei = (registration.get("ueiSAM") or "").strip()
        if not uei:
            raise NormalizationError(self.source_id, "missing entityRegistration.ueiSAM")

        excl_type = (details.get("exclusionType") or "UNKNOWN").strip()
        active_str = (details.get("activeExclusion") or "").strip().upper()
        active = active_str == "Y"

        excl_date = self._parse_date(details.get("exclusionDate"))
        if excl_date is None:
            raise NormalizationError(
                self.source_id, f"unparseable exclusionDate: {details.get('exclusionDate')!r}"
            )

        provenance = self._make_provenance(raw, source_record_id=uei)

        return SamExclusionRecord(
            entity_npi=npi,
            provenance=provenance,
            unique_entity_id=uei[:50],
            exclusion_type=excl_type[:100],
            exclusion_program=_trunc(details.get("exclusionProgram"), 100),
            active_exclusion=active,
            exclusion_date=excl_date,
            exclusion_expiration_date=self._parse_date(details.get("exclusionEndDate")),
            agency=_trunc(
                details.get("excludingAgencyName") or details.get("excludingAgencyCode"),
                100,
            ),
            ct_code=_trunc(details.get("ctCode"), 10),
        )


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None

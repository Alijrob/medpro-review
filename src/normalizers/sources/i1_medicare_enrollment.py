"""
i1_medicare_enrollment.py -- CMS Medicare Enrollment normalizer (source I1, C11).

Transforms RawRecord objects from the CMS Medicare Enrollment adapter into
typed MedicareEnrollmentRecord objects.

The I1 adapter tags each row with raw["_record_type"] to distinguish the
two datasets it fetches in one run (DECISIONS.md Entry 019):

  "enrollment"  -> participating Medicare provider
                   participation_indicator = "Y"
                   specialty_description   = provider_type_desc

  "opt_out"     -> provider who has formally opted out of Medicare
                   participation_indicator = "O"
                   opt_out_effective_date  = parsed optout_effective_date
                   opt_out_end_date        = parsed optout_end_date (if present)

NPI is extracted from raw["npi"] for both record types. The entity_npi
parameter is ignored (NPI is always in the raw for I1).
"""
from __future__ import annotations

from schema.v1.common import SourceCategory
from schema.v1.normalized import MedicareEnrollmentRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register

_RECORD_TYPE_ENROLLMENT = "enrollment"
_RECORD_TYPE_OPT_OUT = "opt_out"


@register
class MedicareEnrollmentNormalizer(SourceNormalizer):
    """Normalizer for CMS Medicare Enrollment raw records (I1)."""

    source_id = "I1"
    source_name = "CMS Medicare Enrollment"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> MedicareEnrollmentRecord:
        r = raw.raw
        npi = self._extract_npi(r, "npi")
        if not npi:
            raise NormalizationError(self.source_id, f"missing or invalid npi: {r.get('npi')!r}")

        record_type = r.get("_record_type", "").strip()
        if record_type not in (_RECORD_TYPE_ENROLLMENT, _RECORD_TYPE_OPT_OUT):
            raise NormalizationError(
                self.source_id,
                f"unknown _record_type: {record_type!r}; expected 'enrollment' or 'opt_out'",
            )

        provenance = self._make_provenance(raw, source_record_id=npi)

        if record_type == _RECORD_TYPE_ENROLLMENT:
            return MedicareEnrollmentRecord(
                entity_npi=npi,
                provenance=provenance,
                participation_indicator="Y",
                opt_out_effective_date=None,
                opt_out_end_date=None,
                specialty_description=_trunc(r.get("provider_type_desc"), 100),
            )
        else:  # opt_out
            opt_out_date = self._parse_date(r.get("optout_effective_date"))
            if opt_out_date is None:
                raise NormalizationError(
                    self.source_id,
                    f"opt_out record has unparseable optout_effective_date: "
                    f"{r.get('optout_effective_date')!r}",
                )
            return MedicareEnrollmentRecord(
                entity_npi=npi,
                provenance=provenance,
                participation_indicator="O",
                opt_out_effective_date=opt_out_date,
                opt_out_end_date=self._parse_date(r.get("optout_end_date")),
                specialty_description=None,
            )


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None

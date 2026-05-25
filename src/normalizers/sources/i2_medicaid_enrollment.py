"""
i2_medicaid_enrollment.py -- CMS Medicaid Enrollment normalizer (source I2, C11).

Transforms a RawRecord from the CMS Medicaid Enrollment adapter into a typed
MedicaidEnrollmentRecord.

The Medicaid enrollment dataset carries only current active enrollments --
every row represents an enrolled provider. enrollment_status is therefore set
to "enrolled" as a normalized constant; no status parsing is required.

state_cd is the critical Medicaid-specific field: Medicaid is state-administered
and state is the primary grouping dimension on the profile.

NPI is extracted from raw["npi"]. The entity_npi parameter is ignored.
"""
from __future__ import annotations

from schema.v1.common import SourceCategory
from schema.v1.normalized import MedicaidEnrollmentRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register


@register
class MedicaidEnrollmentNormalizer(SourceNormalizer):
    """Normalizer for CMS Medicaid Enrollment raw records (I2)."""

    source_id = "I2"
    source_name = "CMS Medicaid Enrollment"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> MedicaidEnrollmentRecord:
        r = raw.raw
        npi = self._extract_npi(r, "npi")
        if not npi:
            raise NormalizationError(self.source_id, f"missing or invalid npi: {r.get('npi')!r}")

        state = _state_or_none(r.get("state_cd"))
        if not state:
            raise NormalizationError(
                self.source_id, f"missing or invalid state_cd: {r.get('state_cd')!r}"
            )

        provenance = self._make_provenance(raw, source_record_id=npi)

        return MedicaidEnrollmentRecord(
            entity_npi=npi,
            provenance=provenance,
            state=state,
            enrollment_status="enrolled",
            enrollment_date=None,    # not in dataset; would require FOIA or state-specific data
            termination_date=None,
            provider_type=_trunc(r.get("provider_type_desc"), 100),
        )


def _state_or_none(s: object) -> str | None:
    if isinstance(s, str) and len(s.strip()) == 2 and s.strip().isalpha():
        return s.strip().upper()
    return None


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None

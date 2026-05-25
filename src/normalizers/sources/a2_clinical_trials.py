"""
a2_clinical_trials.py -- ClinicalTrials.gov normalizer (source A2, C11).

Transforms a RawRecord from the ClinicalTrials.gov adapter into a typed
ClinicalTrialRecord.

Raw structure (DECISIONS.md Entry 023):
  raw["protocolSection"] contains nested sub-modules:
    identificationModule  -- nctId, briefTitle
    statusModule          -- overallStatus, startDateStruct, completionDateStruct
    sponsorCollaboratorsModule -- leadSponsor.name
    conditionsModule      -- conditions (list of strings)
    contactsLocationsModule -- overallOfficials (list of {name, role, affiliation})

NPI handling:
  ClinicalTrials.gov records contain no NPI. entity_npi is required from
  the caller (same pattern as A1 PubMed). Raises NormalizationError if absent.

investigator_role:
  Extracted from protocolSection.contactsLocationsModule.overallOfficials.
  The adapter was queried by investigator name; the first matching official's
  role is used. If overallOfficials is absent (older trials), role is None.

Date handling:
  ClinicalTrials.gov returns dates as {date: "YYYY-MM", type: "ESTIMATED"} or
  {date: "YYYY-MM-DD", type: "ACTUAL"}. Only the date string is parsed.
"""
from __future__ import annotations

from schema.v1.common import SourceCategory
from schema.v1.normalized import ClinicalTrialRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register


@register
class ClinicalTrialsNormalizer(SourceNormalizer):
    """Normalizer for ClinicalTrials.gov raw records (A2)."""

    source_id = "A2"
    source_name = "ClinicalTrials.gov"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> ClinicalTrialRecord:
        npi = self._require_npi(entity_npi, self.source_id)

        r = raw.raw
        protocol = r.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        status_mod = protocol.get("statusModule") or {}
        sponsor_mod = protocol.get("sponsorCollaboratorsModule") or {}
        conditions_mod = protocol.get("conditionsModule") or {}
        contacts_mod = protocol.get("contactsLocationsModule") or {}

        nct_id = (ident.get("nctId") or "").strip()
        if not nct_id:
            raise NormalizationError(self.source_id, "missing protocolSection.identificationModule.nctId")

        title = (ident.get("briefTitle") or ident.get("officialTitle") or "").strip()
        if not title:
            raise NormalizationError(self.source_id, f"missing title for NCT ID {nct_id!r}")

        status = (status_mod.get("overallStatus") or "UNKNOWN").strip()

        # dates: may be {date: "...", type: "..."} or absent
        start_date = self._parse_date(_date_str(status_mod.get("startDateStruct")))
        completion_date = self._parse_date(_date_str(status_mod.get("completionDateStruct")))

        # sponsor
        lead_sponsor = sponsor_mod.get("leadSponsor") or {}
        sponsor_name = _trunc(lead_sponsor.get("name"), 200)

        # condition: take the first condition listed
        conditions = conditions_mod.get("conditions") or []
        condition = _trunc(conditions[0], 200) if conditions else None

        # investigator role from overallOfficials
        investigator_role = _extract_role(contacts_mod.get("overallOfficials") or [])

        provenance = self._make_provenance(raw, source_record_id=nct_id)

        return ClinicalTrialRecord(
            entity_npi=npi,
            provenance=provenance,
            nct_id=nct_id,
            title=title[:1000],
            status=status[:50],
            sponsor=sponsor_name,
            investigator_role=investigator_role,
            start_date=start_date,
            completion_date=completion_date,
            condition=condition,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None


def _date_str(d: object) -> str | None:
    """Extract the date string from a ClinicalTrials.gov date struct dict."""
    if isinstance(d, dict):
        return d.get("date")
    return None


def _extract_role(officials: list) -> str | None:
    """Return the role string of the first official, or None if empty."""
    for official in officials:
        if isinstance(official, dict):
            role = (official.get("role") or "").strip()
            if role:
                return role[:100]
    return None

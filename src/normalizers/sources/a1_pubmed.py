"""
a1_pubmed.py -- PubMed / NCBI Entrez normalizer (source A1, C11).

Transforms a RawRecord from the PubMed adapter into a typed PubMedRecord.

NPI handling:
  PubMed records contain no NPI. Disambiguation (which publications belong to
  the target provider vs. a namesake author) is a C12/C13 concern. For C11
  normalization the caller supplies the entity_npi that the adapter was run for.
  Raises NormalizationError if entity_npi is absent or invalid.

Author position:
  Determining whether the target author is first/last/middle author requires
  knowing the target author's name and matching it within raw["authors"]. This
  is a name-disambiguation concern deferred to C13. author_position is set to
  None in the MVP normalization pass.

pubdate parsing:
  NCBI esummary returns pubdate as a free-text string (e.g., "2022 Jan",
  "2022", "2022 Jan 15"). _parse_date() handles the year-only and year+month
  formats. The parsed date is stored as publication_date; publication_year is
  extracted from it.
"""
from __future__ import annotations

from schema.v1.common import SourceCategory
from schema.v1.normalized import PubMedRecord
from connectors.models import RawRecord

from ..base import NormalizationError, SourceNormalizer
from ..registry import register


@register
class PubmedNormalizer(SourceNormalizer):
    """Normalizer for PubMed raw records (A1)."""

    source_id = "A1"
    source_name = "PubMed / NCBI Entrez"
    source_category = SourceCategory.FEDERAL

    def normalize(self, raw: RawRecord, *, entity_npi: str | None = None) -> PubMedRecord:
        npi = self._require_npi(entity_npi, self.source_id)

        r = raw.raw
        pmid = (r.get("uid") or "").strip()
        if not pmid:
            raise NormalizationError(self.source_id, "missing uid (PMID) in raw")

        title = (r.get("title") or "").strip()
        if not title:
            raise NormalizationError(self.source_id, f"missing title for PMID {pmid!r}")

        pub_date = self._parse_date(r.get("pubdate"))
        pub_year = pub_date.year if pub_date else None

        # journal: prefer full name, fall back to abbreviated source
        journal = _trunc(r.get("fulljournalname") or r.get("source"), 200)

        # DOI: may appear in "elocationid" or in "articleids" list
        doi = _extract_doi(r)

        provenance = self._make_provenance(raw, source_record_id=pmid)

        return PubMedRecord(
            entity_npi=npi,
            provenance=provenance,
            pmid=pmid[:20],
            title=title[:1000],
            journal=journal,
            publication_date=pub_date,
            publication_year=pub_year,
            doi=doi,
            citation_count=None,          # not available from esummary; Phase 3+ via Entrez link
            author_position=None,         # disambiguation deferred to C13
            abstract_snippet=None,        # esummary does not return abstract text
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trunc(s: object, max_len: int) -> str | None:
    if isinstance(s, str) and s.strip():
        return s.strip()[:max_len]
    return None


def _extract_doi(r: dict) -> str | None:
    """Extract DOI from elocationid or articleids list."""
    # elocationid is a string like "10.1056/NEJMoa2026766 [doi]"
    eloc = r.get("elocationid") or ""
    if isinstance(eloc, str) and "[doi]" in eloc.lower():
        doi = eloc.lower().replace("[doi]", "").strip()
        return doi[:200] if doi else None
    # articleids is a list of {idtype, value} dicts
    for entry in (r.get("articleids") or []):
        if isinstance(entry, dict) and entry.get("idtype", "").lower() == "doi":
            doi = (entry.get("value") or "").strip()
            return doi[:200] if doi else None
    return None

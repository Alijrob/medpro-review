"""
resolver.py -- IdentityResolver for the C12 Identity Resolution Engine (Phase 2-E).

Builds and maintains UnifiedIdBundle objects by resolving NormalizedRecord
objects against the IdentityStore. The primary matching strategy is
NPI-exact-match: every NormalizedRecord produced by C11 has entity_npi set,
so there is always a lookup key.

Design (DECISIONS.md Entry 026):
---------------------------------

  1. NPI-exact-match only (MVP).
     Probabilistic/ML matching (Splink) is deferred to Phase 3-I.

  2. F1 (NPPES) is the identity anchor.
     When F1 is the first record for an NPI, the full identity (name,
     entity_type, addresses, taxonomies, other_identifiers) is extracted
     from it. When F1 arrives for a bundle that was seeded by another
     source, it upgrades the primary identity fields.

  3. Idempotency.
     Resolving a source that is already in contributing_sources is a no-op
     (ResolutionAction.SKIPPED). This guards against double-processing.

  4. Batch ordering.
     resolve_batch() sorts F1 records first so the identity anchor is
     established before corroborating records are merged.

  5. Non-F1 first records.
     When a non-F1 record is the first for an NPI, a minimal stub bundle is
     created (best-available name, entity_type=INDIVIDUAL default) with
     human_review_required=True. The reviewer resolves once F1 data lands.
"""
from __future__ import annotations

from schema.v1.common import EntityType, Gender, ProviderName, TaxonomyCode, Address, utc_now
from schema.v1.identity import OtherIdentifier, UnifiedIdBundle
from schema.v1.normalized import (
    NormalizedRecord,
    NppesRecord,
    OigLeieRecord,
)

from .confidence import ConfidenceScorer
from .config import IdentitySettings
from .models import BatchResolutionSummary, ResolutionAction, ResolutionResult
from .store import IdentityStore


class IdentityResolver:
    """
    NPI-first identity resolver (C12 MVP).

    Resolves a NormalizedRecord to a UnifiedIdBundle:
      - If no bundle exists for the record's entity_npi: creates one.
      - If a bundle exists: merges the new source's contribution in.
      - If the source is already in contributing_sources: skips (idempotent).

    The resolver is stateless with respect to the bundle data; all state
    lives in the injected IdentityStore.
    """

    def __init__(
        self,
        store: IdentityStore | None = None,
        scorer: ConfidenceScorer | None = None,
        settings: IdentitySettings | None = None,
    ) -> None:
        self._settings = settings or IdentitySettings()
        self._store = store or IdentityStore()
        self._scorer = scorer or ConfidenceScorer(self._settings)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def store(self) -> IdentityStore:
        """Expose the backing store (read-only access for callers)."""
        return self._store

    def resolve(self, record: NormalizedRecord) -> ResolutionResult:
        """
        Resolve a single NormalizedRecord.

        Returns a ResolutionResult with the current (post-resolution)
        UnifiedIdBundle state and the action taken.
        """
        npi = record.entity_npi
        existing = self._store.get(npi)

        if existing is None:
            bundle = self._create_bundle(record)
            self._store.put(bundle)
            return ResolutionResult(
                bundle=bundle,
                action=ResolutionAction.CREATED,
                record_id=record.record_id,
                source_id=record.provenance.source_id,
                provider_npi=npi,
                confidence_before=None,
                confidence_after=bundle.identity_confidence,
            )

        source_id = record.provenance.source_id
        if source_id in existing.contributing_sources:
            return ResolutionResult(
                bundle=existing,
                action=ResolutionAction.SKIPPED,
                record_id=record.record_id,
                source_id=source_id,
                provider_npi=npi,
                confidence_before=existing.identity_confidence,
                confidence_after=existing.identity_confidence,
            )

        confidence_before = existing.identity_confidence
        updated = self._merge_record(existing, record)
        self._store.put(updated)
        return ResolutionResult(
            bundle=updated,
            action=ResolutionAction.MERGED,
            record_id=record.record_id,
            source_id=source_id,
            provider_npi=npi,
            confidence_before=confidence_before,
            confidence_after=updated.identity_confidence,
        )

    def resolve_batch(self, records: list[NormalizedRecord]) -> BatchResolutionSummary:
        """
        Resolve a list of NormalizedRecords.

        F1 records are sorted first within the batch so the identity anchor
        is established before corroborating records attempt to merge.
        Returns a BatchResolutionSummary with per-record results and totals.
        """
        sorted_records = sorted(
            records,
            key=lambda r: (0 if r.provenance.source_id == "F1" else 1),
        )

        results: list[ResolutionResult] = []
        for record in sorted_records:
            results.append(self.resolve(record))

        created = sum(1 for r in results if r.action == ResolutionAction.CREATED)
        merged = sum(1 for r in results if r.action == ResolutionAction.MERGED)
        skipped = sum(1 for r in results if r.action == ResolutionAction.SKIPPED)
        unique_npis = len({r.provider_npi for r in results})
        bundles_requiring_review = sum(
            1 for b in self._store.get_all() if b.human_review_required
        )

        return BatchResolutionSummary(
            total_records=len(results),
            created=created,
            merged=merged,
            skipped=skipped,
            bundles_requiring_review=bundles_requiring_review,
            unique_npis=unique_npis,
            results=results,
        )

    # ------------------------------------------------------------------
    # Bundle creation
    # ------------------------------------------------------------------

    def _create_bundle(self, record: NormalizedRecord) -> UnifiedIdBundle:
        """
        Create a new UnifiedIdBundle from the first record seen for an NPI.

        F1 (NppesRecord): full identity extraction -- authoritative name,
          entity_type, addresses, taxonomies, other_identifiers.
        All others: minimal stub -- best-available name, entity_type defaults
          to INDIVIDUAL, human_review_required = True.
        """
        source_id = record.provenance.source_id
        sources = [source_id]
        confidence = self._scorer.score(sources)
        human_review = self._scorer.requires_human_review(confidence)

        if isinstance(record, NppesRecord):
            return UnifiedIdBundle(
                primary_npi=record.entity_npi,
                entity_type=record.entity_type,
                primary_name=record.name,
                name_variants=list(record.other_names),
                gender=Gender.UNKNOWN,  # gender not yet on NppesRecord; deferred to C13
                primary_specialty=_primary_taxonomy(record.taxonomy_codes),
                all_taxonomies=list(record.taxonomy_codes),
                known_addresses=list(record.addresses),
                other_identifiers=_convert_nppes_other_ids(record.other_identifiers),
                contributing_sources=sources,
                identity_confidence=confidence,
                human_review_required=human_review,
            )

        # Non-F1: minimal stub bundle. Upgraded when F1 arrives.
        name_hint = _extract_name_hint(record) or ProviderName(first="", last="UNKNOWN")
        return UnifiedIdBundle(
            primary_npi=record.entity_npi,
            entity_type=EntityType.INDIVIDUAL,  # best guess; F1 will correct if org
            primary_name=name_hint,
            name_variants=[],
            gender=Gender.UNKNOWN,
            primary_specialty=None,
            all_taxonomies=[],
            known_addresses=[],
            other_identifiers=[],
            contributing_sources=sources,
            identity_confidence=confidence,
            human_review_required=True,  # F1 not yet seen; always flag
        )

    # ------------------------------------------------------------------
    # Bundle merge
    # ------------------------------------------------------------------

    def _merge_record(self, bundle: UnifiedIdBundle, record: NormalizedRecord) -> UnifiedIdBundle:
        """
        Merge a new NormalizedRecord into an existing bundle.

        For F1: upgrades the primary identity fields (name, entity_type,
          addresses, taxonomies). The prior primary_name is moved to
          name_variants if it differs from the F1 name.
        For all others: adds to contributing_sources, recalculates confidence.
          No identity fields are overwritten by non-F1 sources.
        """
        source_id = record.provenance.source_id
        new_sources = [*bundle.contributing_sources, source_id]
        new_confidence = self._scorer.score(new_sources)
        new_human_review = self._scorer.requires_human_review(new_confidence)

        if isinstance(record, NppesRecord):
            return self._merge_f1(bundle, record, new_sources, new_confidence, new_human_review)

        # For non-F1: accumulate name hints into name_variants, recalc confidence.
        new_name_variants = list(bundle.name_variants)
        hint = _extract_name_hint(record)
        if hint is not None and _name_key(hint) not in {_name_key(n) for n in new_name_variants}:
            if _name_key(hint) != _name_key(bundle.primary_name):
                new_name_variants.append(hint)

        return bundle.model_copy(update={
            "contributing_sources": new_sources,
            "name_variants": new_name_variants,
            "identity_confidence": new_confidence,
            "human_review_required": new_human_review,
            "updated_at": utc_now(),
        })

    def _merge_f1(
        self,
        bundle: UnifiedIdBundle,
        record: NppesRecord,
        new_sources: list[str],
        new_confidence: float,
        new_human_review: bool,
    ) -> UnifiedIdBundle:
        """
        Merge an F1 (NppesRecord) into a bundle that was seeded by another source.

        F1 is the identity anchor: it takes over primary_name, entity_type,
        addresses, and taxonomies. The prior stub primary_name is preserved as
        a name_variant (if it differs and is non-trivial).
        """
        # Preserve any existing name variants + the prior stub primary (if meaningful).
        existing_variants = set(_name_key(n) for n in bundle.name_variants)
        prior_primary_key = _name_key(bundle.primary_name)
        f1_primary_key = _name_key(record.name)

        new_name_variants: list[ProviderName] = []

        # Keep prior primary as a variant if it is non-stub and different from F1 name.
        if prior_primary_key != f1_primary_key and not _is_stub_name(bundle.primary_name):
            new_name_variants.append(bundle.primary_name)
            existing_variants.add(prior_primary_key)

        # Add existing variants (dedup against F1 primary).
        for v in bundle.name_variants:
            k = _name_key(v)
            if k != f1_primary_key and k not in existing_variants:
                new_name_variants.append(v)
                existing_variants.add(k)

        # Add F1's own other_names (former names, DBAs).
        for v in record.other_names:
            k = _name_key(v)
            if k != f1_primary_key and k not in existing_variants:
                new_name_variants.append(v)
                existing_variants.add(k)

        # Merge addresses: dedup by (street_line_1 lower, postal_code).
        new_addresses = _merge_addresses(list(bundle.known_addresses), record.addresses)

        # Convert NPPES other_identifiers from raw dict form to OtherIdentifier objects.
        new_other_ids = _convert_nppes_other_ids(record.other_identifiers)

        return bundle.model_copy(update={
            "entity_type": record.entity_type,
            "primary_name": record.name,
            "name_variants": new_name_variants,
            "primary_specialty": _primary_taxonomy(record.taxonomy_codes),
            "all_taxonomies": list(record.taxonomy_codes),
            "known_addresses": new_addresses,
            "other_identifiers": new_other_ids,
            "contributing_sources": new_sources,
            "identity_confidence": new_confidence,
            "human_review_required": new_human_review,
            "updated_at": utc_now(),
        })


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _primary_taxonomy(taxonomy_codes: list[TaxonomyCode]) -> TaxonomyCode | None:
    """Return the first taxonomy code marked primary=True, or the first code overall."""
    for tc in taxonomy_codes:
        if tc.primary:
            return tc
    return taxonomy_codes[0] if taxonomy_codes else None


def _convert_nppes_other_ids(raw_ids: list[dict[str, str]]) -> list[OtherIdentifier]:
    """
    Convert NPPES raw other_identifier dicts to typed OtherIdentifier objects.

    NPPES other_identifiers entries have keys like:
      {"identifier": "...", "type": "...", "state": "...", "issuer": "..."}
    """
    result: list[OtherIdentifier] = []
    for entry in raw_ids:
        id_type = entry.get("type") or entry.get("identifier_type")
        id_value = entry.get("identifier") or entry.get("identifier_value")
        if not id_type or not id_value:
            continue
        state = entry.get("state")
        issuer = entry.get("issuer")
        try:
            result.append(OtherIdentifier(
                identifier_type=str(id_type)[:50],
                identifier_value=str(id_value)[:100],
                state=str(state)[:2] if state else None,
                issuer=str(issuer)[:100] if issuer else None,
            ))
        except Exception:
            continue
    return result


def _extract_name_hint(record: NormalizedRecord) -> ProviderName | None:
    """
    Extract the best available name from a non-F1 NormalizedRecord, if any.

    Returns None for record types that carry no name information at all.
    Returns a ProviderName stub for records with partial name fields.
    """
    if isinstance(record, OigLeieRecord):
        first = record.reported_first_name or ""
        last = record.reported_last_name
        if last:
            return ProviderName(first=first[:100], last=last[:100])
    # All other P1 record types (F3/F4/I1/I2/A1/A2) carry no individual name.
    # Return None; the resolver will keep the stub as-is.
    return None


def _name_key(name: ProviderName) -> str:
    """Deduplication key: normalized first:last tokens (lowercase, stripped)."""
    return f"{name.first.strip().lower()}:{name.last.strip().lower()}"


def _is_stub_name(name: ProviderName) -> bool:
    """True when the name is the placeholder stub created for non-F1 first records."""
    return name.last.upper() == "UNKNOWN" and name.first.strip() == ""


def _merge_addresses(existing: list[Address], incoming: list[Address]) -> list[Address]:
    """
    Merge address lists, deduplicating by (street_line_1.lower(), postal_code).

    Existing addresses are preserved as-is; incoming addresses are appended
    only if they are not already represented.
    """
    seen: set[tuple[str, str]] = {
        (a.street_line_1.lower(), a.postal_code) for a in existing
    }
    result = list(existing)
    for addr in incoming:
        key = (addr.street_line_1.lower(), addr.postal_code)
        if key not in seen:
            result.append(addr)
            seen.add(key)
    return result

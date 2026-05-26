"""
store.py -- IdentityStore for the C12 Identity Resolution Engine.

In-memory bundle storage for the MVP. Will be backed by Aurora PostgreSQL
(unified_id_bundles table, migration 0001) once Entry 003 is resolved.

The store is the single source of truth for which UnifiedIdBundles are
currently known. The IdentityResolver reads and writes exclusively through
the store, so swapping the in-memory implementation for an Aurora-backed
one only requires replacing this module.
"""
from __future__ import annotations

from schema.v1.identity import UnifiedIdBundle


class IdentityStore:
    """
    In-memory store for UnifiedIdBundles, keyed by primary_npi.

    Thread-safety: not thread-safe. When adapters run in parallel (Phase 2-H
    Temporal workers), a lock or Aurora-backed atomic upsert replaces this.

    Aurora path (deferred to Entry 003):
      - SELECT ... WHERE primary_npi = $1 FOR UPDATE (row-level lock per NPI)
      - INSERT ... ON CONFLICT (primary_npi) DO UPDATE ...
      - All history in updated_at / last_full_refresh_at
    """

    def __init__(self) -> None:
        self._bundles: dict[str, UnifiedIdBundle] = {}

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(self, npi: str) -> UnifiedIdBundle | None:
        """Return the bundle for this NPI, or None if not found."""
        return self._bundles.get(npi)

    def get_all(self) -> list[UnifiedIdBundle]:
        """Return all bundles as a list (order is insertion order in CPython 3.7+)."""
        return list(self._bundles.values())

    def list_npis(self) -> list[str]:
        """Return all NPIs currently tracked by the store."""
        return list(self._bundles.keys())

    def __len__(self) -> int:
        return len(self._bundles)

    def __contains__(self, npi: str) -> bool:
        return npi in self._bundles

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def put(self, bundle: UnifiedIdBundle) -> None:
        """
        Upsert a bundle by primary_npi.

        Replaces any existing bundle for the same NPI unconditionally.
        The caller (IdentityResolver) is responsible for merging state
        before calling put().
        """
        self._bundles[bundle.primary_npi] = bundle

    def remove(self, npi: str) -> None:
        """Remove a bundle by NPI. No-op if not found."""
        self._bundles.pop(npi, None)

    def clear(self) -> None:
        """Remove all bundles. Useful for test reset."""
        self._bundles.clear()

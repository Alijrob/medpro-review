"""
indexer.py -- ProviderIndexer: indexes CanonicalProviderProfiles into OpenSearch (C14).

ProviderIndexer is a thin coordinator:
  1. Calls document.build_provider_doc() (pure, no I/O) to convert the profile.
  2. Calls client.index_doc() or client.bulk_index() to write to OpenSearch.
  3. Returns a typed IndexResult or BatchIndexResult.

The indexer is not a singleton -- callers create one per target index name.
The OpenSearchClient is injected, making the indexer trivially testable with
a mock client (no network needed in tests).

Phase 2-H Temporal workflow will call index_profile() as a Temporal activity
after each EntityLinker.build_profile() completes.
"""
from __future__ import annotations

import logging

from schema.v1.profile import CanonicalProviderProfile

from .client import OpenSearchClient
from .document import build_provider_doc
from .models import BatchIndexResult, IndexResult

logger = logging.getLogger(__name__)


class ProviderIndexer:
    """
    Coordinates the build_provider_doc -> OpenSearchClient write path.

    Usage:
        indexer = ProviderIndexer(index_name="providers-dev")
        result  = indexer.index_profile(profile, client)
        batch   = indexer.index_batch(profiles, client)
    """

    def __init__(self, index_name: str) -> None:
        self.index_name = index_name

    # ------------------------------------------------------------------
    # Single-document path
    # ------------------------------------------------------------------

    def index_profile(
        self,
        profile: CanonicalProviderProfile,
        client: OpenSearchClient,
    ) -> IndexResult:
        """
        Build a ProviderDoc from `profile` and write it to OpenSearch.

        Returns IndexResult(success=True) on success, IndexResult(success=False,
        error=...) when the client returns an error -- never raises.
        """
        doc = build_provider_doc(profile)
        raw = client.index_doc(
            index=self.index_name,
            doc_id=profile.npi,
            body=doc.model_dump(mode="json"),
        )
        return IndexResult(
            npi=profile.npi,
            success=raw.success,
            index_name=self.index_name,
            result=raw.result,
            error=raw.error,
        )

    # ------------------------------------------------------------------
    # Bulk path
    # ------------------------------------------------------------------

    def index_batch(
        self,
        profiles: list[CanonicalProviderProfile],
        client: OpenSearchClient,
    ) -> BatchIndexResult:
        """
        Build ProviderDocs for all `profiles` and write them in one bulk request.

        When the bulk request reports no errors, all documents are counted as
        succeeded. When errors is True, the per-item results in `items` are
        parsed to separate succeeded from failed (by-NPI error reporting).

        Empty list -> BatchIndexResult(total=0, succeeded=0, failed=0) (no request sent).
        """
        if not profiles:
            return BatchIndexResult(total=0, succeeded=0, failed=0)

        # Build all documents first (pure, no I/O)
        docs: list[tuple[str, dict]] = [
            (p.npi, build_provider_doc(p).model_dump(mode="json")) for p in profiles
        ]

        raw = client.bulk_index(index=self.index_name, docs=docs)

        if not raw.errors:
            return BatchIndexResult(
                total=len(profiles),
                succeeded=len(profiles),
                failed=0,
            )

        # Parse per-item errors from the bulk response
        npi_list = [p.npi for p in profiles]
        failures: list[IndexResult] = []
        succeeded = 0

        for i, item in enumerate(raw.items):
            npi = npi_list[i] if i < len(npi_list) else "unknown"
            action = item.get("index", {})
            if action.get("error"):
                failures.append(
                    IndexResult(
                        npi=npi,
                        success=False,
                        index_name=self.index_name,
                        result="error",
                        error=str(action["error"]),
                    )
                )
            else:
                succeeded += 1

        logger.warning(
            "bulk_index partial failure index=%s succeeded=%d failed=%d",
            self.index_name,
            succeeded,
            len(failures),
        )

        return BatchIndexResult(
            total=len(profiles),
            succeeded=succeeded,
            failed=len(failures),
            failures=failures,
        )

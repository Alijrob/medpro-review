"""
sam_gov.py -- SAM.gov Exclusions adapter (source F3, component C10, Phase 2-B.3).

SAM.gov is the U.S. federal government's System for Award Management. Its exclusions
list is the authoritative federal debarment/suspension registry: individuals and entities
barred from doing business with the federal government appear here. For healthcare provider
vetting it complements LEIE (F2) -- some providers appear on SAM but not LEIE (and vice
versa), so checking both lists is required for complete exclusion coverage.

Mode: **REST API (paginated)** -- the SAM.gov Entity Management exclusions endpoint
(`/entity-information/v3/exclusions`). The API is free with a self-service API key
from SAM.gov (CC0/public domain, T1/L0). Paginates through all active exclusion records
using `page` + `size` query params; `totalRecords` from the first response determines
pagination depth. Each yielded record is one `entityData` item (one excluded
entity/individual). Delta-sync mode (incremental via `updatedDate` filter) is a
deferred follow-on once full re-pages become operationally expensive.

Output is `RawRecord`s (one per exclusion, pre-normalization). Mapping SAM.gov exclusion
records into typed exclusion signals on a `CanonicalProviderProfile` is C11 (Normalization
Layer, Phase 2-D) -- this adapter deliberately does no normalization beyond a schema-drift
contract check.

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing here
hits the network on import; tests drive it with a stubbed transport. Running it against
the live SAM.gov endpoint is a deploy-time action behind that gate. F3 is T1/L0
open-data (CC0/public domain -- U.S. Government Work per 17 U.S.C. § 105).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ..base import SourceConnector
from ..config import ConnectorConfig
from ..contract import SchemaContract
from ..errors import SourceUnavailableError
from ..models import IntegrationMethod

DEFAULT_BASE_URL = "https://api.sam.gov"
EXCLUSIONS_PATH = "/entity-information/v3/exclusions"
# SAM.gov supports up to 100 records per page on the exclusions endpoint.
PAGE_SIZE = 100

# Top-level keys in each entityData item from the SAM.gov exclusions response.
# exclusionDetails carries the exclusion fact (type, date, agency, NPI link).
# entityRegistration carries identity (UEI, legal name, CAGE code).
# Guarding both dicts fires the R6 alarm if SAM.gov restructures its response
# shape -- e.g., flattens the nested structure or renames a top-level section.
# Inner keys within each dict (exclusionType, exclusionDate, ueiSAM, etc.) are
# not guarded here; their mapping is C11 normalization (Phase 2-D).
_SAM_REQUIRED_FIELDS = frozenset({"exclusionDetails", "entityRegistration"})


def sam_gov_config(**overrides: Any) -> ConnectorConfig:
    """Build the F3 ConnectorConfig (identity + operational defaults).

    The ``api_key`` is NOT stored in ConnectorConfig -- secrets are passed at
    construction time, never baked into config (per the connector framework
    convention). Pass it to ``SamGovConnector(config, api_key=...)``.

    The ``expected_min_records`` default is None (no threshold enforced). In
    production, set it to a value consistent with the SAM.gov exclusions dataset
    (currently ~80 000 active exclusions) so a truncated run surfaces as PARTIAL
    rather than a silent short run.
    Example: ``sam_gov_config(expected_min_records=70_000)``.
    """
    params: dict[str, Any] = dict(
        source_id="F3",
        source_name="SAM.gov Exclusions",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (SAM.gov Exclusions F3)",
        # SAM.gov enforces API rate limits; 2 req/s is a courteous floor for a
        # paginated batch run that may issue hundreds of requests for a full ingest.
        rate_limit_per_sec=2.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class SamGovConnector(SourceConnector):
    """SAM.gov Exclusions REST API adapter (F3).

    Pages through ``/entity-information/v3/exclusions`` with ``api_key`` + ``page``
    + ``size``, yielding one dict per ``entityData`` item (one excluded entity).
    ``run()`` (inherited) wraps each item in a provenance-hashed ``RawRecord``,
    validates it against ``contract``, and emits a ``SourceHealthRecord`` for the
    Source Health Monitor (C24).

    The ``api_key`` is passed at construction time (not baked into
    ``ConnectorConfig``). In deployed environments it comes from External Secrets
    Operator / Secrets Manager wired to the workers-sa IRSA role.

    Pagination terminates when:
    - The current page returns an empty ``entityData`` list (explicit sentinel from
      the source), OR
    - ``(page + 1) * page_size >= totalRecords`` (all known records fetched).

    If ``totalRecords`` is absent from the response, pagination relies solely on
    the empty-page sentinel -- a safe fallback that avoids an infinite loop.

    Deferred: delta-sync mode (daily incremental using an ``updatedDate`` filter
    to fetch only new/changed exclusions since the last full run). For the initial
    build and MVP, a full re-page is sufficient; the delta path lands once data
    volume makes full re-pages operationally expensive.
    """

    contract = SchemaContract(
        required_fields=_SAM_REQUIRED_FIELDS,
        field_types={
            "exclusionDetails": dict,
            "entityRegistration": dict,
        },
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        api_key: str,
        page_size: int = PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._api_key = api_key
        self._page_size = page_size

    def _params(self, page: int) -> dict[str, Any]:
        """Build query params for a given page number (0-indexed)."""
        return {
            "api_key": self._api_key,
            "page": page,
            "size": self._page_size,
        }

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through the SAM.gov exclusions endpoint, yielding one dict per item."""
        page = 0
        total: int | None = None  # set from first response; None = fall back to empty-page stop

        while True:
            resp = await self.request("GET", EXCLUSIONS_PATH, params=self._params(page))
            body = self._parse_body(resp)

            # Capture totalRecords from the first response only.
            if total is None:
                raw_total = body.get("totalRecords")
                if raw_total is not None:
                    try:
                        total = int(raw_total)
                    except (TypeError, ValueError):
                        pass  # leave as None -- use empty-page stop only

            entity_data: list[dict[str, Any]] = body.get("entityData") or []
            for item in entity_data:
                yield item

            # Termination: empty page or all known records fetched.
            if not entity_data:
                break
            if total is not None and (page + 1) * self._page_size >= total:
                break
            page += 1

    def _parse_body(self, resp: Any) -> dict[str, Any]:
        """Extract the JSON response dict or raise SourceUnavailableError."""
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from SAM.gov: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected SAM.gov response shape: {type(body).__name__}"
            )
        return body

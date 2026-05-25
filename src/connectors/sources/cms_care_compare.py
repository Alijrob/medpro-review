"""
cms_care_compare.py -- CMS Care Compare / Provider Data adapter
(source F4, component C10, Phase 2-B.4).

CMS Care Compare is the public-facing Medicare provider data platform. The
underlying dataset -- "Doctors and Clinicians" (the Physician Compare national
downloadable file) -- contains NPI-level records for every provider who has billed
Medicare: name, primary specialty, practice address, hospital affiliations, group
practice membership, and the accepts-assignment flag (whether the provider accepts
Medicare's approved amount as payment in full). This is the highest-value publicly
available dataset for building the participation and location layers of a provider
report: it links NPI (F1 identity anchor) to specialty, address, affiliations,
and Medicare acceptance status. The dataset is CC0/public domain (T1/L0).

Mode: **paginated REST API** via the Socrata SODA 2.0 API on `data.cms.gov`. The
SODA API serves JSON arrays with no API key required for public datasets. Pagination
uses `$limit` + `$offset` + `$order=:id` (Socrata's internal row ID -- the only
stable key for deterministic pagination across large datasets). Termination fires
when the response array is shorter than `$limit` (the short-page sentinel: the
source is exhausted).

The dataset contains **one row per practice location per NPI** -- a provider with
five practice locations yields five rows with the same NPI but different addresses.
C11 normalization (Phase 2-D) groups and deduplicates rows by NPI. This adapter
yields all rows as-is.

The `dataset_id` is configurable to support future updates (CMS periodically
refreshes or supersedes datasets). The default is the Doctors and Clinicians
national downloadable file; override at construction if the dataset ID changes.

Output is `RawRecord`s (one per dataset row, pre-normalization). Turning CMS rows
into typed affiliation/participation signals on a `CanonicalProviderProfile` is C11.

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing
here hits the network on import; tests drive it with a stubbed transport. Running
it against the live CMS endpoint is a deploy-time action behind that gate. F4 is
T1/L0 open-data (CC0 license, explicitly noted on data.cms.gov/provider-data).
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

DEFAULT_BASE_URL = "https://data.cms.gov"
# "Doctors and Clinicians" -- the Physician Compare national downloadable file.
# If CMS supersedes this dataset, override at construction: CmsCareCompareConnector(
#   cms_care_compare_config(), dataset_id="new-id")
DEFAULT_DATASET_ID = "mj5m-pzi6"
# Socrata allows up to 50 000 per request; 5 000 is conservative and keeps
# individual requests from timing out on slow links.
PAGE_LIMIT = 5_000

# Key fields expected in every CMS Care Compare row.
# Guards identity-link (npi), CMS-specific identity (ind_pac_id), provider name
# (last_name), clinical signal (pri_spec -- primary specialty), participation
# (assgn -- accepts Medicare assignment), and practice location (cty, st, zip).
# first_name is guarded because it anchors identity resolution when NPIs collide.
# Rows with multiple practice locations all share the same NPI; downstream C11
# normalization groups by NPI. One-row-per-location is the intended schema.
_CMS_REQUIRED_FIELDS = frozenset({
    "npi",
    "ind_pac_id",
    "last_name",
    "first_name",
    "pri_spec",
    "assgn",
    "cty",
    "st",
})


def cms_care_compare_config(**overrides: Any) -> ConnectorConfig:
    """Build the F4 ConnectorConfig (identity + operational defaults).

    No API key is needed -- the data.cms.gov SODA API is publicly accessible
    without authentication. An optional `X-App-Token` header would raise the
    rate limit ceiling, but unauthenticated access is sufficient for a single
    scheduled monthly ingest.

    The ``expected_min_records`` default is None. In production, set it to a
    value consistent with the CMS physician dataset size (currently ~3 million
    rows, one per practice location) to detect truncated ingest runs.
    Example: ``cms_care_compare_config(expected_min_records=2_000_000)``.
    """
    params: dict[str, Any] = dict(
        source_id="F4",
        source_name="CMS Care Compare",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (CMS Care Compare F4)",
        # data.cms.gov does not publish a rate limit for unauthenticated SODA
        # access; 5 req/s is conservative and leaves headroom for other traffic.
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class CmsCareCompareConnector(SourceConnector):
    """CMS Care Compare (Physicians & Other Clinicians) adapter (F4).

    Pages through the Socrata SODA API at `data.cms.gov` using `$limit`,
    `$offset`, and `$order=:id`, yielding one dict per dataset row. ``run()``
    (inherited) wraps each row in a provenance-hashed ``RawRecord``, validates
    it against ``contract``, and emits a ``SourceHealthRecord`` for the Source
    Health Monitor (C24).

    **Termination:** the loop stops when the response array is shorter than
    ``$limit`` (the short-page sentinel -- Socrata returns exactly as many
    records as remain, never padding). An empty response array also terminates.

    **One row per practice location:** the Doctors and Clinicians dataset has
    one row per NPI per practice address. Grouping multiple rows for the same
    NPI is C11 normalization (Phase 2-D), not this adapter's responsibility.

    The ``dataset_id`` defaults to ``DEFAULT_DATASET_ID``; pass a different ID
    at construction if CMS supersedes the dataset.
    """

    contract = SchemaContract(
        required_fields=_CMS_REQUIRED_FIELDS,
        field_types={
            "npi": str,
            "ind_pac_id": str,
            "last_name": str,
            "first_name": str,
            "pri_spec": str,
            "assgn": str,
            "st": str,
        },
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        dataset_id: str = DEFAULT_DATASET_ID,
        page_limit: int = PAGE_LIMIT,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._dataset_id = dataset_id
        self._page_limit = page_limit

    @property
    def _resource_path(self) -> str:
        return f"/resource/{self._dataset_id}.json"

    def _params(self, offset: int) -> dict[str, Any]:
        return {
            "$limit": self._page_limit,
            "$offset": offset,
            # Stable ordering by Socrata system row ID prevents records from
            # shifting between pages if CMS updates the dataset mid-ingest.
            "$order": ":id",
        }

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through the SODA endpoint, yielding one dict per row."""
        offset = 0
        while True:
            resp = await self.request("GET", self._resource_path, params=self._params(offset))
            rows = self._parse_body(resp)

            for row in rows:
                yield row

            # Short page (or empty): the source is exhausted.
            if len(rows) < self._page_limit:
                break
            offset += self._page_limit

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract the SODA JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from data.cms.gov: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected CMS response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

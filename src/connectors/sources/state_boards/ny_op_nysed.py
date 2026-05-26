"""
ny_op_nysed.py -- New York NYSED Office of Professions adapter (source state_board_ny, Phase 3-A).

The New York State Education Department (NYSED) Office of the Professions (OP) licenses and
disciplines physicians and other healthcare practitioners in NY. License verification data
is published via NY OpenData (data.op.nysed.gov) as a Socrata SODA API, using the same
pagination pattern as the federal CMS adapters (F4, I1, I2).

Integration method: **REST_API** (SODA 2.0 paginated JSON at data.op.nysed.gov).

Endpoint: https://data.op.nysed.gov/resource/{dataset_id}.json
Default dataset_id: jqe5-ck84 (NY Professions License Data -- verify before live ingest)

Schema contract (6 fields):
    license_number    -- NY license identifier
    full_name         -- practitioner full name (NYSED provides a single name field)
    profession_name   -- e.g. "Medicine", "Osteopathic Medicine", "Registered Professional Nursing"
    license_status    -- e.g. "Registered", "Not Registered"
    issue_date        -- license issue date string
    expiration_date   -- license expiration date string

LEGAL GATE: live ingest governed by Phase 0 FCRA determination. Tested with stub transports.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ...base import SourceConnector
from ...config import ConnectorConfig
from ...contract import SchemaContract
from ...errors import SourceUnavailableError
from ...models import IntegrationMethod

DEFAULT_BASE_URL = "https://data.op.nysed.gov"
# NY Professions License Data (Socrata dataset).
# Verify the dataset ID at https://data.ny.gov before live ingest --
# NYSED may have refreshed the dataset since this default was set.
DEFAULT_DATASET_ID = "jqe5-ck84"
PAGE_LIMIT = 5_000

_NY_REQUIRED_FIELDS = frozenset({
    "license_number",
    "full_name",
    "profession_name",
    "license_status",
    "issue_date",
    "expiration_date",
})


def ny_op_nysed_config(**overrides: Any) -> ConnectorConfig:
    """Build the NY NYSED OP (state_board_ny) ConnectorConfig.

    Uses the SODA 2.0 API (same pattern as F4/I1/I2). No API key required for
    the public NY OpenData endpoint. expected_min_records should be set in
    production (~300 000 for NY's active practitioner population).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_ny",
        source_name="New York NYSED Office of Professions",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (NY NYSED OP state_board_ny)",
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class NyMedicalBoardConnector(SourceConnector):
    """New York NYSED Office of Professions adapter (state_board_ny).

    Pages through the Socrata SODA 2.0 API using $limit/$offset/$order=:id
    (same termination pattern as F4/I1/I2). Yields one dict per row.

    The dataset includes all profession types, not just physicians. Downstream
    normalizers should filter by ``profession_name`` for physician-specific lookups
    (e.g. "Medicine", "Osteopathic Medicine").
    """

    contract = SchemaContract(
        required_fields=_NY_REQUIRED_FIELDS,
        field_types={f: str for f in _NY_REQUIRED_FIELDS},
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
            if len(rows) < self._page_limit:
                break
            offset += self._page_limit

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract the SODA JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from data.op.nysed.gov: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

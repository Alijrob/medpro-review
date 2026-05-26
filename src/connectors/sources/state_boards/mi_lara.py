"""
mi_lara.py -- Michigan LARA (Dept. of Licensing and Regulatory Affairs) adapter
(source state_board_mi, Phase 3-B).

The Michigan Department of Licensing and Regulatory Affairs (LARA) regulates
physicians and other healthcare professionals through the Bureau of Professional
Licensing (BPL). License data is published via the Michigan Open Data portal
(data.michigan.gov) as a Socrata SODA 2.0 API.

Integration method: **REST_API** (SODA 2.0 at data.michigan.gov).

Endpoint: https://data.michigan.gov/resource/{dataset_id}.json
Default dataset_id: nkpp-45cu (Michigan Professional Licenses -- verify before
live ingest at https://data.michigan.gov/browse?category=Health+and+Human+Services)

Schema contract (6 fields):
    license_number    -- MI license identifier (e.g. "4301234567")
    last_name         -- practitioner last name
    first_name        -- practitioner first name
    license_type      -- e.g. "Physician and Surgeon", "Osteopathic Physician"
    license_status    -- e.g. "Active", "Expired", "Lapsed", "Revoked"
    expiration_date   -- license expiration date string

LEGAL GATE: live ingest governed by Phase 0 FCRA determination. Tested with
stub transports only.
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

DEFAULT_BASE_URL = "https://data.michigan.gov"
# Michigan Professional Licenses (Socrata dataset).
# Verify at https://data.michigan.gov/browse?category=Health+and+Human+Services
# before live ingest -- LARA may have refreshed the dataset since this default.
DEFAULT_DATASET_ID = "nkpp-45cu"
PAGE_LIMIT = 5_000

_MI_REQUIRED_FIELDS = frozenset({
    "license_number",
    "last_name",
    "first_name",
    "license_type",
    "license_status",
    "expiration_date",
})


def mi_lara_config(**overrides: Any) -> ConnectorConfig:
    """Build the Michigan LARA (state_board_mi) ConnectorConfig.

    Uses the SODA 2.0 API (same pattern as NY/GA/PA). No API key required for
    the public MI OpenData endpoint. expected_min_records should be set to
    ~50 000 in production (MI licensed physician population).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_mi",
        source_name="Michigan LARA Bureau of Professional Licensing",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (MI LARA BPL state_board_mi)",
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class MiLaraConnector(SourceConnector):
    """Michigan LARA Bureau of Professional Licensing adapter (state_board_mi).

    Pages through the Socrata SODA 2.0 API using $limit/$offset/$order=:id
    (same termination pattern as state_board_ny, state_board_ga, state_board_pa).
    Yields one dict per row.

    The MI OpenData SODA response IS the array (no envelope). The dataset spans
    all regulated professions; downstream normalizers should filter by
    ``license_type`` for physician-specific lookups.
    """

    contract = SchemaContract(
        required_fields=_MI_REQUIRED_FIELDS,
        field_types={f: str for f in _MI_REQUIRED_FIELDS},
    )

    # Maps known MI LARA/SODA column name variants -> contract snake_case names.
    _FIELD_MAP: dict[str, str] = {
        "licnumber": "license_number",
        "lic_number": "license_number",
        "license_number": "license_number",
        "LicenseNumber": "license_number",
        "lname": "last_name",
        "last_name": "last_name",
        "LastName": "last_name",
        "fname": "first_name",
        "first_name": "first_name",
        "FirstName": "first_name",
        "lic_type": "license_type",
        "license_type": "license_type",
        "LicenseType": "license_type",
        "profession": "license_type",
        "lic_status": "license_status",
        "license_status": "license_status",
        "LicenseStatus": "license_status",
        "status": "license_status",
        "exp_date": "expiration_date",
        "expiration_date": "expiration_date",
        "ExpirationDate": "expiration_date",
    }

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

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map SODA column name variants to contract snake_case field names."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through the MI SODA endpoint, yielding one dict per row."""
        offset = 0
        while True:
            resp = await self.request("GET", self._resource_path, params=self._params(offset))
            rows = self._parse_body(resp)
            for row in rows:
                yield self._normalize_row(row)
            if len(rows) < self._page_limit:
                break
            offset += self._page_limit

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract the SODA JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from data.michigan.gov: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected MI SODA response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

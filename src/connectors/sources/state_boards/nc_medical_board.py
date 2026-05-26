"""
nc_medical_board.py -- North Carolina Medical Board adapter
(source state_board_nc, Phase 3-B).

The North Carolina Medical Board (NCMB) licenses physicians and physician
assistants in North Carolina. License lookup data is available via the NCMB
public licensure API, which returns paginated JSON records.

Integration method: **REST_API** (page-number paginated JSON at ncmedboard.org).

Endpoint: https://www.ncmedboard.org/api/licensure/search
Pagination: ?page=N&pageSize=N (terminates on empty array or short page,
same pattern as TX Medical Board).

Schema contract (6 fields):
    license_number    -- NC license identifier (e.g. "20000" for MD)
    last_name         -- practitioner last name
    first_name        -- practitioner first name
    license_status    -- e.g. "Active", "Inactive", "Revoked", "Surrendered"
    expiration_date   -- license expiration date string
    specialty         -- primary specialty designation from NCMB records

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

DEFAULT_BASE_URL = "https://www.ncmedboard.org"
DEFAULT_PATH = "/api/licensure/search"
PAGE_SIZE = 500

_NC_REQUIRED_FIELDS = frozenset({
    "license_number",
    "last_name",
    "first_name",
    "license_status",
    "expiration_date",
    "specialty",
})


def nc_medical_board_config(**overrides: Any) -> ConnectorConfig:
    """Build the NC Medical Board (state_board_nc) ConnectorConfig.

    Page-number paginated REST API (same pattern as TX Medical Board). No API key
    required for the public licensure search endpoint. expected_min_records should
    be set to ~45 000 in production (NC licensed physician population).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_nc",
        source_name="North Carolina Medical Board",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (NC Medical Board state_board_nc)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class NcMedicalBoardConnector(SourceConnector):
    """North Carolina Medical Board adapter (state_board_nc).

    Pages through the NCMB JSON API using page-number pagination (same
    termination pattern as state_board_tx). Terminates on empty-array response
    OR a short page (fewer records than page_size).

    The raw dict fields from the API may use camelCase or PascalCase;
    ``_normalize_row`` converts known variants to the contract's snake_case names.
    """

    contract = SchemaContract(
        required_fields=_NC_REQUIRED_FIELDS,
        field_types={f: str for f in _NC_REQUIRED_FIELDS},
    )

    # Maps NCMB API field name variants -> contract snake_case names.
    _FIELD_MAP: dict[str, str] = {
        "licenseNumber": "license_number",
        "LicenseNumber": "license_number",
        "license_number": "license_number",
        "LicNum": "license_number",
        "lastName": "last_name",
        "LastName": "last_name",
        "last_name": "last_name",
        "firstName": "first_name",
        "FirstName": "first_name",
        "first_name": "first_name",
        "licenseStatus": "license_status",
        "LicenseStatus": "license_status",
        "license_status": "license_status",
        "status": "license_status",
        "Status": "license_status",
        "expirationDate": "expiration_date",
        "ExpirationDate": "expiration_date",
        "expiration_date": "expiration_date",
        "specialty": "specialty",
        "Specialty": "specialty",
        "primarySpecialty": "specialty",
        "PrimarySpecialty": "specialty",
        "specialtyName": "specialty",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        path: str = DEFAULT_PATH,
        page_size: int = PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._path = path
        self._page_size = page_size

    def _params(self, page: int) -> dict[str, Any]:
        return {"page": page, "pageSize": self._page_size}

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map API field names to contract field names (camelCase -> snake_case)."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through the NCMB API, yielding one dict per license record."""
        page = 1
        while True:
            resp = await self.request("GET", self._path, params=self._params(page))
            rows = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            if len(rows) < self._page_size:
                break
            page += 1

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from NCMB API: {exc}"
            ) from exc

        # API may return {"data": [...]} or {"licenses": [...]} or a bare array.
        if isinstance(data, dict):
            data = (
                data.get("data")
                or data.get("licenses")
                or data.get("results")
                or data.get("providers")
                or []
            )
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected NCMB response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

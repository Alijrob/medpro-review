"""
tx_medical_board.py -- Texas Medical Board adapter (source state_board_tx, Phase 3-A).

The Texas Medical Board (TMB) licenses physicians and physician assistants in Texas.
License verification is available via the TMB public JSON API. The API returns JSON
arrays of license records, paginated by page number.

Integration method: **REST_API** (paginated JSON API at profile.tmb.state.tx.us).

Endpoint: https://profile.tmb.state.tx.us/api/licenses
Pagination: ?page=N&pageSize=N (terminates on empty array or short page).

Schema contract (6 fields):
    license_number    -- TX license identifier (e.g. "Q1234" for PA, "12345" for MD)
    last_name         -- practitioner last name
    first_name        -- practitioner first name
    license_status    -- e.g. "Active", "Expired", "Cancelled", "Revoked"
    expiration_date   -- date string
    specialty         -- primary specialty (TMB records include specialty designation)

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

DEFAULT_BASE_URL = "https://profile.tmb.state.tx.us"
DEFAULT_PATH = "/api/licenses"
PAGE_SIZE = 500

_TX_REQUIRED_FIELDS = frozenset({
    "license_number",
    "last_name",
    "first_name",
    "license_status",
    "expiration_date",
    "specialty",
})


def tx_medical_board_config(**overrides: Any) -> ConnectorConfig:
    """Build the Texas Medical Board (state_board_tx) ConnectorConfig.

    Paginated REST API. No API key required for the public lookup endpoint.
    expected_min_records should be set to ~90 000 in production (TX active physicians).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_tx",
        source_name="Texas Medical Board",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (TX Medical Board state_board_tx)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class TxMedicalBoardConnector(SourceConnector):
    """Texas Medical Board adapter (state_board_tx).

    Pages through the TMB JSON API using page-number pagination.
    Terminates on an empty-array response (last page returns [] rather than a
    short page).

    The raw dict fields from the API may use camelCase; ``_normalize_row``
    converts known camelCase variants to the contract's snake_case field names.
    """

    contract = SchemaContract(
        required_fields=_TX_REQUIRED_FIELDS,
        field_types={f: str for f in _TX_REQUIRED_FIELDS},
    )

    # Map TMB API camelCase field names -> contract snake_case names.
    _FIELD_MAP: dict[str, str] = {
        "licenseNumber": "license_number",
        "LicenseNumber": "license_number",
        "lastName": "last_name",
        "LastName": "last_name",
        "firstName": "first_name",
        "FirstName": "first_name",
        "licenseStatus": "license_status",
        "LicenseStatus": "license_status",
        "status": "license_status",
        "expirationDate": "expiration_date",
        "ExpirationDate": "expiration_date",
        "specialty": "specialty",
        "Specialty": "specialty",
        "primarySpecialty": "specialty",
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
        """Page through the TMB API, yielding one dict per license record."""
        page = 1
        while True:
            resp = await self.request("GET", self._path, params=self._params(page))
            rows = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            # Short page or empty page signals end of data.
            if len(rows) < self._page_size:
                break
            page += 1

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from TMB API: {exc}"
            ) from exc

        # API may return {"data": [...]} or a bare array.
        if isinstance(data, dict):
            data = data.get("data") or data.get("licenses") or data.get("results") or []
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected TMB response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

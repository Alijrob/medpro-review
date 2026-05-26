"""
fl_doh.py -- Florida Department of Health (DOH) FDBPR adapter (source state_board_fl, Phase 3-A).

The Florida Department of Health (DOH) regulates healthcare practitioners through its
Medical Quality Assurance (MQA) division. License verification data is accessible via
the MQA REST API (mqa.doh.state.fl.us), which returns JSON records for licensed
practitioners.

Integration method: **REST_API** (paginated JSON at mqa.doh.state.fl.us).

Endpoint: https://mqa.doh.state.fl.us/MQASearchServices/HealthCareProviders
Pagination: offset + limit (short-page sentinel for termination).

Schema contract (6 fields):
    license_number    -- FL license identifier (e.g. "ME12345")
    last_name         -- practitioner last name
    first_name        -- practitioner first name
    license_status    -- e.g. "Active", "Delinquent", "Null and Void", "Revoked"
    expiration_date   -- date string (MM/DD/YYYY format)
    license_type      -- e.g. "Medical Doctor (MD)", "Doctor of Osteopathic Medicine (DO)"

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

DEFAULT_BASE_URL = "https://mqa.doh.state.fl.us"
DEFAULT_PATH = "/MQASearchServices/HealthCareProviders"
PAGE_LIMIT = 1_000

_FL_REQUIRED_FIELDS = frozenset({
    "license_number",
    "last_name",
    "first_name",
    "license_status",
    "expiration_date",
    "license_type",
})


def fl_doh_config(**overrides: Any) -> ConnectorConfig:
    """Build the Florida DOH MQA (state_board_fl) ConnectorConfig.

    Paginated REST API. No API key required for the public lookup endpoint.
    expected_min_records should be set to ~120 000 in production (FL licensed physicians).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_fl",
        source_name="Florida Department of Health FDBPR",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (FL DOH FDBPR state_board_fl)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class FlDohConnector(SourceConnector):
    """Florida DOH Medical Quality Assurance adapter (state_board_fl).

    Pages through the MQA JSON API using offset-based pagination. Short-page
    sentinel (fewer records than PAGE_LIMIT) terminates the loop.

    The API returns records with mixed-case field names; ``_normalize_row``
    maps known FL DOH field name variants to the contract's snake_case names.
    """

    contract = SchemaContract(
        required_fields=_FL_REQUIRED_FIELDS,
        field_types={f: str for f in _FL_REQUIRED_FIELDS},
    )

    _FIELD_MAP: dict[str, str] = {
        "LicenseNumber": "license_number",
        "licenseNumber": "license_number",
        "LicNum": "license_number",
        "LastName": "last_name",
        "lastName": "last_name",
        "Lname": "last_name",
        "FirstName": "first_name",
        "firstName": "first_name",
        "Fname": "first_name",
        "LicenseStatus": "license_status",
        "licenseStatus": "license_status",
        "Status": "license_status",
        "ExpirationDate": "expiration_date",
        "expirationDate": "expiration_date",
        "ExpDate": "expiration_date",
        "LicenseType": "license_type",
        "licenseType": "license_type",
        "ProfessionName": "license_type",
        "Profession": "license_type",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        path: str = DEFAULT_PATH,
        page_limit: int = PAGE_LIMIT,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._path = path
        self._page_limit = page_limit

    def _params(self, offset: int) -> dict[str, Any]:
        return {"offset": offset, "limit": self._page_limit}

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through the FL DOH MQA API, yielding one dict per license record."""
        offset = 0
        while True:
            resp = await self.request("GET", self._path, params=self._params(offset))
            rows = self._parse_body(resp)
            for row in rows:
                yield self._normalize_row(row)
            if len(rows) < self._page_limit:
                break
            offset += self._page_limit

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract JSON array from FL DOH response or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from FL DOH API: {exc}"
            ) from exc

        # FL MQA may wrap the list: {"providers": [...]} or {"results": [...]}
        if isinstance(data, dict):
            data = (
                data.get("providers")
                or data.get("results")
                or data.get("data")
                or data.get("records")
                or []
            )
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected FL DOH response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

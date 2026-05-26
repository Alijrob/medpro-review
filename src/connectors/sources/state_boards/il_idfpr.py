"""
il_idfpr.py -- Illinois IDFPR license lookup adapter (source state_board_il, Phase 3-A).

The Illinois Department of Financial and Professional Regulation (IDFPR) licenses
physicians and other healthcare practitioners in Illinois. License data is accessible
via the IDFPR public online license lookup API, which returns JSON records.

Integration method: **REST_API** (paginated JSON at online-lic.idfpr.illinois.gov).

Endpoint: https://online-lic.idfpr.illinois.gov/api/licenses
Pagination: offset/limit with short-page sentinel.

Schema contract (5 fields):
    license_number    -- IL license identifier (e.g. "036-123456")
    full_name         -- practitioner full name (IDFPR provides combined name field)
    license_type      -- e.g. "Physician and Surgeon License", "Osteopathic Physician License"
    license_status    -- e.g. "Active", "Inactive", "Expired", "Revoked"
    expiration_date   -- date string

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

DEFAULT_BASE_URL = "https://online-lic.idfpr.illinois.gov"
DEFAULT_PATH = "/api/licenses"
PAGE_LIMIT = 1_000

_IL_REQUIRED_FIELDS = frozenset({
    "license_number",
    "full_name",
    "license_type",
    "license_status",
    "expiration_date",
})


def il_idfpr_config(**overrides: Any) -> ConnectorConfig:
    """Build the Illinois IDFPR (state_board_il) ConnectorConfig.

    Paginated REST API. No API key required for the public lookup endpoint.
    expected_min_records should be set to ~60 000 in production (IL licensed physicians).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_il",
        source_name="Illinois IDFPR",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (IL IDFPR state_board_il)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class IlIdfprConnector(SourceConnector):
    """Illinois IDFPR license lookup adapter (state_board_il).

    Pages through the IDFPR license API using offset-based pagination.
    Short-page sentinel terminates the loop.

    The API may return mixed-case or camelCase field names; ``_normalize_row``
    maps known IDFPR variants to the contract's snake_case names.
    """

    contract = SchemaContract(
        required_fields=_IL_REQUIRED_FIELDS,
        field_types={f: str for f in _IL_REQUIRED_FIELDS},
    )

    _FIELD_MAP: dict[str, str] = {
        "LicenseNumber": "license_number",
        "licenseNumber": "license_number",
        "LicNum": "license_number",
        "LICNUM": "license_number",
        "FullName": "full_name",
        "fullName": "full_name",
        "Name": "full_name",
        "NAME": "full_name",
        "LicenseName": "full_name",
        "LicenseType": "license_type",
        "licenseType": "license_type",
        "LicType": "license_type",
        "LICTYPE": "license_type",
        "LicenseStatus": "license_status",
        "licenseStatus": "license_status",
        "Status": "license_status",
        "STATUS": "license_status",
        "ExpirationDate": "expiration_date",
        "expirationDate": "expiration_date",
        "ExpDate": "expiration_date",
        "EXP_DATE": "expiration_date",
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
        """Page through the IDFPR license API, yielding one dict per license record."""
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
        """Extract JSON array from IDFPR response or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from IDFPR API: {exc}"
            ) from exc

        if isinstance(data, dict):
            data = (
                data.get("licenses")
                or data.get("results")
                or data.get("data")
                or data.get("records")
                or []
            )
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected IDFPR response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

"""
oh_state_medical_board.py -- Ohio State Medical Board adapter
(source state_board_oh, Phase 3-B).

The State Medical Board of Ohio (SMBO) licenses physicians, physician assistants,
and other healthcare providers in Ohio. License data is accessible via the Ohio
eLicense portal (elicense.ohio.gov), which provides a JSON REST API with
offset-based pagination.

Integration method: **REST_API** (paginated JSON at elicense.ohio.gov).

Endpoint: https://elicense.ohio.gov/OH_VerifyProvider/api/providers
Pagination: offset + limit (short-page sentinel for termination).

Schema contract (6 fields):
    license_number    -- OH license identifier (e.g. "35.123456")
    last_name         -- practitioner last name
    first_name        -- practitioner first name
    license_type      -- e.g. "Physician (MD)", "Doctor of Osteopathic Medicine"
    license_status    -- e.g. "Active", "Inactive", "Suspended", "Revoked"
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

DEFAULT_BASE_URL = "https://elicense.ohio.gov"
DEFAULT_PATH = "/OH_VerifyProvider/api/providers"
PAGE_LIMIT = 1_000

_OH_REQUIRED_FIELDS = frozenset({
    "license_number",
    "last_name",
    "first_name",
    "license_type",
    "license_status",
    "expiration_date",
})


def oh_state_medical_board_config(**overrides: Any) -> ConnectorConfig:
    """Build the Ohio State Medical Board (state_board_oh) ConnectorConfig.

    Offset-paginated REST API (same termination pattern as FL DOH). No API key
    required for the public eLicense portal endpoint. expected_min_records should
    be set to ~60 000 in production (OH licensed physician population).
    """
    params: dict[str, Any] = dict(
        source_id="state_board_oh",
        source_name="Ohio State Medical Board",
        source_category=SourceCategory.STATE_BOARD,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (OH State Medical Board state_board_oh)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class OhStateMedicalBoardConnector(SourceConnector):
    """Ohio State Medical Board adapter (state_board_oh).

    Pages through the Ohio eLicense JSON API using offset-based pagination.
    Short-page sentinel (fewer records than PAGE_LIMIT) terminates the loop.

    The API may return records with mixed-case or camelCase field names;
    ``_normalize_row`` maps known OH eLicense field name variants to the
    contract's snake_case names.
    """

    contract = SchemaContract(
        required_fields=_OH_REQUIRED_FIELDS,
        field_types={f: str for f in _OH_REQUIRED_FIELDS},
    )

    # Maps Ohio eLicense API field name variants -> contract snake_case names.
    _FIELD_MAP: dict[str, str] = {
        "LicenseNumber": "license_number",
        "licenseNumber": "license_number",
        "license_number": "license_number",
        "LicNum": "license_number",
        "LastName": "last_name",
        "lastName": "last_name",
        "last_name": "last_name",
        "LNAME": "last_name",
        "FirstName": "first_name",
        "firstName": "first_name",
        "first_name": "first_name",
        "FNAME": "first_name",
        "LicenseType": "license_type",
        "licenseType": "license_type",
        "license_type": "license_type",
        "ProfessionName": "license_type",
        "profession": "license_type",
        "LicenseStatus": "license_status",
        "licenseStatus": "license_status",
        "license_status": "license_status",
        "Status": "license_status",
        "ExpirationDate": "expiration_date",
        "expirationDate": "expiration_date",
        "expiration_date": "expiration_date",
        "ExpDate": "expiration_date",
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
        """Map API field names to contract field names."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through the OH eLicense API, yielding one dict per license record."""
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
        """Extract JSON array from OH eLicense response or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from OH eLicense API: {exc}"
            ) from exc

        # OH eLicense may wrap: {"providers": [...]} or {"results": [...]} or bare list.
        if isinstance(data, dict):
            data = (
                data.get("providers")
                or data.get("results")
                or data.get("data")
                or data.get("licenses")
                or []
            )
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected OH eLicense response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

"""
fl_courts.py -- Florida eCourts adapter (source court_fl, Phase 3-C).

Florida circuit courts are operated at the county level but the Florida
Courts E-Filing Authority (FCEFA) provides a statewide eFiling portal at
efiling.flcourts.gov. The Florida State Courts System also maintains a
limited statewide case search API. This adapter targets that statewide
REST endpoint for case metadata lookups by party name.

Integration method: **REST_API** (offset/limit pagination).

Endpoint: https://efiling.flcourts.gov/api/cases/search
Pagination: ?offset=N&limit=N; terminates on short-page sentinel.
Auth: no API key required for public case search.

Schema contract (6 fields):
    case_number  -- Florida court case number
    case_style   -- case caption / style (e.g. "Smith vs Jones Hospital")
    court        -- court identifier or name (e.g. "Hillsborough County Circuit")
    date_filed   -- filing date string
    case_type    -- type code (e.g. "CC" civil circuit, "SC" small claims)
    status       -- case status (e.g. "Open", "Closed")

NOTE: FL courts are county-operated. Statewide API coverage is incomplete;
some counties require direct Clerk of Courts lookups. Exact endpoint path
and field schema must be verified before live ingest. Florida Sunshine Law
provides broad public access but FL sealing/expungement statutes apply.
Counsel must advise on which record types are reportable.

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

DEFAULT_BASE_URL = "https://efiling.flcourts.gov"
DEFAULT_PATH = "/api/cases/search"
DEFAULT_PAGE_SIZE = 100

_FL_COURT_REQUIRED_FIELDS = frozenset({
    "case_number",
    "case_style",
    "court",
    "date_filed",
    "case_type",
    "status",
})


def fl_courts_config(**overrides: Any) -> ConnectorConfig:
    """Build the Florida eCourts (court_fl) ConnectorConfig.

    REST API with offset/limit pagination. Endpoint must be verified before
    live ingest. rate_limit_per_sec=3.0 as a conservative default.
    """
    params: dict[str, Any] = dict(
        source_id="court_fl",
        source_name="Florida eCourts",
        source_category=SourceCategory.COURT,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (Florida Courts court_fl)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class FlCourtsConnector(SourceConnector):
    """Florida eCourts adapter (court_fl).

    Searches by party name using offset/limit pagination. Terminates on a
    short-page sentinel. The response may be a bare list or a dict with a
    'cases', 'results', or 'data' key; _parse_body unwraps both shapes.
    """

    contract = SchemaContract(
        required_fields=_FL_COURT_REQUIRED_FIELDS,
        field_types={f: str for f in _FL_COURT_REQUIRED_FIELDS},
    )

    _FIELD_MAP: dict[str, str] = {
        "caseNumber": "case_number",
        "case_number": "case_number",
        "caseNo": "case_number",
        "caseStyle": "case_style",
        "case_style": "case_style",
        "caseName": "case_style",
        "case_name": "case_style",
        "court": "court",
        "courtName": "court",
        "court_name": "court",
        "county": "court",
        "dateFiled": "date_filed",
        "date_filed": "date_filed",
        "filedDate": "date_filed",
        "filed_date": "date_filed",
        "caseType": "case_type",
        "case_type": "case_type",
        "type": "case_type",
        "status": "status",
        "caseStatus": "status",
        "case_status": "status",
        "dispositionType": "status",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        party_name: str = "",
        path: str = DEFAULT_PATH,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._party_name = party_name
        self._path = path
        self._page_size = page_size

    def _params(self, offset: int) -> dict[str, Any]:
        params: dict[str, Any] = {"offset": offset, "limit": self._page_size}
        if self._party_name:
            params["partyName"] = self._party_name
        return params

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            if val is None:
                val = ""
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through FL Courts results, yielding one dict per case."""
        offset = 0
        while True:
            resp = await self.request("GET", self._path, params=self._params(offset))
            rows = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            if len(rows) < self._page_size:
                break
            offset += len(rows)

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract row list from response or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from FL Courts: {exc}"
            ) from exc

        if isinstance(data, dict):
            data = (
                data.get("cases")
                or data.get("results")
                or data.get("data")
                or []
            )
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected FL Courts response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

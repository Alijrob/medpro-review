"""
tx_courts.py -- Texas Courts Search adapter (source court_tx, Phase 3-C).

The Texas Office of Court Administration (OCA) provides a public court records search
at search.txcourts.gov. The search covers appellate courts, district courts, and county
courts at law across Texas. Some counties also use Tyler Technologies' Odyssey platform
which exposes a REST API; this adapter targets the statewide OCA search endpoint.

Integration method: **REST_API** (offset/limit pagination).

Endpoint: https://search.txcourts.gov/api/cases
Pagination: ?offset=N&limit=N; terminates on short-page sentinel.
Auth: no API key required for public search.

Schema contract (6 fields):
    case_number  -- Texas court case number (e.g. "01-22-00123-CV")
    style        -- case style / caption (e.g. "SMITH v. JONES HOSPITAL")
    court        -- court name or identifier
    date_filed   -- filing date string
    case_type    -- type code or description (e.g. "CV" for civil)
    status       -- case status (e.g. "Active", "Disposed")

NOTE: The exact endpoint path and field schema must be verified against the live
Texas OCA API before live ingest. TX expunction law (CCP Art. 55.01) restricts
re-reporting expunged records -- counsel must advise on filtering obligations.

LEGAL GATE: live ingest governed by Phase 0 FCRA determination. Tested with stub
transports only.
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

DEFAULT_BASE_URL = "https://search.txcourts.gov"
DEFAULT_PATH = "/api/cases"
DEFAULT_PAGE_SIZE = 100

_TX_COURT_REQUIRED_FIELDS = frozenset({
    "case_number",
    "style",
    "court",
    "date_filed",
    "case_type",
    "status",
})


def tx_courts_config(**overrides: Any) -> ConnectorConfig:
    """Build the Texas Courts Search (court_tx) ConnectorConfig.

    REST API with offset/limit pagination. Endpoint must be verified before
    live ingest. rate_limit_per_sec=3.0 as a conservative default.
    """
    params: dict[str, Any] = dict(
        source_id="court_tx",
        source_name="Texas Courts Search",
        source_category=SourceCategory.COURT,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (Texas Courts court_tx)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class TxCourtsConnector(SourceConnector):
    """Texas Courts Search adapter (court_tx).

    Searches by party name using offset/limit pagination. Terminates on a
    short-page sentinel (page with fewer rows than the limit). May also
    terminate on an empty-results page when the API returns a totalCount
    field and the offset has exceeded it.

    The response may be a bare list or a dict with a 'results' or 'cases'
    key. _parse_body unwraps both shapes.
    """

    contract = SchemaContract(
        required_fields=_TX_COURT_REQUIRED_FIELDS,
        field_types={f: str for f in _TX_COURT_REQUIRED_FIELDS},
    )

    _FIELD_MAP: dict[str, str] = {
        "caseNumber": "case_number",
        "case_number": "case_number",
        "caseNo": "case_number",
        "style": "style",
        "caseStyle": "style",
        "case_style": "style",
        "caseName": "style",
        "case_name": "style",
        "court": "court",
        "courtName": "court",
        "court_name": "court",
        "dateFiled": "date_filed",
        "date_filed": "date_filed",
        "fileDate": "date_filed",
        "file_date": "date_filed",
        "caseType": "case_type",
        "case_type": "case_type",
        "type": "case_type",
        "status": "status",
        "caseStatus": "status",
        "case_status": "status",
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
        """Page through TX Courts results, yielding one dict per case."""
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
                f"{self.source_id}: non-JSON response from TX Courts: {exc}"
            ) from exc

        # Unwrap dict envelope if present.
        if isinstance(data, dict):
            data = (
                data.get("results")
                or data.get("cases")
                or data.get("data")
                or []
            )
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected TX Courts response shape "
                f"(expected list, got {type(data).__name__})"
            )
        return data

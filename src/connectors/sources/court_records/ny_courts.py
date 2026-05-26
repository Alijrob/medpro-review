"""
ny_courts.py -- New York eCourts WebCivil adapter (source court_ny, Phase 3-C).

The New York State Unified Court System operates eCourts, which provides public access
to civil court records via WebCivil Online (iapps.courts.state.ny.us/webcivil).
This adapter targets the WebCivil case search API for party-name lookups.

Integration method: **REST_API** (page-number pagination).

Endpoint: https://iapps.courts.state.ny.us/webcivil/api/cases
Pagination: ?page=N&pageSize=N; terminates when 'next' is null or page >= totalPages.
Auth: no API key required for public WebCivil search.

Schema contract (6 fields):
    index_number  -- NY court index number (e.g. "150001/2022")
    caption       -- case caption (e.g. "SMITH v. JONES MEMORIAL HOSPITAL")
    court_name    -- court name (e.g. "Supreme Court, New York County")
    date_filed    -- filing date string
    case_type     -- case type (e.g. "Tort", "Contract", "Other Negligence")
    status        -- RJI status (e.g. "Active", "Disposed", "Discontinued")

NOTE: NY eCourts WebCivil covers civil cases filed in Supreme Court and some
lower courts. Criminal records, sealed matters, and Family Court are NOT
available via this public interface. NY sealing statutes (CPL ss 160.50, 160.55)
restrict re-reporting certain records -- counsel must advise on which NY court
records are reportable for the medpro-review use case. Endpoint must be
verified before live ingest.

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

DEFAULT_BASE_URL = "https://iapps.courts.state.ny.us"
DEFAULT_PATH = "/webcivil/api/cases"
DEFAULT_PAGE_SIZE = 100

_NY_COURT_REQUIRED_FIELDS = frozenset({
    "index_number",
    "caption",
    "court_name",
    "date_filed",
    "case_type",
    "status",
})


def ny_courts_config(**overrides: Any) -> ConnectorConfig:
    """Build the New York eCourts WebCivil (court_ny) ConnectorConfig.

    REST API with page-number pagination. Endpoint must be verified before
    live ingest. rate_limit_per_sec=3.0 as a conservative default.
    """
    params: dict[str, Any] = dict(
        source_id="court_ny",
        source_name="New York eCourts WebCivil",
        source_category=SourceCategory.COURT,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (NY eCourts court_ny)",
        rate_limit_per_sec=3.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class NyCourtsConnector(SourceConnector):
    """New York eCourts WebCivil adapter (court_ny).

    Searches by party name using page-number pagination. Terminates when the
    'next' field is null or when page >= totalPages. The response may be a
    bare list or a dict with a 'cases', 'results', or 'data' key.
    """

    contract = SchemaContract(
        required_fields=_NY_COURT_REQUIRED_FIELDS,
        field_types={f: str for f in _NY_COURT_REQUIRED_FIELDS},
    )

    _FIELD_MAP: dict[str, str] = {
        "indexNumber": "index_number",
        "index_number": "index_number",
        "captionOnFiling": "caption",
        "caption": "caption",
        "caseCaption": "caption",
        "case_caption": "caption",
        "courtName": "court_name",
        "court_name": "court_name",
        "court": "court_name",
        "dateFiled": "date_filed",
        "date_filed": "date_filed",
        "rjiDate": "date_filed",
        "rji_date": "date_filed",
        "caseType": "case_type",
        "case_type": "case_type",
        "natureOfAction": "case_type",
        "nature_of_action": "case_type",
        "status": "status",
        "rjiStatus": "status",
        "rji_status": "status",
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

    def _params(self, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "pageSize": self._page_size}
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
        """Page through NY eCourts results, yielding one dict per case."""
        page = 1
        while True:
            resp = await self.request("GET", self._path, params=self._params(page))
            rows, has_next = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            if not has_next:
                break
            page += 1

    def _parse_body(self, resp: Any) -> tuple[list[dict[str, Any]], bool]:
        """Extract (cases_list, has_next) or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from NY eCourts: {exc}"
            ) from exc

        if isinstance(data, dict):
            has_next = bool(data.get("next"))
            rows = (
                data.get("cases")
                or data.get("results")
                or data.get("data")
                or []
            )
        elif isinstance(data, list):
            rows = data
            has_next = False  # bare list has no pagination metadata
        else:
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected NY eCourts response shape "
                f"(expected dict or list, got {type(data).__name__})"
            )

        if not isinstance(rows, list):
            raise SourceUnavailableError(
                f"{self.source_id}: cases field is not a list in NY eCourts response"
            )

        return rows, has_next

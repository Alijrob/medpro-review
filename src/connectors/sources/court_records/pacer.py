"""
pacer.py -- PACER Case Locator adapter (source pacer, Phase 3-C).

PACER (Public Access to Court Electronic Records) is the authoritative source for
federal court records across all 94 districts. The PACER Case Locator (PCL) REST API
supports cross-district party-name searches and returns case metadata without per-page
document fees. Document retrieval via CM/ECF incurs the $0.10/page fee (waived under
$30/quarter per account).

Integration method: **REST_API** (page-number pagination via pcl.uscourts.gov).

Endpoint: https://pcl.uscourts.gov/pcl-public-api/rest/cases/find
Pagination: ?page=N&size=N (0-indexed pages); terminates when page >= totalPages
            or when 'content' is empty.
Auth: X-NEXT-GEN-CSO token header. Token is obtained out-of-band via PACER
      login at pacer.login.uscourts.gov; pass as 'pacer_token' constructor arg.

Schema contract (6 fields):
    case_id     -- PACER PCL internal case identifier
    case_title  -- full case caption (e.g. "SMITH vs. JONES HOSPITAL INC")
    case_number -- docket number (e.g. "1:22-cv-00123")
    court_id    -- court identifier (e.g. "txnd" for N.D. Texas)
    date_filed  -- filing date string
    case_type   -- type code: "cv" (civil), "bk" (bankruptcy), "cr" (criminal)

LEGAL GATE: live ingest governed by Phase 0 FCRA determination. PACER ToS permits
programmatic access for legitimate purposes; counsel must confirm re-publishing federal
court case metadata in consumer reports before live ingest. Tested with stub transports.
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

DEFAULT_BASE_URL = "https://pcl.uscourts.gov"
DEFAULT_PATH = "/pcl-public-api/rest/cases/find"
DEFAULT_PAGE_SIZE = 50

_PACER_REQUIRED_FIELDS = frozenset({
    "case_id",
    "case_title",
    "case_number",
    "court_id",
    "date_filed",
    "case_type",
})


def pacer_config(**overrides: Any) -> ConnectorConfig:
    """Build the PACER Case Locator (pacer) ConnectorConfig.

    REST API with 0-indexed page-number pagination. pacer_token is a
    constructor arg (not ConnectorConfig) -- PACER credentials are secrets
    and must not appear in config. Token is obtained via PACER login API.
    rate_limit_per_sec=2.0 to stay within PACER's acceptable-use guidelines.
    """
    params: dict[str, Any] = dict(
        source_id="pacer",
        source_name="PACER Case Locator (Federal Courts)",
        source_category=SourceCategory.COURT,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (PACER PCL pacer)",
        rate_limit_per_sec=2.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class PacerConnector(SourceConnector):
    """PACER Case Locator adapter (pacer).

    Searches the PCL cross-district API by party name using 0-indexed
    page-number pagination. Terminates when the current page >= totalPages
    or when the 'content' array is empty.

    pacer_token is the NextGen CSO authentication token obtained from PACER
    login; it is passed as the X-NEXT-GEN-CSO header on every request.
    If pacer_token is None the header is omitted (useful for stub-transport
    tests that don't validate auth headers).
    """

    contract = SchemaContract(
        required_fields=_PACER_REQUIRED_FIELDS,
        field_types={f: str for f in _PACER_REQUIRED_FIELDS},
    )

    # PCL API may return camelCase or snake_case depending on endpoint version.
    _FIELD_MAP: dict[str, str] = {
        "caseId": "case_id",
        "case_id": "case_id",
        "caseTitle": "case_title",
        "case_title": "case_title",
        "caseNumber": "case_number",
        "case_number": "case_number",
        "courtId": "court_id",
        "court_id": "court_id",
        "dateFiled": "date_filed",
        "date_filed": "date_filed",
        "caseType": "case_type",
        "case_type": "case_type",
        "caseTypeFull": "case_type",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        last_name: str = "",
        first_name: str = "",
        page_size: int = DEFAULT_PAGE_SIZE,
        pacer_token: str | None = None,
        path: str = DEFAULT_PATH,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._last_name = last_name
        self._first_name = first_name
        self._page_size = page_size
        self._pacer_token = pacer_token
        self._path = path

    def _auth_headers(self) -> dict[str, str]:
        if self._pacer_token:
            return {"X-NEXT-GEN-CSO": self._pacer_token}
        return {}

    def _params(self, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "size": self._page_size}
        if self._last_name:
            params["lastName"] = self._last_name
        if self._first_name:
            params["firstName"] = self._first_name
        return params

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map PCL field names to contract names; normalize None to empty str."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            if val is None:
                val = ""
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through PCL results, yielding one dict per case."""
        page = 0  # PCL uses 0-based page indexing
        while True:
            resp = await self.request(
                "GET",
                self._path,
                params=self._params(page),
                headers=self._auth_headers(),
            )
            rows, total_pages = self._parse_body(resp, page)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            page += 1
            if total_pages is not None and page >= total_pages:
                break

    def _parse_body(
        self, resp: Any, current_page: int
    ) -> tuple[list[dict[str, Any]], int | None]:
        """Extract (content_list, total_pages) or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from PACER PCL: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected PACER PCL response shape "
                f"(expected dict, got {type(data).__name__})"
            )

        content = data.get("content", [])
        if not isinstance(content, list):
            raise SourceUnavailableError(
                f"{self.source_id}: 'content' is not a list in PACER PCL response"
            )

        total_pages = data.get("totalPages")  # None if absent -- open-ended
        return content, total_pages

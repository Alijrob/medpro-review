"""
court_listener.py -- CourtListener / RECAP Archive adapter (source court_listener, Phase 3-C).

CourtListener (Free Law Project) provides free CC0/open-licensed access to a large
subset of federal court dockets, opinions, and case metadata via a public REST API.
It is the primary cost-reduction proxy for PACER data: build and exhaust CourtListener
before paying PACER per-page fees.

Integration method: **REST_API** (paginated JSON at api.courtlistener.com/v4).

Endpoint: https://www.courtlistener.com/api/rest/v4/dockets/
Pagination: page-number via ?page=N&page_size=N; terminates when 'next' is null.
Auth: optional API token (higher rate-limit ceiling with token).

Schema contract (6 fields):
    docket_id       -- CourtListener docket ID (coerced to str)
    case_name       -- case name / caption (e.g. "Smith v. Jones Hospital")
    docket_number   -- court docket number (e.g. "2:22-cv-01234")
    court           -- court identifier string (e.g. "cacd", "txnd")
    date_filed      -- filing date string (YYYY-MM-DD or empty)
    nature_of_suit  -- nature-of-suit description (e.g. "Personal Injury -- Medical")

Field normalization: CourtListener v4 returns mostly snake_case; _FIELD_MAP covers
legacy camelCase keys from older API versions that may appear in RECAP-uploaded docs.

LEGAL GATE: live ingest governed by Phase 0 FCRA determination. Tested with stub
transports only. Free Law Project data is CC0-licensed; counsel should confirm that
using CourtListener as a PACER proxy satisfies FCRA accuracy (ss 1681e(b)) provenance
requirements before live ingest.
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

DEFAULT_BASE_URL = "https://www.courtlistener.com"
DEFAULT_PATH = "/api/rest/v4/dockets/"
DEFAULT_PAGE_SIZE = 100

_CL_REQUIRED_FIELDS = frozenset({
    "docket_id",
    "case_name",
    "docket_number",
    "court",
    "date_filed",
    "nature_of_suit",
})


def court_listener_config(**overrides: Any) -> ConnectorConfig:
    """Build the CourtListener (court_listener) ConnectorConfig.

    REST API with page-number pagination. Optional API token for higher
    rate-limit ceiling. Party-name search is injected at the connector level
    (not in ConnectorConfig) since each provider lookup uses a different name.
    expected_min_records should remain None (depends on party_name query scope).
    """
    params: dict[str, Any] = dict(
        source_id="court_listener",
        source_name="CourtListener / RECAP Archive",
        source_category=SourceCategory.COURT,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (CourtListener court_listener)",
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class CourtListenerConnector(SourceConnector):
    """CourtListener / RECAP Archive adapter (court_listener).

    Searches CourtListener dockets by party name using page-number pagination.
    Terminates when the API response's 'next' field is null (no more pages).

    The response body is a dict with 'count', 'next', 'previous', and 'results'.
    'results' is the list of docket records; 'next' being null signals last page.

    CourtListener v4 returns mostly snake_case; _FIELD_MAP normalizes any
    residual camelCase keys from legacy RECAP-uploaded documents.
    """

    contract = SchemaContract(
        required_fields=_CL_REQUIRED_FIELDS,
        field_types={f: str for f in _CL_REQUIRED_FIELDS},
    )

    # CourtListener v4 uses snake_case; map legacy camelCase keys too.
    _FIELD_MAP: dict[str, str] = {
        # ID field -- coerce int to str in _normalize_row
        "id": "docket_id",
        "docketId": "docket_id",
        "docket_id": "docket_id",
        # Case name
        "caseName": "case_name",
        "case_name": "case_name",
        # Docket number
        "docketNumber": "docket_number",
        "docket_number": "docket_number",
        # Court (short ID like "cacd")
        "court": "court",
        "courtId": "court",
        # Date filed
        "dateFiled": "date_filed",
        "date_filed": "date_filed",
        # Nature of suit
        "natureOfSuit": "nature_of_suit",
        "nature_of_suit": "nature_of_suit",
        "suitNature": "nature_of_suit",
        "suit_nature": "nature_of_suit",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        party_name: str = "",
        path: str = DEFAULT_PATH,
        page_size: int = DEFAULT_PAGE_SIZE,
        api_token: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._party_name = party_name
        self._path = path
        self._page_size = page_size
        self._api_token = api_token

    def _auth_headers(self) -> dict[str, str]:
        if self._api_token:
            return {"Authorization": f"Token {self._api_token}"}
        return {}

    def _params(self, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": self._page_size}
        if self._party_name:
            params["party_name"] = self._party_name
        return params

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map API field names to contract names; coerce id (int) to str."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            # Coerce numeric id to str so contract's str type check passes.
            if mapped == "docket_id" and val is not None:
                val = str(val)
            # Normalize None to empty string for optional-ish text fields.
            if val is None:
                val = ""
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through CourtListener dockets, yielding one dict per case."""
        page = 1
        while True:
            resp = await self.request(
                "GET",
                self._path,
                params=self._params(page),
                headers=self._auth_headers(),
            )
            rows, has_next = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            if not has_next:
                break
            page += 1

    def _parse_body(self, resp: Any) -> tuple[list[dict[str, Any]], bool]:
        """Extract (results_list, has_next) from response or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from CourtListener: {exc}"
            ) from exc

        if not isinstance(data, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected CourtListener response shape "
                f"(expected dict, got {type(data).__name__})"
            )

        results = data.get("results", [])
        if not isinstance(results, list):
            raise SourceUnavailableError(
                f"{self.source_id}: 'results' is not a list in CourtListener response"
            )

        has_next = bool(data.get("next"))
        return results, has_next

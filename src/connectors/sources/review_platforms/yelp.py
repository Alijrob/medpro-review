"""
yelp.py -- Yelp Fusion API review platform adapter (source yelp, Phase 3-E).

Yelp Fusion (api.yelp.com) provides consumer-facing provider profiles including star
ratings, review counts, business categories, and location data. The Yelp Fusion ToS
prohibit caching beyond 24 hours, require Yelp branding on displayed data, and restrict
commercial redistribution. A Yelp Developer account and API key are required; the free
tier has rate limits.

Integration method: REST_API (Yelp Fusion Business Search endpoint).

Endpoint: https://api.yelp.com/v3/businesses/search
Pagination: offset/limit; terminates on short-page sentinel (len(rows) < page_size)
            OR when offset reaches the Yelp hard cap of 1000 results per search.
Auth: Bearer token (api_key from Yelp Developer account, NOT stored in ConnectorConfig).

Schema contract (6 fields):
    id            -- Yelp business identifier (str)
    name          -- business/provider name (str)
    rating        -- aggregate Yelp star rating (str, coerced from float)
    review_count  -- total number of Yelp reviews (str, coerced from int)
    location      -- location dict with address fields (dict; None -> {})
    categories    -- list of category dicts [{alias, title}] (list; None -> [])

Field normalization: _FIELD_MAP covers common alias variants. Numeric rating and
review_count are coerced to str. None location is coerced to {} and None categories
to [] to avoid false-positive schema drift.

ToS / Legal notes:
    - T2: free Yelp Developer API key; rate-limited; Yelp branding required on display.
    - ToS prohibit caching beyond 24 hours and commercial redistribution.
    - Maximum 1000 results per search query (Yelp hard cap -- offset >= 1000 terminates).
    - Live ingest is additionally gated on the Phase 0 FCRA determination.
    See docs/reference/tos-matrix.md row R2.

LICENSE GATE: api_key must come from a Yelp Developer account. Raises AuthenticationError
on fetch_raw() if api_key is absent. This adapter is built and tested stub-only.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ...base import SourceConnector
from ...config import ConnectorConfig
from ...contract import SchemaContract
from ...errors import AuthenticationError, SourceUnavailableError
from ...models import IntegrationMethod

DEFAULT_BASE_URL = "https://api.yelp.com"
DEFAULT_PATH = "/v3/businesses/search"
DEFAULT_PAGE_SIZE = 50  # Yelp Fusion max per request

# Yelp hard caps pagination at 1000 results per search query regardless of total.
_YELP_MAX_OFFSET = 1000

_YP_REQUIRED_FIELDS = frozenset({
    "id",
    "name",
    "rating",
    "review_count",
    "location",
    "categories",
})


def yelp_config(**overrides: Any) -> ConnectorConfig:
    """Build the Yelp Fusion (yelp) ConnectorConfig.

    Offset/limit paginated REST API. api_key comes from a Yelp Developer account.
    expected_min_records is None by default -- depends on the search query scope.

    ToS: T2 -- Yelp Developer API key required; Yelp branding required on display;
    24-hour cache limit; 1000-result max per search. See docs/reference/tos-matrix.md row R2.
    """
    params: dict[str, Any] = dict(
        source_id="yelp",
        source_name="Yelp Fusion Provider Reviews",
        source_category=SourceCategory.REVIEW_PLATFORM,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (Yelp Fusion yelp)",
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class YelpConnector(SourceConnector):
    """Yelp Fusion Business Search adapter for healthcare provider reviews (yelp).

    Fetches provider listings via offset/limit pagination. Terminates on a
    short-page sentinel (len(rows) < page_size) or when the Yelp hard cap of
    1000 results per search is reached (offset >= _YELP_MAX_OFFSET).

    Response envelope:
        {
            "total": N,
            "businesses": [...]
        }

    ToS: api_key must be from a Yelp Developer account. Raises AuthenticationError
    on fetch_raw() if api_key is absent. Yelp branding is required on any display
    of the returned data.
    """

    contract = SchemaContract(
        required_fields=_YP_REQUIRED_FIELDS,
        field_types={
            "id": str,
            "name": str,
            "rating": str,
            "review_count": str,
            "location": dict,
            "categories": list,
        },
    )

    _FIELD_MAP: dict[str, str] = {
        # Business ID
        "id": "id",
        "alias": "id",  # Yelp alias is sometimes used as identifier
        # Name
        "name": "name",
        "businessName": "name",
        "business_name": "name",
        # Rating
        "rating": "rating",
        "starRating": "rating",
        "star_rating": "rating",
        # Review count
        "review_count": "review_count",
        "reviewCount": "review_count",
        "totalReviews": "review_count",
        "total_reviews": "review_count",
        # Location
        "location": "location",
        "address": "location",
        # Categories
        "categories": "categories",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        term: str = "",
        location: str = "",
        path: str = DEFAULT_PATH,
        page_size: int = DEFAULT_PAGE_SIZE,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._term = term
        self._location = location
        self._path = path
        self._page_size = page_size
        self._api_key = api_key

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def _params(self, offset: int) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": self._page_size, "offset": offset}
        if self._term:
            params["term"] = self._term
        if self._location:
            params["location"] = self._location
        return params

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map API field names to contract names; coerce numeric and None values."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            # Coerce numeric types to str for rating and review_count.
            if mapped in {"rating", "review_count"} and val is not None and not isinstance(val, str):
                val = str(val)
            # Coerce None: location dict stays {}, categories list stays [], strings become "".
            if val is None:
                if mapped == "location":
                    val = {}
                elif mapped == "categories":
                    val = []
                else:
                    val = ""
            normalized[mapped] = val
        # Ensure location and categories always present even if omitted from response.
        normalized.setdefault("location", {})
        normalized.setdefault("categories", [])
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through Yelp business results, yielding one dict per business.

        Raises AuthenticationError immediately if api_key is absent. Terminates on
        a short-page sentinel or when offset reaches the Yelp 1000-result hard cap.
        """
        if not self._api_key:
            raise AuthenticationError(
                "yelp: api_key is required (Yelp Developer account Bearer token). "
                "See docs/reference/tos-matrix.md row R2."
            )
        offset = 0
        while True:
            if offset >= _YELP_MAX_OFFSET:
                break
            resp = await self.request(
                "GET",
                self._path,
                params=self._params(offset),
                headers=self._auth_headers(),
            )
            rows = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            if len(rows) < self._page_size:
                break
            offset += self._page_size

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract businesses list from response or raise SourceUnavailableError."""
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from Yelp Fusion: {exc}"
            ) from exc

        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected Yelp Fusion response shape "
                f"(expected dict, got {type(body).__name__})"
            )

        businesses = body.get("businesses", [])
        if not isinstance(businesses, list):
            raise SourceUnavailableError(
                f"{self.source_id}: 'businesses' is not a list in Yelp Fusion response"
            )

        return businesses

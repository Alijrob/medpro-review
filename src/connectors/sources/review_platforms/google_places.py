"""
google_places.py -- Google Places API review platform adapter (source google_places, Phase 3-E).

Google Places (via the Maps Platform Places API) provides consumer-facing ratings, review
counts, and business details for healthcare providers searchable by name and location. The
Places API Terms of Service permit API-based lookup for application use but prohibit bulk
downloads, scraping, caching beyond permitted durations, and use outside Google-attributed
display contexts. A paid Maps Platform API key is required; per-request pricing applies.

Integration method: REST_API (Google Places Text Search endpoint).

Endpoint: https://maps.googleapis.com/maps/api/place/textsearch/json
Pagination: cursor via next_page_token returned in response; absent = last page.
Auth: api_key passed as query parameter `key` (Google standard -- NOT in Authorization header).

Schema contract (6 fields):
    place_id            -- unique Google Place identifier (str)
    name                -- business/provider name (str)
    rating              -- aggregate Google rating (str, coerced from float)
    user_ratings_total  -- total number of ratings (str, coerced from int)
    formatted_address   -- full address string (str)
    reviews             -- list of review dicts (list; defaults to [] in Text Search mode;
                           populated when connector runs in Place Details mode)

Field normalization: _FIELD_MAP covers camelCase variants returned by the legacy Places API
response shape. Numeric rating and user_ratings_total are coerced to str. None reviews are
coerced to [] because Text Search results do not include reviews -- the list is only populated
when a Place Details call is chained (future extension).

ToS / Legal notes:
    - T2: API key required; paid Maps Platform account; per-request pricing.
    - ToS prohibit caching place data beyond allowed TTLs and bulk export.
    - Reviews must not be displayed without proper Google attribution.
    - Live ingest is additionally gated on the Phase 0 FCRA determination.
    See docs/reference/tos-matrix.md row R1.

LICENSE GATE: api_key must come from a paid Maps Platform project. Raises AuthenticationError
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

DEFAULT_BASE_URL = "https://maps.googleapis.com"
DEFAULT_PATH = "/maps/api/place/textsearch/json"
DEFAULT_PAGE_SIZE = 20  # Google Text Search returns up to 20 results per page

_GP_REQUIRED_FIELDS = frozenset({
    "place_id",
    "name",
    "rating",
    "user_ratings_total",
    "formatted_address",
    "reviews",
})

_YELP_MAX_OFFSET = 1000  # not used here; kept for clarity


def google_places_config(**overrides: Any) -> ConnectorConfig:
    """Build the Google Places (google_places) ConnectorConfig.

    Cursor-paginated REST API. api_key comes from the Maps Platform project.
    expected_min_records is None by default -- depends on the search query scope.

    ToS: T2 -- paid Maps Platform API key required; per-request pricing; caching
    restrictions apply. See docs/reference/tos-matrix.md row R1.
    """
    params: dict[str, Any] = dict(
        source_id="google_places",
        source_name="Google Places Provider Reviews",
        source_category=SourceCategory.REVIEW_PLATFORM,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (Google Places google_places)",
        rate_limit_per_sec=10.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class GooglePlacesConnector(SourceConnector):
    """Google Places Text Search adapter for healthcare provider reviews (google_places).

    Fetches provider listings via cursor pagination using next_page_token. Each page
    returns up to 20 results (Google's fixed Text Search page size). Pagination
    terminates when next_page_token is absent from the response.

    Response envelope:
        {
            "status": "OK",
            "results": [...],
            "next_page_token": "..."   // absent on last page
        }

    The `reviews` field is empty in Text Search results -- it is only populated by the
    Google Place Details endpoint. The contract includes reviews as a list field
    defaulting to [] so that downstream normalization handles both modes uniformly.

    ToS: api_key must be from a paid Maps Platform project. Raises AuthenticationError
    on fetch_raw() if api_key is absent.
    """

    contract = SchemaContract(
        required_fields=_GP_REQUIRED_FIELDS,
        field_types={
            "place_id": str,
            "name": str,
            "rating": str,
            "user_ratings_total": str,
            "formatted_address": str,
            "reviews": list,
        },
    )

    _FIELD_MAP: dict[str, str] = {
        # Place ID
        "place_id": "place_id",
        "placeId": "place_id",
        # Name
        "name": "name",
        "displayName": "name",
        "display_name": "name",
        # Rating
        "rating": "rating",
        # User ratings total
        "user_ratings_total": "user_ratings_total",
        "userRatingsTotal": "user_ratings_total",
        "userRatingCount": "user_ratings_total",
        "user_rating_count": "user_ratings_total",
        # Formatted address
        "formatted_address": "formatted_address",
        "formattedAddress": "formatted_address",
        "vicinity": "formatted_address",
        # Reviews
        "reviews": "reviews",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        query: str = "",
        path: str = DEFAULT_PATH,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._query = query
        self._path = path
        self._api_key = api_key

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map API field names to contract names; coerce numeric and None values."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            # Coerce numeric types to str for rating and user_ratings_total.
            if mapped in {"rating", "user_ratings_total"} and val is not None and not isinstance(val, str):
                val = str(val)
            # Coerce None: reviews list stays [], strings become "".
            if val is None:
                val = [] if mapped == "reviews" else ""
            normalized[mapped] = val
        # Ensure reviews is always present (Text Search omits it entirely).
        normalized.setdefault("reviews", [])
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through Google Places results, yielding one dict per result.

        Uses cursor pagination via next_page_token. Raises AuthenticationError
        immediately if api_key is absent.
        """
        if not self._api_key:
            raise AuthenticationError(
                "google_places: api_key is required (paid Maps Platform API key). "
                "See docs/reference/tos-matrix.md row R1."
            )
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"key": self._api_key}
            if self._query:
                params["query"] = self._query
            if page_token:
                params["pagetoken"] = page_token

            resp = await self.request("GET", self._path, params=params)
            results, next_token = self._parse_body(resp)
            for row in results:
                yield self._normalize_row(row)
            if not next_token:
                break
            page_token = next_token

    def _parse_body(self, resp: Any) -> tuple[list[dict[str, Any]], str | None]:
        """Extract (results, next_page_token) from response or raise SourceUnavailableError."""
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from Google Places: {exc}"
            ) from exc

        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected Google Places response shape "
                f"(expected dict, got {type(body).__name__})"
            )

        results = body.get("results", [])
        if not isinstance(results, list):
            raise SourceUnavailableError(
                f"{self.source_id}: 'results' is not a list in Google Places response"
            )

        next_token: str | None = body.get("next_page_token") or None
        return results, next_token

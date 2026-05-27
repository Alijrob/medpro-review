"""
healthgrades.py -- Healthgrades licensed provider data adapter (source healthgrades, Phase 3-D).

Healthgrades (healthgrades.com) provides consumer-facing provider profiles including patient
ratings, board certifications, malpractice history, and hospital affiliations. The ToS
explicitly prohibits scraping, automated access, and commercial re-use of provider data
without written permission. A licensed data agreement with CRA use authorization (if Path A)
is required before any engineering use against live endpoints.

Integration method: REST_API (Healthgrades licensed data API -- endpoint URL confirmed at
license negotiation time; DEFAULT_BASE_URL is a placeholder).

Endpoint: /v1/providers (licensed endpoint; path confirmed with Healthgrades at contract time)
Pagination: offset/limit; terminates on short-page sentinel (len(rows) < page_size).
Auth: Bearer token (api_key from signed license agreement, NOT stored in ConnectorConfig).

Schema contract (6 fields):
    npi                  -- National Provider Identifier (str)
    provider_name        -- full provider name (str)
    specialty            -- primary specialty label (str)
    rating               -- aggregate patient rating (str, coerced from float)
    review_count         -- number of patient reviews (str, coerced from int)
    board_certifications -- list of board certification record dicts

Field normalization: _FIELD_MAP covers common camelCase variants. Numeric rating and
review_count values are coerced to str to satisfy the contract's uniform str requirement
for scalar fields. None board_certifications are coerced to [] to avoid false-positive
schema drift on providers with no board certifications on record.

LICENSE GATE: Healthgrades ToS (T4) explicitly prohibits automated access and commercial
re-use. Healthgrades has enforcement history against scrapers. A signed data license
agreement is required before the api_key constructor arg can be populated. This adapter is
built and tested stub-only. Live ingest is gated on (1) signed Healthgrades license with
CRA use authorization (if Path A) and (2) Phase 0 FCRA determination. DEFAULT_BASE_URL is
a placeholder -- confirm the licensed API endpoint with Healthgrades at contract time.
See docs/reference/tos-matrix.md row D2 and source-priority.md section 4.2.
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

# Placeholder -- confirmed at license negotiation with Healthgrades.
DEFAULT_BASE_URL = "https://api.healthgrades.com"
DEFAULT_PATH = "/v1/providers"
DEFAULT_PAGE_SIZE = 100

_HG_REQUIRED_FIELDS = frozenset({
    "npi",
    "provider_name",
    "specialty",
    "rating",
    "review_count",
    "board_certifications",
})


def healthgrades_config(**overrides: Any) -> ConnectorConfig:
    """Build the Healthgrades (healthgrades) ConnectorConfig.

    Offset/limit paginated REST API. api_key and the actual base_url come from
    the signed Healthgrades data license agreement (DEFAULT_BASE_URL is a
    placeholder). expected_min_records must be set in production config after
    the license scope is negotiated.

    LICENSE GATE: Healthgrades ToS (T4) explicitly prohibits automated access and
    commercial re-use. A signed data license agreement is required before live ingest.
    See docs/reference/tos-matrix.md row D2.
    """
    params: dict[str, Any] = dict(
        source_id="healthgrades",
        source_name="Healthgrades Provider Profiles",
        source_category=SourceCategory.COMMERCIAL_DIRECTORY,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (Healthgrades healthgrades)",
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class HealthgradesConnector(SourceConnector):
    """Healthgrades licensed provider profile adapter (healthgrades).

    Fetches provider profiles via offset/limit pagination. Terminates on a
    short-page sentinel (len(rows) < page_size).

    Response envelope:
        {
            "providers": [...],
            "total": N
        }

    This shape reflects the standard Healthgrades licensed data API contract
    template; the exact field names and endpoint path must be confirmed with
    Healthgrades at license negotiation time.

    LICENSE GATE: api_key must be populated from the signed Healthgrades data
    license agreement. Raises AuthenticationError on fetch_raw() if api_key is
    absent to surface the missing license credential before any network I/O.
    """

    contract = SchemaContract(
        required_fields=_HG_REQUIRED_FIELDS,
        field_types={
            "npi": str,
            "provider_name": str,
            "specialty": str,
            "rating": str,
            "review_count": str,
            "board_certifications": list,
        },
    )

    _FIELD_MAP: dict[str, str] = {
        # NPI
        "npi": "npi",
        "nationalProviderId": "npi",
        "national_provider_id": "npi",
        # Provider name
        "provider_name": "provider_name",
        "providerName": "provider_name",
        "fullName": "provider_name",
        "full_name": "provider_name",
        # Specialty
        "specialty": "specialty",
        "primarySpecialty": "specialty",
        "primary_specialty": "specialty",
        # Rating
        "rating": "rating",
        "patientRating": "rating",
        "patient_rating": "rating",
        "overallRating": "rating",
        "overall_rating": "rating",
        # Review count
        "review_count": "review_count",
        "reviewCount": "review_count",
        "totalReviews": "review_count",
        "total_reviews": "review_count",
        # Board certifications
        "board_certifications": "board_certifications",
        "boardCertifications": "board_certifications",
        "certifications": "board_certifications",
    }

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        npi: str = "",
        provider_name: str = "",
        path: str = DEFAULT_PATH,
        page_size: int = DEFAULT_PAGE_SIZE,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._npi = npi
        self._provider_name = provider_name
        self._path = path
        self._page_size = page_size
        self._api_key = api_key

    def _auth_headers(self) -> dict[str, str]:
        if self._api_key:
            return {"Authorization": f"Bearer {self._api_key}"}
        return {}

    def _params(self, offset: int) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": self._page_size, "offset": offset}
        if self._npi:
            params["npi"] = self._npi
        if self._provider_name:
            params["name"] = self._provider_name
        return params

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map API field names to contract names; coerce numeric rating/review_count to str."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            # Coerce numeric types to str for scalar rating and review_count fields.
            if mapped in {"rating", "review_count"} and val is not None and not isinstance(val, str):
                val = str(val)
            # Coerce None: board_certifications list stays [], strings become "".
            if val is None:
                val = [] if mapped == "board_certifications" else ""
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through Healthgrades provider profiles, yielding one dict per provider.

        Raises AuthenticationError immediately if api_key is absent -- the Healthgrades
        T4 license credential must be in place before any live fetch attempt.
        """
        if not self._api_key:
            raise AuthenticationError(
                "healthgrades: api_key is required (Healthgrades T4 data license "
                "agreement must be signed before live ingest). See tos-matrix.md D2."
            )
        offset = 0
        while True:
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
        """Extract providers list from response or raise SourceUnavailableError."""
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from Healthgrades: {exc}"
            ) from exc

        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected Healthgrades response shape "
                f"(expected dict, got {type(body).__name__})"
            )

        providers = body.get("providers", [])
        if not isinstance(providers, list):
            raise SourceUnavailableError(
                f"{self.source_id}: 'providers' is not a list in Healthgrades response"
            )

        return providers

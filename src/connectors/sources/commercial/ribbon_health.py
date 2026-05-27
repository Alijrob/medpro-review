"""
ribbon_health.py -- Ribbon Health provider directory adapter (source ribbon_health, Phase 3-D).

Ribbon Health (ribbonhealth.com) is a B2B commercial provider data platform that aggregates
specialty, affiliation, location, and insurance network participation data. Access requires
a signed commercial data license agreement; live ingestion is blocked until the contract is
in place AND the Phase 0 FCRA legal gate closes.

Integration method: REST_API (Ribbon Health B2B API v1).

Endpoint: https://api.ribbonhealth.com/v1/custom/providers
Pagination: page-number via ?page=N; terminates when current_page >= total_pages in the
            response envelope.
Auth: Token authentication (api_key from signed contract, NOT stored in ConnectorConfig).

Schema contract (6 fields):
    npi            -- National Provider Identifier (str)
    provider_name  -- full provider name (str)
    specialty      -- primary specialty label (str)
    locations      -- list of practice location dicts
    insurances     -- list of accepted insurance plan dicts
    affiliations   -- list of hospital / health-system affiliation dicts

Field normalization: Ribbon Health v1 returns snake_case; _FIELD_MAP also covers common
camelCase aliases and alternative top-level key names that may appear across API versions
or in pilot/sandbox environments.

LICENSE GATE: a signed Ribbon Health data license agreement is required before the api_key
constructor arg can be populated. Engineering may build and test this adapter against stubbed
transports; live ingest is gated on (1) signed contract and (2) Phase 0 FCRA determination.
See docs/reference/tos-matrix.md row D1 and source-priority.md section 4.1.
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

DEFAULT_BASE_URL = "https://api.ribbonhealth.com"
DEFAULT_PATH = "/v1/custom/providers"
DEFAULT_PAGE_SIZE = 100

_RH_REQUIRED_FIELDS = frozenset({
    "npi",
    "provider_name",
    "specialty",
    "locations",
    "insurances",
    "affiliations",
})


def ribbon_health_config(**overrides: Any) -> ConnectorConfig:
    """Build the Ribbon Health (ribbon_health) ConnectorConfig.

    REST API with page-number pagination. api_key comes from the signed Ribbon
    Health data license agreement and is injected as a constructor arg (not in
    ConnectorConfig). expected_min_records depends on query scope (NPI lookup vs.
    full-directory ingest) and must be set in production configuration.

    LICENSE GATE: a signed Ribbon Health commercial data license (T3, source D1) is
    required before any live ingest. See docs/reference/tos-matrix.md row D1.
    """
    params: dict[str, Any] = dict(
        source_id="ribbon_health",
        source_name="Ribbon Health Provider Directory",
        source_category=SourceCategory.COMMERCIAL_DIRECTORY,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (Ribbon Health ribbon_health)",
        rate_limit_per_sec=10.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class RibbonHealthConnector(SourceConnector):
    """Ribbon Health provider directory adapter (ribbon_health).

    Looks up provider records by NPI or name using page-number pagination.
    Terminates when current_page reaches total_pages in the API pagination envelope.

    Response envelope:
        {
            "data": [...providers...],
            "pagination": {"current_page": N, "total_pages": N, "count": N}
        }

    LICENSE GATE: api_key must be populated from the signed Ribbon Health data license
    agreement. The connector raises AuthenticationError on fetch_raw() if api_key is
    absent, surfacing the missing license credential before any network I/O is attempted.
    """

    contract = SchemaContract(
        required_fields=_RH_REQUIRED_FIELDS,
        field_types={
            "npi": str,
            "provider_name": str,
            "specialty": str,
            "locations": list,
            "insurances": list,
            "affiliations": list,
        },
    )

    # Ribbon Health v1 is snake_case; map common camelCase and alias variants too.
    _FIELD_MAP: dict[str, str] = {
        # NPI
        "npi": "npi",
        "nationalProviderId": "npi",
        "national_provider_id": "npi",
        # Provider name
        "provider_name": "provider_name",
        "name": "provider_name",
        "fullName": "provider_name",
        "full_name": "provider_name",
        # Specialty -- list variant collapsed in _normalize_row
        "specialty": "specialty",
        "primarySpecialty": "specialty",
        "primary_specialty": "specialty",
        "specialties": "specialty",
        # Locations
        "locations": "locations",
        "practice_locations": "locations",
        "practiceLocations": "locations",
        # Insurances
        "insurances": "insurances",
        "accepted_insurances": "insurances",
        "acceptedInsurances": "insurances",
        "insurance_plans": "insurances",
        # Affiliations
        "affiliations": "affiliations",
        "hospital_affiliations": "affiliations",
        "hospitalAffiliations": "affiliations",
        "org_affiliations": "affiliations",
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
            return {"Authorization": f"Token {self._api_key}"}
        return {}

    def _params(self, page: int) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "page_size": self._page_size}
        if self._npi:
            params["npi"] = self._npi
        if self._provider_name:
            params["name"] = self._provider_name
        return params

    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Map API field names to contract names; coerce list specialty to str."""
        normalized: dict[str, Any] = {}
        for key, val in row.items():
            mapped = self._FIELD_MAP.get(key, key)
            # Ribbon may return specialties as a list; use first element as primary.
            if mapped == "specialty" and isinstance(val, list):
                val = val[0] if val else ""
            # Coerce None: lists stay [], strings become "".
            if val is None:
                val = [] if mapped in {"locations", "insurances", "affiliations"} else ""
            normalized[mapped] = val
        return normalized

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Page through Ribbon Health providers, yielding one dict per provider.

        Raises AuthenticationError immediately if api_key is absent -- the license
        credential must be in place before any live fetch attempt.
        """
        if not self._api_key:
            raise AuthenticationError(
                "ribbon_health: api_key is required (Ribbon Health commercial data "
                "license must be signed before live ingest). See tos-matrix.md D1."
            )
        page = 1
        while True:
            resp = await self.request(
                "GET",
                self._path,
                params=self._params(page),
                headers=self._auth_headers(),
            )
            rows, total_pages = self._parse_body(resp)
            if not rows:
                break
            for row in rows:
                yield self._normalize_row(row)
            if page >= total_pages:
                break
            page += 1

    def _parse_body(self, resp: Any) -> tuple[list[dict[str, Any]], int]:
        """Extract (data_list, total_pages) from response or raise SourceUnavailableError."""
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from Ribbon Health: {exc}"
            ) from exc

        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected Ribbon Health response shape "
                f"(expected dict, got {type(body).__name__})"
            )

        data = body.get("data", [])
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: 'data' is not a list in Ribbon Health response"
            )

        pagination = body.get("pagination", {})
        if not isinstance(pagination, dict):
            pagination = {}
        total_pages = pagination.get("total_pages", 1)
        if not isinstance(total_pages, int) or total_pages < 1:
            total_pages = 1

        return data, total_pages

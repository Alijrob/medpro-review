"""
nppes.py — NPPES / NPI Registry adapter (source F1, component C10, Phase 2-B.1).

NPPES is the identity anchor for the whole platform: every licensed US provider has
an NPI, and all downstream identity resolution (C12+) keys on it. This adapter is the
first concrete `SourceConnector` (the C9 framework, Phase 2-A, is what it builds on).

Mode: **API lookup** — a per-provider query against the public CMS NPPES API
(`https://npiregistry.cms.hhs.gov/api/?version=2.1`), paginated via `skip`. The API is
free, keyless, and CC0/public-domain (T1/L0 in docs/reference/source-priority.md). The
monthly **bulk-download** mode (the full dissemination file) is a separate follow-on
adapter; this one covers the on-demand lookup the report pipeline uses.

Output is `RawRecord`s (one per NPPES result, pre-normalization). Mapping NPPES JSON
into a typed `CanonicalProviderProfile` is C11 (Normalization Layer, Phase 2-D) — this
adapter deliberately does no normalization beyond a schema-drift contract check.

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing here
hits the network on import; the tests drive it with a stubbed transport. Running it
against the live endpoint is a deploy-time action behind that gate.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import Field, model_validator

from schema.v1.common import MedproBaseModel, SourceCategory

from ..base import SourceConnector
from ..config import ConnectorConfig
from ..contract import SchemaContract
from ..errors import PermanentError, SourceUnavailableError
from ..models import IntegrationMethod

DEFAULT_BASE_URL = "https://npiregistry.cms.hhs.gov"
API_PATH = "/api/"
API_VERSION = "2.1"
# NPPES caps a page at 200 results and rejects skip > 1000 (so at most 1200 results
# are reachable for one query — narrow the query, don't try to page past the cap).
PAGE_SIZE = 200
MAX_SKIP = 1000


def nppes_config(**overrides: Any) -> ConnectorConfig:
    """Build the F1 ConnectorConfig (identity + sane operational defaults)."""
    params: dict[str, Any] = dict(
        source_id="F1",
        source_name="NPPES NPI Registry",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (NPPES F1)",
        # NPPES publishes no formal rate limit; spacing requests is courteous + safe.
        rate_limit_per_sec=5.0,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class NppesQuery(MedproBaseModel):
    """A single NPPES lookup. At least one of number / last_name / organization_name
    must be set (the API rejects a query with only `version`)."""

    number: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="A specific 10-digit NPI. When set, other criteria are ignored by NPPES.",
    )
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    organization_name: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    taxonomy_description: str | None = Field(default=None, max_length=200)
    enumeration_type: Literal["NPI-1", "NPI-2"] | None = Field(
        default=None,
        description="NPI-1 = individual provider, NPI-2 = organization.",
    )

    @model_validator(mode="after")
    def _require_a_criterion(self) -> "NppesQuery":
        if not (self.number or self.last_name or self.organization_name):
            raise ValueError(
                "NppesQuery requires at least one of: number, last_name, organization_name"
            )
        return self

    def to_params(self) -> dict[str, Any]:
        """The query as NPPES API params (only the fields that are set)."""
        fields = (
            "number",
            "first_name",
            "last_name",
            "organization_name",
            "city",
            "state",
            "taxonomy_description",
            "enumeration_type",
        )
        return {f: getattr(self, f) for f in fields if getattr(self, f) is not None}


class NppesConnector(SourceConnector):
    """NPPES NPI Registry API-lookup adapter (F1).

    Pages through `results` via `skip`, yields each provider record dict. `run()`
    (inherited) wraps each in a provenance-hashed `RawRecord`, validates it against
    `contract`, and reports a `SourceHealthRecord`.
    """

    # NPPES results always carry these top-level keys; a drift here is a real schema
    # change (risk R6) and surfaces as SCHEMA_DRIFT health rather than silent breakage.
    contract = SchemaContract(
        required_fields=frozenset(
            {"number", "enumeration_type", "basic", "addresses", "taxonomies"}
        ),
        field_types={
            "enumeration_type": str,
            "basic": dict,
            "addresses": list,
            "taxonomies": list,
        },
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        query: NppesQuery,
        page_size: int = PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._query = query
        self._page_size = page_size

    def _params(self, skip: int) -> dict[str, Any]:
        params: dict[str, Any] = {
            "version": API_VERSION,
            "limit": self._page_size,
            "skip": skip,
        }
        params.update(self._query.to_params())
        return params

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        skip = 0
        while True:
            resp = await self.request("GET", API_PATH, params=self._params(skip))
            body = self._parse_body(resp)

            # NPPES signals a bad query with HTTP 200 + an `Errors` array, not a 4xx.
            errors = body.get("Errors")
            if errors:
                raise PermanentError(f"{self.source_id}: NPPES query rejected: {errors}")

            results = body.get("results") or []
            for item in results:
                yield item

            # Stop when the source returns a short page or we reach the API skip cap.
            if len(results) < self._page_size or skip + self._page_size > MAX_SKIP:
                break
            skip += self._page_size

    @staticmethod
    def _parse_body(resp: Any) -> dict[str, Any]:
        try:
            body = resp.json()
        except Exception as exc:  # malformed/HTML response from an upstream fault
            raise SourceUnavailableError(f"NPPES: non-JSON response: {exc}") from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"NPPES: unexpected response shape: {type(body).__name__}"
            )
        return body

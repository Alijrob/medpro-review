"""
clinical_trials.py -- ClinicalTrials.gov adapter (source A2, component C10, Phase 2-B.9).

ClinicalTrials.gov (A2) is the NIH registry of clinical trials. Investigator-level
records identify which providers are (or were) principal investigators or study
coordinators. This signal is:
  - High-value for academic medical center physicians and research subspecialists.
  - Low-value for generalists / primary care providers (most have no trials).
  - Narrow but trivial to add alongside PubMed (A1) since it uses the same
    on-demand-per-provider lookup pattern.

The source-priority matrix notes: "V=2 because it enriches a small provider subset.
Build with A1 batch." (source-priority.md, A2)

Integration: ClinicalTrials.gov API v2 (stable public JSON API, public domain, no
API key required). Per-provider query by investigator name using cursor-based
pagination (``pageToken``).

API overview:
  Base URL: ``https://clinicaltrials.gov``
  Endpoint: ``GET /api/v2/studies``
  Query:    ``query.term = "{name}[Investigator]"``
  Pagination: ``pageSize`` (number of studies per page) + ``pageToken`` (cursor
              string returned by each response; absent when the last page is reached).
  Response: ``{"studies": [...], "nextPageToken": "...", "totalCount": N}``

Schema contract:
  Guards ``protocolSection`` (dict) on each study record. This is the top-level
  structural key that must be present for the record to be useful. Inner sub-fields
  (``identificationModule.nctId``, ``statusModule.overallStatus``,
  ``contactsLocationsModule.overallOfficials``) are accessed by C11 normalization (Phase
  2-D); they are not guarded here to avoid false-positive drift if ClinicalTrials.gov
  restructures inner sub-modules.

Output is ``RawRecord``s (pre-normalization). Extracting NCT ID, trial status, phase,
and investigator role is C11 (Phase 2-D).

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing here
hits the network on import; tests drive it with stubbed transports. A2 is public domain
(NIH), T1/L0 (source-priority.md).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from schema.v1.common import SourceCategory

from ..base import SourceConnector
from ..config import ConnectorConfig
from ..contract import SchemaContract
from ..errors import SourceUnavailableError
from ..models import IntegrationMethod

DEFAULT_BASE_URL = "https://clinicaltrials.gov"
STUDIES_PATH = "/api/v2/studies"

# Number of studies per page. ClinicalTrials.gov API v2 supports up to 1000.
# 200 is conservative and keeps response payloads manageable.
DEFAULT_PAGE_SIZE = 200


def clinical_trials_config(**overrides: Any) -> ConnectorConfig:
    """Build the A2 ConnectorConfig (identity + operational defaults).

    ClinicalTrials.gov does not publish a formal rate limit for the v2 API.
    5 req/s is a conservative, courteous default consistent with other federal
    open-data adapters in this batch. There is no API key required or available.

    ``expected_min_records`` is ``None`` by default -- most providers have zero
    trials; set a floor only for batch pipelines over academic medical center
    provider lists.
    """
    params: dict[str, Any] = dict(
        source_id="A2",
        source_name="ClinicalTrials.gov",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (ClinicalTrials.gov A2)",
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class ClinicalTrialsConnector(SourceConnector):
    """ClinicalTrials.gov API v2 adapter (A2).

    Fetches all clinical trials where ``investigator_name`` appears as an
    investigator (``[Investigator]`` query term), using cursor-based pagination
    via the ``pageToken`` field in each response.

    Pagination:
      - First request: no ``pageToken`` (omitted from params).
      - Subsequent requests: ``pageToken`` value from the previous response.
      - Stops when the response does not contain a ``nextPageToken`` key (last page).

    The adapter yields each study dict as returned by the API. C11 normalization
    (Phase 2-D) extracts the NCT ID, status, phase, and the investigator's role
    (principal investigator vs. sub-investigator).

    Investigator name disambiguation (which trials actually belong to the target
    provider) is a C11 concern, not the adapter's.
    """

    # Guards the top-level structural key on every ClinicalTrials.gov study record.
    # Inner sub-modules (identificationModule, statusModule, etc.) are not guarded
    # to avoid false-positive drift if ClinicalTrials.gov reorganizes its schema.
    contract = SchemaContract(
        required_fields=frozenset({"protocolSection"}),
        field_types={"protocolSection": dict},
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        investigator_name: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._investigator_name = investigator_name
        self._page_size = page_size

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Yield one study dict per matching ClinicalTrials.gov record.

        Uses cursor-based pagination: ``pageToken`` from each response is passed
        as a query parameter to the next request. Pagination stops when
        ``nextPageToken`` is absent from the response (last page sentinel).
        """
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "query.term": f"{self._investigator_name}[Investigator]",
                "pageSize": self._page_size,
                "format": "json",
            }
            if page_token is not None:
                params["pageToken"] = page_token

            resp = await self.request("GET", STUDIES_PATH, params=params)
            studies, next_token = self._parse_body(resp)

            for study in studies:
                yield study

            if next_token is None:
                break  # Last page -- cursor exhausted.
            page_token = next_token

    def _parse_body(self, resp: Any) -> tuple[list[dict[str, Any]], str | None]:
        """Extract (studies_list, next_page_token) from a ClinicalTrials.gov response.

        Expected response shape:
            {
              "studies": [...],
              "nextPageToken": "...",   # absent on the last page
              "totalCount": N           # informational; not used for pagination
            }
        """
        try:
            body = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from ClinicalTrials.gov: {exc}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected ClinicalTrials.gov response shape "
                f"(expected dict, got {type(body).__name__})"
            )
        studies = body.get("studies")
        if not isinstance(studies, list):
            raise SourceUnavailableError(
                f"{self.source_id}: missing or invalid 'studies' list in "
                f"ClinicalTrials.gov response"
            )
        next_token = body.get("nextPageToken")  # None if key is absent = last page
        return studies, next_token

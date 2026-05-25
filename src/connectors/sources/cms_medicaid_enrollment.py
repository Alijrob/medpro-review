"""
cms_medicaid_enrollment.py -- CMS Medicaid Provider Enrollment adapter
(source I2, component C10, Phase 2-B.6).

CMS Medicaid Provider Enrollment (I2) covers Medicaid participation records
served as CC0 open data on data.cms.gov. Medicaid is state-administered: each
state runs its own program, but CMS aggregates national enrollment data and
publishes it through the Socrata SODA 2.0 API on data.cms.gov.

I2 is the natural companion to I1 (Medicare Enrollment): while I1 tells you
whether a provider participates in Medicare, I2 tells you whether they
participate in Medicaid. This is the key coverage signal for:
  - Primary care physicians (high Medicaid panel penetration)
  - Pediatricians (CHIP + Medicaid for children)
  - OBGYNs (Medicaid is the largest payer for deliveries in the US)
  - Federally Qualified Health Centers (FQHCs)

A provider absent from both I1 and I2 is a strong signal of private-pay-only
or cash-only practice. A provider present in I2 but absent from I1 signals
Medicaid-only participation. Both patterns are meaningful to report consumers.

The adapter fetches a single `data.cms.gov` SODA dataset. It uses the same
pagination idiom as F4 (Care Compare) and I1:
  - ``$limit`` + ``$offset`` + ``$order=:id``
  - Short-page sentinel termination (SODA 2.0 has no response envelope)
  - No API key required for public datasets

Dataset ID note:
  CMS periodically refreshes datasets; the default ``dataset_id`` should be
  verified against ``data.cms.gov/provider-data`` or
  ``data.cms.gov/provider-characteristics/medicaid`` before first live ingest.
  Override at construction time if CMS issues a new dataset:
      CmsMedicaidEnrollmentConnector(cfg, dataset_id="new-id-here")

Schema contract note:
  CMS Medicaid enrollment field naming should be confirmed against the live
  dataset schema before first live ingest. The contract guards 5 fields that
  are expected to be present on any CMS Medicaid provider enrollment record:
  NPI (identity anchor), name fields (identity confirmation), state code
  (critical -- Medicaid is state-administered), and provider type. Extra
  columns pass through without raising SCHEMA_DRIFT. If field names differ on
  the live dataset, update ``_MEDICAID_REQUIRED_FIELDS`` and
  ``CmsMedicaidEnrollmentConnector.contract`` accordingly.

Output is ``RawRecord``s (pre-normalization). Turning enrollment rows into
typed participation signals on a ``CanonicalProviderProfile`` is C11
(Phase 2-D).

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination.
Nothing here hits the network on import; tests drive it with a stubbed
transport. I2 is T1/L0 open-data (CC0, published on data.cms.gov/provider-data).
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

DEFAULT_BASE_URL = "https://data.cms.gov"

# CMS Medicaid Provider Enrollment dataset.
# Verify this ID against data.cms.gov/provider-data or
# data.cms.gov/provider-characteristics/medicaid before live ingest.
# Override at construction if CMS supersedes this dataset:
#   CmsMedicaidEnrollmentConnector(cfg, dataset_id="new-id-here")
#
# Note: Medicaid datasets are state-administered and the CMS aggregated
# national enrollment view may span multiple SODA datasets. If CMS splits
# the data by state or program type, use the most complete national-level
# dataset covering individual NPI-level enrollment records.
DEFAULT_DATASET_ID = "pcbs-9zei"  # PLACEHOLDER -- must be verified before live ingest

# Socrata allows up to 50 000 per request; 5 000 is conservative and keeps
# individual requests from timing out on slow connections.
PAGE_LIMIT = 5_000

# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------

# Fields expected in every CMS Medicaid provider enrollment row.
# Guards the identity anchor (NPI), name fields (identity confirmation),
# state code (critical: Medicaid is state-administered; state is the primary
# grouping dimension for Medicaid participation data), and provider type
# (specialty signal for primary care + pediatric coverage analysis).
#
# These 5 fields are the expected minimum for a Medicaid enrollment record
# keyed on NPI. Extra columns added by CMS pass through without SCHEMA_DRIFT.
# Verify these field names against the live dataset schema before first live
# ingest and update accordingly.
_MEDICAID_REQUIRED_FIELDS = frozenset({
    "npi",
    "last_name",
    "first_name",
    "state_cd",
    "provider_type_desc",
})


def cms_medicaid_enrollment_config(**overrides: Any) -> ConnectorConfig:
    """Build the I2 ConnectorConfig (identity + operational defaults).

    No API key is needed -- data.cms.gov SODA datasets are publicly accessible
    without authentication. An optional ``X-App-Token`` header would raise the
    rate-limit ceiling but is not required for a single scheduled monthly ingest.

    ``expected_min_records`` is left as ``None`` by default. In production, set
    to a value consistent with the current CMS dataset size. Medicaid enrollment
    data is less concentrated than Medicare (more state-level variation); a
    reasonable production floor is on the order of tens of thousands to hundreds
    of thousands of records depending on the specific national dataset.
    Example: ``cms_medicaid_enrollment_config(expected_min_records=500_000)``.
    """
    params: dict[str, Any] = dict(
        source_id="I2",
        source_name="CMS Medicaid Enrollment",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (CMS Medicaid Enrollment I2)",
        # data.cms.gov does not publish a rate limit for unauthenticated SODA
        # access; 5 req/s is conservative and leaves headroom.
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class CmsMedicaidEnrollmentConnector(SourceConnector):
    """CMS Medicaid Provider Enrollment adapter (I2).

    Fetches a single ``data.cms.gov`` SODA 2.0 dataset covering Medicaid
    provider enrollment records. Uses the same pagination idiom as F4 and I1:
    ``$limit``/``$offset``/``$order=:id``, short-page sentinel termination.

    A single ``SchemaContract`` guards 5 fields (see ``_MEDICAID_REQUIRED_FIELDS``).
    Contract field names should be verified against the live dataset schema before
    first live ingest. Extra columns (which CMS adds occasionally) pass through
    without raising SCHEMA_DRIFT.

    Unlike I1 (two datasets, ``contract = None``, per-record-type contracts
    applied in ``fetch_raw``), I2 is a single-dataset adapter that uses the
    standard base-class contract path -- simpler because there is no record-type
    ambiguity.

    The ``dataset_id`` is a configurable constructor arg. Override it if CMS
    refreshes the dataset or if the default has been superseded:
        CmsMedicaidEnrollmentConnector(cfg, dataset_id="new-id-here")

    C11 normalization (Phase 2-D) turns yielded rows into typed Medicaid
    participation signals on a ``CanonicalProviderProfile``.
    """

    contract = SchemaContract(
        required_fields=_MEDICAID_REQUIRED_FIELDS,
        field_types={
            "npi": str,
            "last_name": str,
            "first_name": str,
            "state_cd": str,
            "provider_type_desc": str,
        },
    )

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        dataset_id: str = DEFAULT_DATASET_ID,
        page_limit: int = PAGE_LIMIT,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._dataset_id = dataset_id
        self._page_limit = page_limit

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Yield one dict per Medicaid enrollment row, paginated via SODA 2.0.

        The base-class ``run()`` applies ``self.contract`` to each yielded row.
        Any ``SchemaDriftError`` raised by the contract propagates to ``run()``'s
        exception handler, which converts it into a SCHEMA_DRIFT health status.
        """
        resource_path = f"/resource/{self._dataset_id}.json"
        offset = 0
        while True:
            resp = await self.request(
                "GET",
                resource_path,
                params={
                    "$limit": self._page_limit,
                    "$offset": offset,
                    "$order": ":id",
                },
            )
            rows = self._parse_body(resp)
            for row in rows:
                yield row
            # Short page (or empty): the dataset is exhausted.
            if len(rows) < self._page_limit:
                break
            offset += self._page_limit

    def _parse_body(self, resp: Any) -> list[dict[str, Any]]:
        """Extract the SODA JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from data.cms.gov "
                f"(dataset {self._dataset_id}): {exc}"
            ) from exc
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected CMS response shape "
                f"(dataset {self._dataset_id}: expected list, got {type(data).__name__})"
            )
        return data

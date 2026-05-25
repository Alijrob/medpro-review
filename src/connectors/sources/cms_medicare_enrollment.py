"""
cms_medicare_enrollment.py -- CMS Medicare Physician Enrollment adapter
(source I1, component C10, Phase 2-B.5).

CMS Medicare Physician Enrollment (I1) covers two complementary signals on a
provider's Medicare relationship, both served as CC0 open data on data.cms.gov:

  1. **Enrollment records** -- providers actively enrolled in Medicare
     Fee-For-Service (FFS). Contains NPI, CMS enrollment ID, provider type, and
     practice state. Partially overlaps with F4 (Care Compare) but I1's enrollment
     file is the authoritative participation indicator: a provider can appear in
     Care Compare without being currently enrolled (e.g., revoked, withdrawn, or
     group-only). The enrollment record establishes that a provider is (or was)
     a recognized Medicare participant.

  2. **Opt-Out Affidavits** -- providers who have formally opted out of Medicare.
     An opt-out is a high-value red flag signal: the provider has elected to be
     paid privately, bypassing Medicare rates entirely. Patients who see an
     opted-out provider pay out-of-pocket and cannot be reimbursed by Medicare.
     Presence on this list is a critical signal for Medicare beneficiaries.
     The affidavit record includes the opt-out effective + end dates and whether
     the provider can still order/refer Medicare services for patients.

Both datasets are CC0/public domain (T1/L0) published on data.cms.gov via the
Socrata SODA 2.0 API. Same pagination pattern as F4 (Care Compare):
  - ``$limit`` + ``$offset`` + ``$order=:id``
  - Short-page sentinel termination (SODA 2.0 has no response envelope)
  - No API key required for public datasets

This adapter fetches **both datasets in a single run()** -- enrollment first,
then opt-out. Each yielded dict includes a ``_record_type`` tag
(``"enrollment"`` or ``"opt_out"``) so C11 normalization (Phase 2-D) can route
each row to the correct signal extractor on a ``CanonicalProviderProfile`` without
re-parsing the source. The per-dataset-type schema contracts
(``enrollment_contract`` and ``opt_out_contract``) are applied inside
``fetch_raw``; the base-class single-contract path is suppressed
(``contract = None``).

Dataset IDs default to the current data.cms.gov identifiers but are configurable
as constructor args -- CMS has refreshed datasets before. Verify both against
``data.cms.gov/provider-characteristics`` before first live ingest.

Output is ``RawRecord``s (pre-normalization). Turning enrollment/opt-out rows into
typed participation signals on a ``CanonicalProviderProfile`` is C11 (Phase 2-D).

LEGAL GATE: live ingestion is governed by the Phase 0 FCRA determination. Nothing
here hits the network on import; tests drive it with a stubbed transport. I1 is
T1/L0 open-data (CC0, published on data.cms.gov/provider-data).
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

# Medicare Fee-For-Service Public Provider Enrollment.
# Verify against data.cms.gov/provider-characteristics/medicare-provider-supplier
# -enrollment/medicare-fee-for-service-public-provider-enrollment before live
# ingest. Override at construction if CMS supersedes this dataset:
#   CmsMedicareEnrollmentConnector(cfg, enrollment_dataset_id="new-id", ...)
DEFAULT_ENROLLMENT_DATASET_ID = "s2uc-8wxp"

# Medicare Opt-Out Affidavits.
# Verify against data.cms.gov/provider-characteristics/medicare-provider-supplier
# -enrollment/opt-out-affidavits before live ingest. Override similarly.
DEFAULT_OPT_OUT_DATASET_ID = "7tef-9pja"

# Socrata allows up to 50 000 per request; 5 000 is conservative and keeps
# individual requests from timing out on slow connections.
PAGE_LIMIT = 5_000

# _record_type tag key + values written into each yielded row.
# C11 normalization (Phase 2-D) uses these to route records to the
# correct signal extractor without re-inspecting the payload shape.
_RECORD_TYPE_KEY = "_record_type"
RECORD_TYPE_ENROLLMENT = "enrollment"
RECORD_TYPE_OPT_OUT = "opt_out"

# ---------------------------------------------------------------------------
# Schema contracts
# ---------------------------------------------------------------------------

# Fields expected in every Medicare FFS enrollment row.
# Guards NPI (identity anchor), CMS enrollment identity (enroll_id),
# provider classification (provider_type_desc), and practice state (state_cd).
# first_name is guarded because it anchors identity resolution.
# org_name and middle_name are excluded: both are optional for individual providers.
_ENROLLMENT_REQUIRED_FIELDS = frozenset({
    "npi",
    "last_name",
    "first_name",
    "enroll_id",
    "provider_type_desc",
    "state_cd",
})

# Fields expected in every opt-out affidavit row.
# optout_end_date is intentionally excluded: it is null for providers currently
# within their two-year opt-out window (active opt-out), which is the common
# case on this list. Requiring it would cause false-positive drift alerts on
# nearly every row. C11 normalization treats absent end_date as "active opt-out".
_OPT_OUT_REQUIRED_FIELDS = frozenset({
    "npi",
    "last_name",
    "first_name",
    "optout_effective_date",
    "order_refer_flag",
})


def cms_medicare_enrollment_config(**overrides: Any) -> ConnectorConfig:
    """Build the I1 ConnectorConfig (identity + operational defaults).

    No API key is needed -- both data.cms.gov SODA datasets are publicly
    accessible without authentication. An optional ``X-App-Token`` header would
    raise the rate-limit ceiling but is not required for a single scheduled
    monthly ingest.

    ``expected_min_records`` covers both datasets combined. In production, set
    to a value consistent with current CMS dataset sizes (enrollment is ~1 million
    providers; opt-out list is tens of thousands -- combined well over 1 million).
    Example: ``cms_medicare_enrollment_config(expected_min_records=900_000)``.
    """
    params: dict[str, Any] = dict(
        source_id="I1",
        source_name="CMS Medicare Enrollment",
        source_category=SourceCategory.FEDERAL,
        integration_method=IntegrationMethod.REST_API,
        base_url=DEFAULT_BASE_URL,
        user_agent="medpro-review-connector/0.1 (CMS Medicare Enrollment I1)",
        # data.cms.gov does not publish a rate limit for unauthenticated SODA
        # access; 5 req/s is conservative and leaves headroom.
        rate_limit_per_sec=5.0,
        expected_min_records=None,
    )
    params.update(overrides)
    return ConnectorConfig(**params)


class CmsMedicareEnrollmentConnector(SourceConnector):
    """CMS Medicare Physician Enrollment + Opt-Out Affidavits adapter (I1).

    Fetches from two data.cms.gov SODA 2.0 datasets in a single run():

    1. **Enrollment** (``enrollment_dataset_id``): Medicare FFS enrollment records.
       Each yielded row gets ``_record_type = "enrollment"``.
    2. **Opt-Out** (``opt_out_dataset_id``): opt-out affidavit records -- a high-
       value red flag signal. Each yielded row gets ``_record_type = "opt_out"``.

    Both use the Socrata SODA 2.0 pagination idiom (``$limit``/``$offset``/
    ``$order=:id``, short-page sentinel termination), identical to F4.

    The two per-dataset-type contracts (``enrollment_contract`` and
    ``opt_out_contract``) are applied inside ``fetch_raw`` before each row is
    yielded. The base-class single-contract path is intentionally suppressed
    (``contract = None``). Any drift in either dataset raises ``SchemaDriftError``,
    which ``run()`` catches and converts into a SCHEMA_DRIFT health status.

    If enrollment fetching succeeds but the opt-out dataset fails, ``run()``
    returns ``FetchStatus.PARTIAL`` -- enrollment records are preserved.

    C11 normalization (Phase 2-D) routes each yielded record by ``_record_type``
    to the correct signal extractor on the ``CanonicalProviderProfile``.
    """

    # Per-record-type contracts. Applied explicitly inside fetch_raw.
    enrollment_contract = SchemaContract(
        required_fields=_ENROLLMENT_REQUIRED_FIELDS,
        field_types={
            "npi": str,
            "last_name": str,
            "first_name": str,
            "enroll_id": str,
            "provider_type_desc": str,
            "state_cd": str,
        },
    )
    opt_out_contract = SchemaContract(
        required_fields=_OPT_OUT_REQUIRED_FIELDS,
        field_types={
            "npi": str,
            "last_name": str,
            "first_name": str,
            "optout_effective_date": str,
            "order_refer_flag": str,
        },
    )
    # Suppress base-class single-contract validation; per-record-type contracts
    # are applied in fetch_raw before each yield.
    contract = None

    def __init__(
        self,
        config: ConnectorConfig,
        *,
        enrollment_dataset_id: str = DEFAULT_ENROLLMENT_DATASET_ID,
        opt_out_dataset_id: str = DEFAULT_OPT_OUT_DATASET_ID,
        page_limit: int = PAGE_LIMIT,
        **kwargs: Any,
    ) -> None:
        super().__init__(config, **kwargs)
        self._enrollment_dataset_id = enrollment_dataset_id
        self._opt_out_dataset_id = opt_out_dataset_id
        self._page_limit = page_limit

    async def fetch_raw(self) -> AsyncIterator[dict[str, Any]]:
        """Yield enrollment rows then opt-out rows, each tagged with _record_type.

        Enrollment pass runs to completion before the opt-out pass begins.
        A ``SchemaDriftError`` (or any ``ConnectorError``) raised in either pass
        propagates to ``run()``'s exception handler.
        """
        # Pass 1: enrollment records
        async for row in self._soda_pages(self._enrollment_dataset_id):
            row[_RECORD_TYPE_KEY] = RECORD_TYPE_ENROLLMENT
            self.enrollment_contract.validate(row)
            yield row
        # Pass 2: opt-out affidavit records
        async for row in self._soda_pages(self._opt_out_dataset_id):
            row[_RECORD_TYPE_KEY] = RECORD_TYPE_OPT_OUT
            self.opt_out_contract.validate(row)
            yield row

    async def _soda_pages(self, dataset_id: str) -> AsyncIterator[dict[str, Any]]:
        """Page through a data.cms.gov SODA 2.0 dataset, yielding one dict per row.

        Terminates when the response array is shorter than ``page_limit`` (the
        Socrata short-page sentinel -- the source is exhausted). An empty array
        also terminates. Stable ``$order=:id`` prevents record shifts between
        pages if CMS updates the dataset mid-ingest.
        """
        offset = 0
        resource_path = f"/resource/{dataset_id}.json"
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
            rows = self._parse_body(resp, dataset_id)
            for row in rows:
                yield row
            # Short page (or empty): the dataset is exhausted.
            if len(rows) < self._page_limit:
                break
            offset += self._page_limit

    def _parse_body(self, resp: Any, dataset_id: str) -> list[dict[str, Any]]:
        """Extract the SODA JSON array or raise SourceUnavailableError."""
        try:
            data = resp.json()
        except Exception as exc:
            raise SourceUnavailableError(
                f"{self.source_id}: non-JSON response from data.cms.gov "
                f"(dataset {dataset_id}): {exc}"
            ) from exc
        if not isinstance(data, list):
            raise SourceUnavailableError(
                f"{self.source_id}: unexpected CMS response shape "
                f"(dataset {dataset_id}: expected list, got {type(data).__name__})"
            )
        return data

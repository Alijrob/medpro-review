"""
fetch.py -- fetch_source_activity: fetch raw records for one source + NPI (C10 wrapper).

Thin Temporal activity. Business logic lives in the C10 connectors.

LEGAL GATE: live network calls are blocked until Phase 0 legal gate is cleared.
This activity will return fetch_status="failed" in any environment without live
connector config (which is expected during development). The workflow handles
partial/empty results gracefully.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from temporalio import activity

from connectors.config import ConnectorConfig
from connectors.errors import ConnectorError
from connectors.models import FetchStatus, RawRecord
from schema.v1.common import SourceCategory

from ..models import FetchSourceInput, FetchSourceOutput

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connector factory
# ---------------------------------------------------------------------------
# Maps source_id -> (connector_class, config_factory, extra_kwargs_builder)
# extra_kwargs_builder(npi) returns the kwargs specific to that connector.

def _build_connector_and_config(source_id: str, npi: str) -> tuple[Any, ConnectorConfig]:
    """
    Return (connector_instance, config) for the given source_id and NPI.

    Raises KeyError if source_id is not recognised.
    Raises ConnectorError (or subclass) if the connector cannot be instantiated.
    """
    from connectors.sources import (
        ClinicalTrialsConnector,
        CmsCareCompareConnector,
        CmsMedicaidEnrollmentConnector,
        CmsMedicareEnrollmentConnector,
        NppesConnector,
        NppesQuery,
        OigLeieConnector,
        PubmedConnector,
        SamGovConnector,
        clinical_trials_config,
        cms_care_compare_config,
        cms_medicaid_enrollment_config,
        cms_medicare_enrollment_config,
        nppes_config,
        oig_leie_config,
        pubmed_config,
        sam_gov_config,
    )

    import os

    if source_id == "F1":
        cfg = nppes_config()
        return NppesConnector(cfg, query=NppesQuery(number=npi)), cfg

    if source_id == "F2":
        cfg = oig_leie_config()
        return OigLeieConnector(cfg), cfg

    if source_id == "F3":
        # SAM.gov requires an API key. Read from env; fall back to empty string
        # (live requests will fail -- expected under legal gate).
        api_key = os.environ.get("SAM_GOV_API_KEY", "")
        cfg = sam_gov_config()
        return SamGovConnector(cfg, api_key=api_key), cfg

    if source_id == "F4":
        # CMS Care Compare: bulk dataset connector, no NPI param.
        cfg = cms_care_compare_config()
        return CmsCareCompareConnector(cfg), cfg

    if source_id == "I1":
        # CMS Medicare Enrollment: bulk dataset connector, no NPI param.
        cfg = cms_medicare_enrollment_config()
        return CmsMedicareEnrollmentConnector(cfg), cfg

    if source_id == "I2":
        # CMS Medicaid Enrollment: bulk dataset connector, no NPI param.
        cfg = cms_medicaid_enrollment_config()
        return CmsMedicaidEnrollmentConnector(cfg), cfg

    if source_id == "I4":
        # I4 is the NPPES taxonomy crosswalk -- a static lookup, not a live fetch.
        # The normalizer handles it via get_specialty_group(); return empty records.
        cfg = nppes_config(source_id="I4", source_name="NPPES Taxonomy Crosswalk")
        return None, cfg  # sentinel: no connector, no records needed

    if source_id == "A1":
        # PubMed: queries by author name, not NPI. In Phase 2-H, NPI is used as
        # a placeholder; the full pipeline resolves name from NPPES first (Phase 4+).
        author_name = os.environ.get("PUBMED_AUTHOR_NAME", f"NPI:{npi}")
        cfg = pubmed_config()
        return PubmedConnector(cfg, author_name=author_name), cfg

    if source_id == "A2":
        # ClinicalTrials.gov: queries by investigator name.
        investigator_name = os.environ.get("CLINICAL_TRIALS_INVESTIGATOR", f"NPI:{npi}")
        cfg = clinical_trials_config()
        return ClinicalTrialsConnector(cfg, investigator_name=investigator_name), cfg

    raise KeyError(f"Unknown source_id: {source_id!r}")


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------


@activity.defn(name="fetch_source")
async def fetch_source_activity(inp: FetchSourceInput) -> FetchSourceOutput:
    """
    Fetch raw records for one source and one NPI.

    Returns FetchSourceOutput regardless of success/failure -- callers should
    check fetch_status and handle "failed"/"partial" gracefully.

    Legal gate: live network calls return fetch_status="failed" in dev
    (no credentials configured). This is expected.
    """
    npi = inp.npi
    source_id = inp.source_id

    activity.logger.info("fetch_source_activity: source=%s npi=%s", source_id, npi)

    try:
        connector, cfg = _build_connector_and_config(source_id, npi)
    except KeyError as exc:
        return FetchSourceOutput(
            source_id=source_id,
            fetch_status=FetchStatus.FAILED.value,
            error_message=str(exc),
        )

    # I4 is a static crosswalk, not a live fetch.
    if connector is None:
        return FetchSourceOutput(
            source_id=source_id,
            fetch_status=FetchStatus.SUCCESS.value,
            raw_records=[],
            records_count=0,
        )

    try:
        result = await connector.run()
        raw_dicts: list[dict[str, Any]] = [r.model_dump(mode="json") for r in result.records]
        return FetchSourceOutput(
            source_id=source_id,
            raw_records=raw_dicts,
            fetch_status=result.status.value,
            error_message=result.error_message if hasattr(result, "error_message") else None,
            records_count=len(raw_dicts),
        )
    except ConnectorError as exc:
        activity.logger.warning(
            "fetch_source_activity: ConnectorError source=%s npi=%s: %s",
            source_id, npi, exc,
        )
        return FetchSourceOutput(
            source_id=source_id,
            fetch_status=FetchStatus.FAILED.value,
            error_message=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        activity.logger.error(
            "fetch_source_activity: unexpected error source=%s npi=%s: %s",
            source_id, npi, exc,
        )
        return FetchSourceOutput(
            source_id=source_id,
            fetch_status=FetchStatus.FAILED.value,
            error_message=f"Unexpected error: {exc}",
        )

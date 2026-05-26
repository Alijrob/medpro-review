"""
provider_pipeline.py -- ProviderPipelineWorkflow: per-NPI orchestration (C15 basic).

Orchestrates the full provider data pipeline for a single NPI:

    1. Fan-out: fetch raw records from all P1 sources in parallel.
    2. Collect all raw records; bail gracefully if none.
    3. Normalize all raw records into typed NormalizedRecords.
    4. Resolve identity: group records into a UnifiedIdBundle.
    5. Link & merge: build a CanonicalProviderProfile.
    6. Index: write the profile to OpenSearch (best-effort; won't fail the workflow).
    7. Generate report: build ProviderReport + render HTML.

`is_partial` semantics (mirrors CanonicalProviderProfile.is_partial):
    - True  when any source failed or returned no records.
    - False when all sources in source_ids succeeded (full pipeline run).

The workflow is deterministic -- all non-deterministic work lives in activities.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from workers.activities import (
        fetch_source_activity,
        generate_report_activity,
        index_profile_activity,
        link_and_merge_activity,
        normalize_records_activity,
        persist_report_activity,
        resolve_identity_activity,
    )
    from workers.config import P1_SOURCE_IDS, get_settings
    from workers.models import (
        FetchSourceInput,
        GenerateReportInput,
        IndexProfileInput,
        LinkAndMergeInput,
        NormalizeRecordsInput,
        PersistReportInput,
        ProviderPipelineInput,
        ProviderPipelineResult,
        ResolveIdentityInput,
    )

log = logging.getLogger(__name__)

# RetryPolicy for activities: 3 attempts, exponential backoff, 30s initial interval.
_DEFAULT_RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=60),
)

# No retries for best-effort steps (index, report) -- failure should not block the pipeline.
_BEST_EFFORT_RETRY = RetryPolicy(maximum_attempts=1)


@workflow.defn(name="ProviderPipeline")
class ProviderPipelineWorkflow:
    """
    Per-NPI provider data pipeline workflow.

    Input:  ProviderPipelineInput (npi, optional source_ids override, include_html flag)
    Output: ProviderPipelineResult (report dict, HTML, pipeline status)
    """

    @workflow.run
    async def run(self, inp: ProviderPipelineInput) -> ProviderPipelineResult:
        settings = get_settings()
        source_ids = inp.source_ids if inp.source_ids else P1_SOURCE_IDS
        npi = inp.npi

        workflow.logger.info(
            "ProviderPipelineWorkflow: npi=%s sources=%s", npi, source_ids
        )

        # ------------------------------------------------------------------
        # Step 1: Fan-out fetch (all P1 sources in parallel)
        # ------------------------------------------------------------------
        fetch_tasks = [
            workflow.execute_activity(
                fetch_source_activity,
                FetchSourceInput(npi=npi, source_id=src),
                start_to_close_timeout=timedelta(seconds=settings.fetch_activity_timeout_s),
                retry_policy=_DEFAULT_RETRY,
            )
            for src in source_ids
        ]
        fetch_outputs = await asyncio.gather(*fetch_tasks)

        sources_attempted = list(source_ids)
        sources_succeeded = [
            o.source_id for o in fetch_outputs if o.fetch_status == "success"
        ]
        sources_failed = [
            o.source_id for o in fetch_outputs if o.fetch_status == "failed"
        ]

        # Collect all raw records across all sources
        all_raw: list[dict] = []
        for out in fetch_outputs:
            all_raw.extend(out.raw_records)

        if not all_raw:
            workflow.logger.warning(
                "ProviderPipelineWorkflow: npi=%s -- no raw records from any source", npi
            )
            return ProviderPipelineResult(
                npi=npi,
                report=None,
                is_partial=True,
                pipeline_status="no_data",
                sources_attempted=sources_attempted,
                sources_succeeded=sources_succeeded,
                sources_failed=sources_failed,
                error_message="No raw records retrieved from any source adapter.",
            )

        # ------------------------------------------------------------------
        # Step 2: Normalize
        # ------------------------------------------------------------------
        norm_out = await workflow.execute_activity(
            normalize_records_activity,
            NormalizeRecordsInput(raw_records=all_raw, entity_npi=npi),
            start_to_close_timeout=timedelta(seconds=settings.normalize_activity_timeout_s),
            retry_policy=_DEFAULT_RETRY,
        )

        if not norm_out.normalized_records:
            workflow.logger.warning(
                "ProviderPipelineWorkflow: npi=%s -- normalization produced no records", npi
            )
            return ProviderPipelineResult(
                npi=npi,
                report=None,
                is_partial=True,
                pipeline_status="no_data",
                sources_attempted=sources_attempted,
                sources_succeeded=sources_succeeded,
                sources_failed=sources_failed,
                error_message="Normalization produced no usable records.",
            )

        # ------------------------------------------------------------------
        # Step 3: Resolve identity
        # ------------------------------------------------------------------
        resolve_out = await workflow.execute_activity(
            resolve_identity_activity,
            ResolveIdentityInput(npi=npi, normalized_records=norm_out.normalized_records),
            start_to_close_timeout=timedelta(seconds=settings.resolve_activity_timeout_s),
            retry_policy=_DEFAULT_RETRY,
        )

        if resolve_out.bundle is None:
            workflow.logger.warning(
                "ProviderPipelineWorkflow: npi=%s -- identity resolution failed: %s",
                npi, resolve_out.resolution_status,
            )
            return ProviderPipelineResult(
                npi=npi,
                report=None,
                is_partial=True,
                pipeline_status="partial",
                sources_attempted=sources_attempted,
                sources_succeeded=sources_succeeded,
                sources_failed=sources_failed,
                error_message=f"Identity resolution status: {resolve_out.resolution_status}",
            )

        # ------------------------------------------------------------------
        # Step 4: Link & merge
        # ------------------------------------------------------------------
        merge_out = await workflow.execute_activity(
            link_and_merge_activity,
            LinkAndMergeInput(
                bundle=resolve_out.bundle,
                normalized_records=norm_out.normalized_records,
                npi=npi,
            ),
            start_to_close_timeout=timedelta(seconds=settings.link_activity_timeout_s),
            retry_policy=_DEFAULT_RETRY,
        )

        # ------------------------------------------------------------------
        # Step 5: Index (best-effort -- don't fail pipeline if OpenSearch is down)
        # ------------------------------------------------------------------
        await workflow.execute_activity(
            index_profile_activity,
            IndexProfileInput(profile=merge_out.profile, npi=npi),
            start_to_close_timeout=timedelta(seconds=settings.index_activity_timeout_s),
            retry_policy=_BEST_EFFORT_RETRY,
        )

        # ------------------------------------------------------------------
        # Step 6: Generate report
        # ------------------------------------------------------------------
        report_out = await workflow.execute_activity(
            generate_report_activity,
            GenerateReportInput(
                profile=merge_out.profile,
                npi=npi,
                include_html=inp.include_html,
            ),
            start_to_close_timeout=timedelta(seconds=settings.report_activity_timeout_s),
            retry_policy=_DEFAULT_RETRY,
        )

        # is_partial = True if any source failed
        is_partial = bool(sources_failed)
        pipeline_status = "partial" if is_partial else "complete"

        workflow.logger.info(
            "ProviderPipelineWorkflow: npi=%s status=%s report_id=%s",
            npi, pipeline_status, report_out.report_id,
        )

        final_result = ProviderPipelineResult(
            npi=npi,
            report=report_out.report,
            html=report_out.html,
            report_id=report_out.report_id,
            is_partial=is_partial,
            pipeline_status=pipeline_status,
            sources_attempted=sources_attempted,
            sources_succeeded=sources_succeeded,
            sources_failed=sources_failed,
        )

        # ------------------------------------------------------------------
        # Step 7: Persist report (best-effort -- won't fail the pipeline)
        # Only runs when inp.report_id is set (i.e., the request came through
        # the API gateway which created the DB row first).
        # ------------------------------------------------------------------
        if inp.report_id:
            await workflow.execute_activity(
                persist_report_activity,
                PersistReportInput(
                    report_id=inp.report_id,
                    pipeline_result=final_result.model_dump(mode="json"),
                ),
                start_to_close_timeout=timedelta(seconds=settings.persist_activity_timeout_s),
                retry_policy=_BEST_EFFORT_RETRY,
            )

        return final_result

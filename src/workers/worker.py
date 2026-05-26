"""
worker.py -- Temporal worker entrypoint (C15 basic).

Starts a Temporal worker that listens on the medpro-provider-pipeline task queue
and handles all activities + the ProviderPipelineWorkflow.

Usage::

    WORKER_TEMPORAL_ADDRESS=localhost:7233 python -m workers.worker

Environment variables (all prefixed WORKER_):
    WORKER_TEMPORAL_ADDRESS          Temporal server address (default: localhost:7233)
    WORKER_TEMPORAL_NAMESPACE        Temporal namespace (default: default)
    WORKER_TEMPORAL_TASK_QUEUE       Task queue name (default: medpro-provider-pipeline)
    WORKER_TEMPORAL_MAX_CONCURRENT_ACTIVITIES  (default: 50)
    WORKER_TEMPORAL_MAX_CONCURRENT_WORKFLOWS   (default: 20)

LEGAL GATE: live source ingestion is gated by the Phase 0 FCRA determination.
The worker will start successfully but source adapters will return fetch_status=failed
until live credentials + legal gate clearance are in place.
"""
from __future__ import annotations

import asyncio
import logging

import temporalio.client
import temporalio.worker

from .activities import (
    fetch_source_activity,
    generate_report_activity,
    index_profile_activity,
    link_and_merge_activity,
    normalize_records_activity,
    resolve_identity_activity,
)
from .config import get_settings
from .workflows import ProviderPipelineWorkflow

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def run_worker() -> None:
    settings = get_settings()

    log.info(
        "Starting Temporal worker: address=%s namespace=%s task_queue=%s",
        settings.temporal_address,
        settings.temporal_namespace,
        settings.temporal_task_queue,
    )

    client = await temporalio.client.Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )

    worker = temporalio.worker.Worker(
        client,
        task_queue=settings.temporal_task_queue,
        activities=[
            fetch_source_activity,
            normalize_records_activity,
            resolve_identity_activity,
            link_and_merge_activity,
            index_profile_activity,
            generate_report_activity,
        ],
        workflows=[ProviderPipelineWorkflow],
        max_concurrent_activities=settings.temporal_max_concurrent_activities,
        max_concurrent_workflow_tasks=settings.temporal_max_concurrent_workflows,
    )

    log.info("Worker started. Listening for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_worker())

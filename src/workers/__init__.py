"""
workers -- Temporal worker package for the medpro-review per-NPI provider pipeline (C15 basic).

Provides:
    - Temporal activity functions wrapping C10-C17 pure libraries
    - ProviderPipelineWorkflow: per-NPI orchestration workflow
    - WorkerSettings: configuration (env prefix WORKER_)
    - ProviderPipelineInput / ProviderPipelineResult: workflow I/O models

Entrypoint::

    python -m workers.worker     # starts the Temporal worker process

DECISIONS.md Entry 029 (Phase 2-H).
"""
from .config import P1_SOURCE_IDS, WorkerSettings, get_settings
from .models import (
    FetchSourceInput,
    FetchSourceOutput,
    GenerateReportInput,
    GenerateReportOutput,
    IndexProfileInput,
    IndexProfileOutput,
    LinkAndMergeInput,
    LinkAndMergeOutput,
    NormalizeRecordsInput,
    NormalizeRecordsOutput,
    ProviderPipelineInput,
    ProviderPipelineResult,
    ResolveIdentityInput,
    ResolveIdentityOutput,
)
from .workflows import ProviderPipelineWorkflow

__all__ = [
    # config
    "WorkerSettings",
    "get_settings",
    "P1_SOURCE_IDS",
    # workflow
    "ProviderPipelineWorkflow",
    # I/O models
    "ProviderPipelineInput",
    "ProviderPipelineResult",
    "FetchSourceInput",
    "FetchSourceOutput",
    "NormalizeRecordsInput",
    "NormalizeRecordsOutput",
    "ResolveIdentityInput",
    "ResolveIdentityOutput",
    "LinkAndMergeInput",
    "LinkAndMergeOutput",
    "IndexProfileInput",
    "IndexProfileOutput",
    "GenerateReportInput",
    "GenerateReportOutput",
]

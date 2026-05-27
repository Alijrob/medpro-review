"""
config.py -- WorkerSettings for the Temporal worker (C15 basic).

Env prefix: WORKER_
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings

# All P1 source IDs in the order they should be attempted.
# Mirrors the Phase 2-B build order.
P1_SOURCE_IDS: list[str] = ["F1", "F2", "F3", "F4", "I1", "I2", "I4", "A1", "A2"]


class WorkerSettings(BaseSettings):
    """
    Configuration for the Temporal worker process.

    All settings default to dev-friendly values so the worker can start
    without any env vars set (but won't connect to a real Temporal cluster
    or live sources without them).
    """

    # Temporal connection
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "medpro-provider-pipeline"
    temporal_max_concurrent_activities: int = 50
    temporal_max_concurrent_workflows: int = 20

    # Activity timeouts (seconds) -- overridable per-env
    fetch_activity_timeout_s: int = 300      # 5 min per source
    normalize_activity_timeout_s: int = 60   # 1 min
    resolve_activity_timeout_s: int = 30     # 30 s
    link_activity_timeout_s: int = 60        # 1 min
    index_activity_timeout_s: int = 30       # 30 s
    report_activity_timeout_s: int = 30      # 30 s

    # Report activity
    generate_html_in_report_activity: bool = True

    # Persist report activity (Phase 2-I)
    persist_activity_timeout_s: int = 30  # 30 s

    # AI narrative activity (Phase 4-H) -- longer to allow AI API latency
    narrative_activity_timeout_s: int = 120  # 2 min

    model_config = {"env_prefix": "WORKER_", "case_sensitive": False}

    @property
    def is_configured(self) -> bool:
        """True when a non-localhost Temporal address is configured."""
        return self.temporal_address != "localhost:7233"


@lru_cache(maxsize=1)
def get_settings() -> WorkerSettings:
    return WorkerSettings()

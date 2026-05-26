"""
config.py -- Report Service configuration (Phase 2-I).

Env prefix: REPORT_

Key env vars:
    REPORT_DATABASE_URL          Aurora PostgreSQL URL for report persistence
                                 Falls back to DATABASE_URL if not set.
    REPORT_TEMPORAL_ADDRESS      Temporal server address (default: localhost:7233)
    REPORT_TEMPORAL_NAMESPACE    Temporal namespace (default: default)
    REPORT_TEMPORAL_TASK_QUEUE   Task queue name (default: medpro-provider-pipeline)
    REPORT_HTML_MAX_STORAGE_BYTES  Max HTML size to store inline (default: 500000 = 500KB)
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class ReportServiceSettings(BaseSettings):
    """
    Configuration for the Report Service FastAPI application (Phase 2-I).

    All settings have dev-safe defaults so the service can start without
    any env vars set (but won't persist or trigger Temporal until configured).
    """

    # Aurora / PostgreSQL
    database_url: str = ""          # REPORT_DATABASE_URL (falls back to DATABASE_URL)

    # Temporal
    temporal_address: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "medpro-provider-pipeline"

    # HTML storage limit
    html_max_storage_bytes: int = 500_000  # 500 KB

    model_config = {
        "env_prefix": "REPORT_",
        "case_sensitive": False,
        "populate_by_name": True,
    }

    def model_post_init(self, __context: object) -> None:
        """Fall back to DATABASE_URL if REPORT_DATABASE_URL is not set."""
        if not self.database_url:
            fallback = os.environ.get("DATABASE_URL", "")
            # Use object.__setattr__ to bypass Pydantic validation freeze
            object.__setattr__(self, "database_url", fallback)

    @property
    def is_db_configured(self) -> bool:
        """True when a non-empty database URL is available."""
        return bool(self.database_url)

    @property
    def is_temporal_configured(self) -> bool:
        """True when a non-localhost Temporal address is configured."""
        return self.temporal_address not in ("localhost:7233", "")


@lru_cache(maxsize=1)
def get_settings() -> ReportServiceSettings:
    return ReportServiceSettings()

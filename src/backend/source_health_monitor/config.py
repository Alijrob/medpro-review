"""
config.py — Source Health Monitor service settings (env-driven, 12-factor).

The Source Health Monitor (C24) aggregates SourceHealthRecord snapshots from
adapter runs, evaluates alert thresholds, and exposes a fleet health dashboard.
In deployed environments it upserts source_health_records and appends to
source_health_history (migration 0004); locally the shell keeps all state in
memory. Everything defaults to safe/blank so the service imports and runs
without a database -- `is_configured` is False until DATABASE_URL is wired.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MonitorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "dev"
    service_name: str = "source-health-monitor"

    # --- Aurora medpro (main) DB (migration 0004). Blank => in-memory shell. ---
    database_url: str = Field(
        default="",
        description="postgresql+psycopg2://medpro_app:***@host:5432/medpro",
    )

    # --- Alert thresholds ---
    failure_warning_threshold: int = Field(
        default=3,
        ge=1,
        description="Consecutive failures before a WARNING alert fires.",
    )
    failure_critical_threshold: int = Field(
        default=5,
        ge=2,
        description="Consecutive failures before a CRITICAL alert fires.",
    )

    # --- Stale-source detection ---
    # Bulk-download sources (e.g. OIG LEIE) refresh monthly; allow 48h before
    # raising a stale alert. API sources poll more frequently; alert after 4h.
    stale_bulk_hours: float = Field(
        default=48.0,
        ge=1.0,
        description="Hours without a successful run before a bulk-DL source is stale.",
    )
    stale_api_hours: float = Field(
        default=4.0,
        ge=0.5,
        description="Hours without a successful run before an API source is stale.",
    )

    # --- History ring-buffer depth (in-memory shell only) ---
    history_limit: int = Field(
        default=100,
        ge=10,
        description="Max history entries kept per source in the in-memory store.",
    )

    # --- Sentry SaaS (Entry 009). Blank => no-op. ---
    sentry_dsn: str = ""

    # Internal service -- not browser-facing. No CORS origins by default.
    cors_allow_origins: list[str] = []

    @property
    def is_configured(self) -> bool:
        """True once the Aurora DB is wired (post Entry 003)."""
        return bool(self.database_url)


@lru_cache
def get_settings() -> MonitorSettings:
    """Cached settings accessor. Call `get_settings.cache_clear()` in tests."""
    return MonitorSettings()

"""
config.py — Audit ledger service settings (env-driven, 12-factor).

The append-only audit ledger (component C5-audit) that replaces QLDB
(DECISIONS.md Entry 005). In deployed environments it writes to the Aurora
`medpro_audit` database as the INSERT-only `medpro_audit_writer` role (migration
0003); locally the shell keeps the chain in memory. Everything defaults to
safe/blank so the service imports and runs without a database — `is_configured`
is False until AUDIT_DATABASE_URL is wired.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuditSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "dev"
    service_name: str = "audit-service"

    # --- Aurora medpro_audit DB (migration 0002/0003). Blank => in-memory shell. ---
    # Connect as medpro_audit_writer (INSERT-only); UPDATE/DELETE are blocked by the
    # deny_audit_mutation trigger + RLS regardless.
    audit_database_url: str = Field(
        default="",
        description="postgresql+psycopg2://medpro_audit_writer:***@host:5432/medpro_audit",
    )

    # --- Chain checkpointing. Snapshot the head every N events of a target_type. ---
    checkpoint_every_n_events: int = Field(default=1000, ge=1)

    # --- Sentry SaaS (DECISIONS.md Entry 009). Blank => no-op. ---
    sentry_dsn: str = ""

    # Internal service — not browser-facing. No CORS origins by default.
    cors_allow_origins: list[str] = []

    @property
    def is_configured(self) -> bool:
        """True once the Aurora audit DB is wired (post Entry 003)."""
        return bool(self.audit_database_url)


@lru_cache
def get_settings() -> AuditSettings:
    """Cached settings accessor. Call `get_settings.cache_clear()` in tests."""
    return AuditSettings()

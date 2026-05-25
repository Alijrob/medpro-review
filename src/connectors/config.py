"""
config.py — per-source connector configuration (component C9).

A plain Pydantic model (not env-driven settings): each source adapter is
instantiated with a ConnectorConfig describing its identity and operational knobs.
Secrets (API keys) are passed separately at construction in deployed environments
(from External Secrets), never baked into this config.
"""
from __future__ import annotations

from pydantic import Field

from schema.v1.common import MedproBaseModel, SourceCategory

from .models import IntegrationMethod


class ConnectorConfig(MedproBaseModel):
    # --- Identity (from the ToS / Source Priority matrices) ---
    source_id: str = Field(..., max_length=20, description="e.g. 'F1' (NPPES), 'F2' (OIG LEIE).")
    source_name: str = Field(..., max_length=200)
    source_category: SourceCategory
    integration_method: IntegrationMethod
    schema_version: str = Field(default="v1")

    # --- Transport ---
    base_url: str = Field(default="")
    timeout_seconds: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="medpro-review-connector/0.1")

    # --- Retry / backoff ---
    max_retries: int = Field(default=3, ge=0)
    backoff_base_seconds: float = Field(default=0.5, gt=0)
    backoff_max_seconds: float = Field(default=30.0, gt=0)

    # --- Throttling (0 = unlimited) ---
    rate_limit_per_sec: float = Field(default=0.0, ge=0.0)

    # --- Health: bulk-download record-count drop detection ---
    expected_min_records: int | None = Field(
        default=None,
        ge=0,
        description="Alert/PARTIAL if a bulk run returns fewer records than this.",
    )

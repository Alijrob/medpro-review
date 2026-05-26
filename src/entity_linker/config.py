"""
config.py -- EntityLinker configuration (Phase 2-F, C13).

All thresholds and limits are overridable via environment variables
(prefix: LINKER_). The service boots with safe defaults and no env vars.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LinkerSettings(BaseSettings):
    """Configuration for the Entity Linking & Merge engine (C13)."""

    model_config = SettingsConfigDict(
        env_prefix="LINKER_",
        case_sensitive=False,
        env_ignore_empty=True,
    )

    # Maximum recent publications to store in the profile (full list
    # stays in NormalizedRecords).
    max_recent_publications: int = 10

    # Completeness score below which is_partial = True.
    # Default 0.70 means F1 + F2/F3 + I1 + F4 is the minimum complete set.
    completeness_threshold_for_partial: float = 0.70

    # Completeness weight for each expected data section (must sum to 1.0).
    # Configuring individual weights via env is intentionally not supported
    # in the MVP -- modify the class if tuning is needed.
    # Weights are declared here for documentation; the actual dict is
    # defined in signals.py so it can be tested without loading settings.

    @property
    def is_configured(self) -> bool:
        """Always True (no required env vars for the library)."""
        return True

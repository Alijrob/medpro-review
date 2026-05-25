"""
config.py — API gateway settings (env-driven, 12-factor).

Gateway-specific knobs only. Auth/Auth0 settings live in the shared auth overlay
(backend.auth_service.config); the gateway reuses those for token validation.
Everything defaults to safe/shell values so the service boots without external
dependencies (rate-limit + idempotency use in-memory stores; OPA is off).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "dev"
    service_name: str = "api-gateway"

    # --- CORS ---
    cors_allow_origins: list[str] = ["https://researchyourdoctor.com"]

    # --- Rate limiting (fixed window). Redis-backed in deploy; in-memory in shell. ---
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(default=100, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # --- Idempotency (Idempotency-Key replay). Redis-backed in deploy. ---
    idempotency_enabled: bool = True
    idempotency_ttl_seconds: int = Field(default=86400, ge=1)

    # --- OPA authorization hook (C2 baseline). Off until the opa-sidecar exists. ---
    opa_enabled: bool = False
    opa_url: str = Field(default="", description="OPA sidecar base URL, e.g. http://localhost:8181")
    opa_decision_path: str = Field(
        default="v1/data/medpro/authz/allow",
        description="OPA data API path that returns the boolean allow decision.",
    )

    # --- Backing stores (when set, middleware uses Redis instead of in-memory) ---
    redis_url: str = ""

    # --- Sentry SaaS (DECISIONS.md Entry 009). Blank => no-op. ---
    sentry_dsn: str = ""


@lru_cache
def get_settings() -> GatewaySettings:
    """Cached settings accessor. Call `get_settings.cache_clear()` in tests."""
    return GatewaySettings()

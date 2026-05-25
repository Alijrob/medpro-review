"""
config.py — Auth service settings.

All values come from the environment (12-factor). In deployed environments they
are injected by External Secrets Operator from AWS Secrets Manager; locally they
come from a `.env` file. Everything defaults to blank/safe so the shell imports
and runs without an Auth0 tenant — JWT validation then fails closed (401) and
/readyz reports not-ready.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "dev"
    service_name: str = "auth-service"

    # --- Auth0 (DECISIONS.md Entry 002). Blank until the tenant is provisioned. ---
    auth0_domain: str = Field(default="", description="e.g. medpro.us.auth0.com")
    auth0_audience: str = Field(default="", description="Auth0 API identifier (the `aud` claim).")
    auth0_issuer: str = Field(
        default="",
        description="Issuer override. Defaults to https://{auth0_domain}/ when blank.",
    )
    algorithms: list[str] = Field(default=["RS256"], description="Only asymmetric algs accepted.")
    jwks_ttl_seconds: int = Field(default=3600, ge=60)

    # --- Where claims live in the Auth0 token ---
    # Auth0 RBAC puts granted permissions in `permissions` (access token) when the
    # API has RBAC enabled. Roles and email require a namespaced custom claim added
    # via an Auth0 Action (OIDC forbids unnamespaced custom claims).
    permissions_claim: str = "permissions"
    roles_claim: str = "https://researchyourdoctor.com/roles"
    email_claim: str = "https://researchyourdoctor.com/email"

    # --- Path B permissible-use (DECISIONS.md Entry 004) ---
    tos_current_version: str = "tos-v1.0"

    # --- Sentry SaaS (DECISIONS.md Entry 009). Blank => no-op. ---
    sentry_dsn: str = ""

    # --- CORS ---
    cors_allow_origins: list[str] = ["https://researchyourdoctor.com"]

    @property
    def issuer(self) -> str:
        if self.auth0_issuer:
            return self.auth0_issuer
        return f"https://{self.auth0_domain}/" if self.auth0_domain else ""

    @property
    def jwks_url(self) -> str:
        return f"https://{self.auth0_domain}/.well-known/jwks.json" if self.auth0_domain else ""

    @property
    def is_configured(self) -> bool:
        """True once an Auth0 tenant + API audience are set (post Entry 003 wiring)."""
        return bool(self.auth0_domain and self.auth0_audience)


@lru_cache
def get_settings() -> AuthSettings:
    """Cached settings accessor. Call `get_settings.cache_clear()` in tests."""
    return AuthSettings()

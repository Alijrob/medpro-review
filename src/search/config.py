"""
config.py -- Provider Search Service settings (env-driven, 12-factor).

All settings default to safe/blank so the service imports and runs without
a live OpenSearch cluster -- `is_configured` is False until the cluster URL
is wired (post DECISIONS.md Entry 003, AWS account/region).

Environment prefix: SEARCH_
  SEARCH_OPENSEARCH_URL, SEARCH_INDEX_NAME, SEARCH_OPENSEARCH_PASSWORD, etc.

Local dev (docker-compose.dev.yml):
  SEARCH_OPENSEARCH_URL=http://localhost:9200
  SEARCH_OPENSEARCH_PASSWORD=DevOpenSearch1!
  SEARCH_INDEX_NAME=providers-dev
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SEARCH_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "dev"
    service_name: str = "search-service"

    # -- OpenSearch connection --
    opensearch_url: str = Field(
        default="http://localhost:9200",
        description="OpenSearch cluster base URL.",
    )
    opensearch_username: str = Field(
        default="admin",
        description="OpenSearch basic-auth username.",
    )
    opensearch_password: str = Field(
        default="",
        description="OpenSearch basic-auth password. Blank = no auth (local dev).",
    )
    opensearch_timeout_s: float = Field(
        default=5.0,
        ge=0.5,
        description="Per-request timeout in seconds.",
    )

    # -- Index --
    index_name: str = Field(
        default="providers-dev",
        description=(
            "Target index name. Pattern: providers-{env}. "
            "Template (providers_index_template.json) auto-applies on first index."
        ),
    )

    # -- Search defaults --
    default_page_size: int = Field(default=10, ge=1, le=100)
    max_page_size: int = Field(default=100, ge=10)

    # -- Sentry (Entry 009). Blank => no-op. --
    sentry_dsn: str = ""

    cors_allow_origins: list[str] = []

    @property
    def is_configured(self) -> bool:
        """True once a non-default OpenSearch URL is set (post Entry 003)."""
        return bool(self.opensearch_url)

    @property
    def has_auth(self) -> bool:
        """True when both username and password are set."""
        return bool(self.opensearch_username and self.opensearch_password)


@lru_cache
def get_settings() -> SearchSettings:
    """Cached settings accessor. Call `get_settings.cache_clear()` in tests."""
    return SearchSettings()

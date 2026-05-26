"""
config.py -- Payment Service configuration (Phase 2-J).

Env prefix: PAYMENT_

Key env vars:
    PAYMENT_STRIPE_SECRET_KEY       Stripe secret key (sk_live_... or sk_test_...)
    PAYMENT_STRIPE_WEBHOOK_SECRET   Stripe webhook signing secret (whsec_...)
    PAYMENT_STRIPE_PRICE_ID         Stripe Price ID for a single report purchase (price_...)
    PAYMENT_REPORT_PRICE_USD        Fallback unit price in USD when price_id not used (default 35.00)
    PAYMENT_TOS_VERSION             ToS version to record on use_agreements rows (default tos-v1.0)
    PAYMENT_DATABASE_URL            Aurora PostgreSQL URL; falls back to DATABASE_URL
    PAYMENT_SENTRY_DSN              Optional Sentry DSN (best-effort)
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class PaymentServiceSettings(BaseSettings):
    """
    Configuration for the Payment Service FastAPI application (Phase 2-J).

    All settings have dev-safe defaults so the service can start without
    any env vars set (but won't process payments until STRIPE_SECRET_KEY is set).
    """

    # Stripe
    stripe_secret_key: str = ""          # PAYMENT_STRIPE_SECRET_KEY
    stripe_webhook_secret: str = ""      # PAYMENT_STRIPE_WEBHOOK_SECRET
    stripe_price_id: str = ""            # PAYMENT_STRIPE_PRICE_ID (price_...) -- preferred
    report_price_usd: float = 35.00      # PAYMENT_REPORT_PRICE_USD -- used when price_id absent

    # Path B ToS version to record on use_agreements
    tos_version: str = "tos-v1.0"        # PAYMENT_TOS_VERSION

    # Aurora / PostgreSQL
    database_url: str = ""               # PAYMENT_DATABASE_URL (falls back to DATABASE_URL)

    # Observability (best-effort)
    sentry_dsn: str = ""                 # PAYMENT_SENTRY_DSN

    model_config = {
        "env_prefix": "PAYMENT_",
        "case_sensitive": False,
        "populate_by_name": True,
    }

    def model_post_init(self, __context: object) -> None:
        """Fall back to DATABASE_URL if PAYMENT_DATABASE_URL is not set."""
        if not self.database_url:
            fallback = os.environ.get("DATABASE_URL", "")
            object.__setattr__(self, "database_url", fallback)

    @property
    def is_stripe_configured(self) -> bool:
        """True when a non-empty Stripe secret key is present."""
        return bool(self.stripe_secret_key)

    @property
    def is_webhook_configured(self) -> bool:
        """True when both the secret key and webhook secret are present."""
        return bool(self.stripe_secret_key) and bool(self.stripe_webhook_secret)

    @property
    def is_db_configured(self) -> bool:
        """True when a non-empty database URL is available."""
        return bool(self.database_url)


@lru_cache(maxsize=1)
def get_settings() -> PaymentServiceSettings:
    return PaymentServiceSettings()

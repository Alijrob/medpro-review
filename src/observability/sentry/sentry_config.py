"""
Sentry initialization — shared across all medpro-review Python services.

Phase 1-D. Status: NON-DEPLOYED (no DSN is wired until services exist in
Phase 1-F+). This module is imported by each FastAPI service at startup:

    from observability.sentry.sentry_config import init_sentry
    init_sentry(service_name="api-gateway")

Design rules:
  - The DSN is read from the SENTRY_DSN env var, injected by External Secrets
    Operator from AWS Secrets Manager (see ../k8s/external-secrets.yaml). It is
    NEVER hardcoded. If SENTRY_DSN is unset, Sentry stays disabled (safe default
    for local dev and the current non-deployed state).
  - PII scrubbing is mandatory and non-negotiable. This handles regulated
    healthcare-adjacent data; raw provider/user identifiers must never leave the
    cluster. `before_send` and `before_send_transaction` strip known PII keys and
    redact anything that looks like an SSN/email. This is layered with the OTel
    collector's attributes/scrub_pii processor (defense in depth).
  - Sentry shares trace context with OpenTelemetry so an error in Sentry links
    back to the trace in Tempo.
"""
from __future__ import annotations

import os
import re
from typing import Any

# Keys that must be removed from any event payload before it leaves the process.
_PII_KEYS = frozenset(
    {
        "ssn",
        "social_security_number",
        "dob",
        "date_of_birth",
        "email",
        "full_name",
        "first_name",
        "last_name",
        "phone",
        "address",
        "password",
        "authorization",
        "api_key",
        "db.statement",
    }
)

_SSN_RE = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_REDACTED = "[redacted]"


def _scrub(obj: Any) -> Any:
    """Recursively drop PII keys and redact SSN/email patterns in string values."""
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            if key.lower() in _PII_KEYS:
                cleaned[key] = _REDACTED
            else:
                cleaned[key] = _scrub(value)
        return cleaned
    if isinstance(obj, list):
        return [_scrub(item) for item in obj]
    if isinstance(obj, str):
        scrubbed = _SSN_RE.sub(_REDACTED, obj)
        scrubbed = _EMAIL_RE.sub(_REDACTED, scrubbed)
        return scrubbed
    return obj


def _before_send(event: dict, hint: dict) -> dict:
    """Scrub every error event before it is sent to Sentry."""
    return _scrub(event)


def _before_send_transaction(event: dict, hint: dict) -> dict:
    """Scrub performance/transaction events too."""
    return _scrub(event)


def init_sentry(service_name: str) -> bool:
    """
    Initialize Sentry for a service. Returns True if enabled, False if skipped.

    No-ops (returns False) when SENTRY_DSN is unset so local dev and the current
    non-deployed state never emit anything.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False

    # Imported lazily so the dependency is only required where Sentry is enabled.
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    environment = os.environ.get("OTEL_ENVIRONMENT", "dev")

    # Sample rates: full errors, partial traces (traces also flow via OTel/Tempo,
    # so Sentry tracing is kept low to control cost).
    traces_sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=os.environ.get("SERVICE_VERSION", "unknown"),
        server_name=service_name,
        traces_sample_rate=traces_sample_rate,
        # Never let the SDK collect request bodies / cookies / user IP.
        send_default_pii=False,
        max_request_body_size="never",
        before_send=_before_send,
        before_send_transaction=_before_send_transaction,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )
    sentry_sdk.set_tag("service.name", service_name)
    sentry_sdk.set_tag("service.namespace", "medpro")
    return True

# =============================================================================
# audit-service image (Phase 1-I). Status: NON-DEPLOYED (not yet built/pushed).
# Multi-stage: install deps into a venv, then a slim runtime as a non-root user.
# =============================================================================
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# Minimal runtime deps for the audit ledger shell (no Poetry in the image).
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install \
    "fastapi>=0.111,<0.112" \
    "uvicorn[standard]>=0.30,<0.31" \
    "pydantic>=2.7,<3" \
    "pydantic-settings>=2.3,<3" \
    "structlog>=24.1"

# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
# Ship the audit service, the canonical schema it persists, and the Sentry init.
COPY src/backend /app/src/backend
COPY src/schema /app/src/schema
COPY src/observability/sentry /app/src/observability/sentry
COPY src/observability/__init__.py /app/src/observability/__init__.py

# Non-root runtime.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001

EXPOSE 8000
# Metrics port (OTel SDK Prometheus exporter) wired in a later phase.
EXPOSE 9464

CMD ["uvicorn", "backend.audit_service.app:app", "--host", "0.0.0.0", "--port", "8000"]

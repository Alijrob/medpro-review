"""
connectors — Source Connector Framework (component C9, Phase 2-A).

The base classes, error handling, throttling, retry/backoff, and contract-testing
that every source adapter (C10, Phase 2-B+) builds on. This package is the framework
only — it fetches no live source. Real ingestion lives in the adapters and is governed
by the Phase 0 legal gate.

Public API:
    SourceConnector        — abstract base; adapters implement `fetch_raw`
    ConnectorConfig        — per-source configuration
    SchemaContract         — runtime schema-drift guard
    RawRecord, FetchResult, FetchStatus, IntegrationMethod
    ConnectorError + subclasses — the error taxonomy
"""
from .base import SourceConnector
from .config import ConnectorConfig
from .contract import SchemaContract
from .errors import (
    AuthenticationError,
    ConnectorError,
    PermanentError,
    RateLimitedError,
    SchemaDriftError,
    SourceUnavailableError,
    TransientError,
)
from .models import FetchResult, FetchStatus, IntegrationMethod, RawRecord
from .retry import retry_with_backoff
from .throttle import RateLimiter

__all__ = [
    "SourceConnector",
    "ConnectorConfig",
    "SchemaContract",
    "RawRecord",
    "FetchResult",
    "FetchStatus",
    "IntegrationMethod",
    "ConnectorError",
    "TransientError",
    "SourceUnavailableError",
    "RateLimitedError",
    "AuthenticationError",
    "SchemaDriftError",
    "PermanentError",
    "retry_with_backoff",
    "RateLimiter",
]

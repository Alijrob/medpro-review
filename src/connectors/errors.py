"""
errors.py — connector error taxonomy (component C9).

Every failure a source adapter can hit maps to one of these. The base class
carries two facts the framework needs: whether the error is worth retrying, and
which SourceStatus it implies for the health record. Adapters raise these (or the
framework raises them when classifying an HTTP response); `SourceConnector.run`
catches `ConnectorError` and turns it into a FetchResult + SourceHealthRecord.
"""
from __future__ import annotations

from schema.v1.source_health import SourceStatus


class ConnectorError(Exception):
    """Base for all connector failures."""

    retryable: bool = False
    status: SourceStatus = SourceStatus.DOWN

    def to_status(self) -> SourceStatus:
        return self.status


class TransientError(ConnectorError):
    """A temporary failure worth retrying (timeouts, transient 5xx)."""

    retryable = True
    status = SourceStatus.DEGRADED


class SourceUnavailableError(TransientError):
    """The source is unreachable or returning 5xx — retry, then mark DOWN."""

    status = SourceStatus.DOWN


class RateLimitedError(TransientError):
    """The source is throttling us (HTTP 429). Honor Retry-After when present."""

    status = SourceStatus.RATE_LIMITED

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(ConnectorError):
    """Bad/expired API key or credentials (401/403). Not retryable — page an operator."""

    retryable = False
    status = SourceStatus.AUTHENTICATION_FAILED


class SchemaDriftError(ConnectorError):
    """The source's response no longer matches the declared contract. Not retryable."""

    retryable = False
    status = SourceStatus.SCHEMA_DRIFT


class PermanentError(ConnectorError):
    """A non-retryable failure (4xx other than auth/rate-limit, bad config)."""

    retryable = False
    status = SourceStatus.DOWN

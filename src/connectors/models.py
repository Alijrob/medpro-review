"""
models.py — connector framework value types (component C9).

A connector's output is a RawRecord — the source payload plus provenance, BEFORE
normalization. Turning a RawRecord into a typed NormalizedRecord is C11
(Normalization Layer, Phase 2-D), deliberately kept out of the connector.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from schema.v1.common import (
    DataProvenance,
    ImmutableRecord,
    MedproBaseModel,
    utc_now,
)
from schema.v1.source_health import SourceHealthRecord


class IntegrationMethod(str, Enum):
    """How a source is acquired (mirrors the Source Priority Matrix effort tiers)."""

    BULK_DOWNLOAD = "bulk_download"   # CSV/file dump (NPPES, OIG LEIE, CMS files)
    REST_API = "rest_api"             # keyed/unkeyed REST API (SAM.gov, data.cms.gov, Entrez)
    FOIA = "foia"                     # FOIA request pipeline (most state boards)
    WEB_SCRAPE = "web_scrape"         # structured portal scrape (ToS-permitting)


class FetchStatus(str, Enum):
    SUCCESS = "success"     # all expected records fetched, no errors
    PARTIAL = "partial"     # some records fetched, but a fault or a low count occurred
    FAILED = "failed"       # nothing usable fetched


class RawRecord(ImmutableRecord):
    """One raw source record + provenance, pre-normalization."""

    source_id: str = Field(..., max_length=20)
    source_record_id: str | None = Field(default=None, max_length=200)
    fetched_at: datetime = Field(default_factory=utc_now)
    raw: dict[str, Any]
    raw_record_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    schema_version: str = Field(default="v1")

    @classmethod
    def from_raw(
        cls,
        source_id: str,
        raw: dict[str, Any],
        *,
        source_record_id: str | None = None,
        schema_version: str = "v1",
    ) -> "RawRecord":
        """Build a RawRecord, computing the canonical raw hash (DataProvenance.hash_raw)."""
        return cls(
            source_id=source_id,
            source_record_id=source_record_id,
            raw=raw,
            raw_record_hash=DataProvenance.hash_raw(raw),
            schema_version=schema_version,
        )


class FetchResult(MedproBaseModel):
    """The outcome of one connector run — records, metrics, and a health snapshot."""

    source_id: str = Field(..., max_length=20)
    status: FetchStatus
    records: list[RawRecord] = Field(default_factory=list)
    record_count: int = Field(default=0, ge=0)
    error_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = Field(default=0.0, ge=0.0)
    retries: int = Field(default=0, ge=0)
    health: SourceHealthRecord

"""
source_health.py — SourceHealth and DerivedSignal models.

SourceHealth is the output of C24 (Source Health Monitor): tracks availability,
latency, error rate, and schema drift for each data source.

DerivedSignal is the output of C16 (Analytics & Anomaly Detection): computed
risk, confidence, and anomaly signals attached to a CanonicalProviderProfile.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from .common import NPI, ConfidenceScore, MedproBaseModel, SourceCategory, new_uuid, utc_now


# ---------------------------------------------------------------------------
# Source Health
# ---------------------------------------------------------------------------


class SourceStatus(str, Enum):
    """Operational status of a data source."""

    HEALTHY = "healthy"                 # Responding normally, no drift
    DEGRADED = "degraded"               # Slow or elevated error rate but still functional
    DOWN = "down"                       # Not responding or returning errors
    SCHEMA_DRIFT = "schema_drift"       # Response structure changed from expected schema
    RATE_LIMITED = "rate_limited"       # Source is throttling our requests
    AUTHENTICATION_FAILED = "auth_failed"  # Credentials or API key issue
    MAINTENANCE = "maintenance"         # Planned maintenance (set manually)
    UNKNOWN = "unknown"                 # Not yet checked


class SourceHealthRecord(MedproBaseModel):
    """
    Current health state of a single data source.

    One record per source (e.g., one for F1/NPPES, one for F2/OIG, etc.).
    Updated after each scheduled health check and after each adapter run.
    """

    health_id: UUID = Field(default_factory=new_uuid)
    source_id: str = Field(
        ...,
        max_length=20,
        description="Source identifier code from the ToS matrix (e.g., 'F1', 'F2', 'S5').",
    )
    source_name: str = Field(..., max_length=200)
    source_category: SourceCategory
    status: SourceStatus = Field(default=SourceStatus.UNKNOWN)

    # --- Availability metrics ---
    last_checked_at: datetime | None = None
    last_successful_at: datetime | None = None
    last_failed_at: datetime | None = None
    consecutive_failures: int = Field(default=0, ge=0)
    consecutive_successes: int = Field(default=0, ge=0)

    # --- Performance metrics (rolling window) ---
    avg_latency_ms: float | None = Field(default=None, ge=0.0)
    p95_latency_ms: float | None = Field(default=None, ge=0.0)
    error_rate_1h: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Error rate over the last hour (fraction of requests that failed).",
    )
    requests_last_1h: int | None = Field(default=None, ge=0)

    # --- Schema drift detection ---
    expected_schema_version: str | None = Field(
        default=None,
        max_length=20,
        description="The schema version this source is expected to return.",
    )
    detected_schema_version: str | None = Field(
        default=None,
        max_length=20,
        description="The schema version detected on the last successful response.",
    )
    schema_drift_detected: bool = Field(default=False)
    schema_drift_details: str | None = Field(
        default=None,
        max_length=1000,
        description=(
            "Description of the drift if detected (e.g., missing fields, "
            "changed types, new required fields)."
        ),
    )
    schema_drift_first_seen_at: datetime | None = None

    # --- Bulk download tracking ---
    last_bulk_download_at: datetime | None = Field(
        default=None,
        description="Last successful bulk file download for bulk-DL sources.",
    )
    bulk_download_record_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of records in the last bulk download.",
    )
    bulk_download_expected_min: int | None = Field(
        default=None,
        ge=0,
        description="Minimum expected record count. Alert if actual count drops below this.",
    )

    # --- Operational notes ---
    alert_suppressed_until: datetime | None = Field(
        default=None,
        description="Suppress health alerts for this source until this timestamp.",
    )
    notes: str | None = Field(default=None, max_length=500)

    updated_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# Derived Signals
# ---------------------------------------------------------------------------


class DerivedSignalType(str, Enum):
    """
    Types of derived signals computed by C16 (Analytics & Anomaly Detection).
    All signals require a plain-English explanation attribute for report display.
    """

    # --- Risk flags (True/False, high-salience) ---
    EXCLUSION_ACTIVE = "exclusion_active"               # Provider is on OIG LEIE or SAM.gov
    DISCIPLINE_ACTIVE = "discipline_active"             # Active disciplinary action exists
    LICENSE_LAPSED = "license_lapsed"                   # No active license in any state
    LICENSE_SUSPENDED_OR_REVOKED = "license_suspended_revoked"

    # --- Risk scores (0.0-1.0, higher = more concerning) ---
    DISCIPLINARY_HISTORY_RISK = "disciplinary_history_risk"
    COURT_RECORD_RISK = "court_record_risk"
    EXCLUSION_HISTORY_RISK = "exclusion_history_risk"  # Includes historical (not just active)
    OVERALL_RISK_SCORE = "overall_risk_score"           # Composite risk score

    # --- Quality and completeness signals ---
    IDENTITY_CONFIDENCE = "identity_confidence"         # From UnifiedIdBundle
    DATA_COMPLETENESS = "data_completeness"             # Fraction of expected fields populated
    SOURCE_COVERAGE = "source_coverage"                 # Fraction of enabled sources succeeded
    DATA_FRESHNESS = "data_freshness"                   # Age of oldest source data in profile

    # --- Positive signals ---
    BOARD_CERTIFIED = "board_certified"                 # Has at least one board certification
    RESEARCH_ACTIVE = "research_active"                 # Has recent publications
    LONG_LICENSE_TENURE = "long_license_tenure"         # License active > 10 years

    # --- Contextual benchmarks (using NPDB aggregate) ---
    MALPRACTICE_RATE_VS_PEERS = "malpractice_rate_vs_peers"  # How provider compares to specialty peers


class DerivedSignal(MedproBaseModel):
    """
    A single computed signal for a specific provider.

    Output of C16 (Analytics & Anomaly Detection). Stored alongside the
    CanonicalProviderProfile and included in report output.

    Every signal MUST have a human-readable explanation. Explanations are
    reviewed for accuracy and legal safety before deployment (per architecture
    acceptance criteria: "all derived signals are explainable").
    """

    signal_id: UUID = Field(default_factory=new_uuid)
    provider_npi: NPI
    signal_type: DerivedSignalType

    # --- Signal value ---
    value: float = Field(
        ...,
        description=(
            "Numeric signal value. Interpretation depends on signal_type: "
            "flag signals use 1.0=True/0.0=False; "
            "risk scores use 0.0 (low) to 1.0 (high); "
            "completeness/freshness use 0.0 to 1.0."
        ),
    )
    confidence: ConfidenceScore = Field(
        ...,
        description="Confidence in this signal's accuracy (0.0-1.0).",
    )

    # --- Explanation (required) ---
    explanation: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description=(
            "Plain-English explanation of this signal. "
            "Must be factual, non-judgmental, and suitable for direct display in the report. "
            "Example: 'The provider currently has an active license suspension in California, "
            "effective 2024-03-01, based on data from the California Medical Board.'"
        ),
    )

    # --- Provenance ---
    contributing_sources: list[str] = Field(
        default_factory=list,
        description="Source IDs that contributed data for this signal.",
    )
    contributing_record_ids: list[UUID] = Field(
        default_factory=list,
        description="NormalizedRecord IDs used to compute this signal.",
    )

    # --- Model metadata ---
    model_version: str = Field(
        default="rule-v1",
        max_length=50,
        description=(
            "Version of the computation model. 'rule-v1' for rule-based; "
            "'ml-v1' for ML-based (Phase 3+ upgrade of C12)."
        ),
    )

    # --- Timestamps ---
    computed_at: datetime = Field(default_factory=utc_now)
    valid_until: datetime | None = Field(
        default=None,
        description="Signals expire when source data is refreshed; re-computation is triggered.",
    )

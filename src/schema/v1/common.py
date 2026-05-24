"""
common.py — Shared primitive types used across all v1 schema models.

All types here are source-agnostic and reusable. Import from here, not
from individual model modules, to avoid circular dependencies.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Validated scalar aliases
# ---------------------------------------------------------------------------

NPI = Annotated[
    str,
    Field(
        pattern=r"^\d{10}$",
        description="10-digit National Provider Identifier issued by CMS.",
        examples=["1234567890"],
    ),
]

StateCode = Annotated[
    str,
    Field(
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="Two-letter US state or territory code (uppercase).",
        examples=["CA", "TX", "NY"],
    ),
]

ConfidenceScore = Annotated[
    float,
    Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the accuracy of this value. 0.0 = unknown, 1.0 = verified.",
    ),
]

SchemaVersion = Annotated[
    str,
    Field(
        pattern=r"^v\d+$",
        description="Schema version string (e.g., 'v1', 'v2').",
        examples=["v1"],
    ),
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceCategory(str, Enum):
    """Top-level category of a data source. Maps to the 7 categories in the ToS matrix."""

    FEDERAL = "federal"
    STATE_BOARD = "state_board"
    COURT = "court"
    COMMERCIAL_DIRECTORY = "commercial_directory"
    REVIEW_PLATFORM = "review_platform"
    INSURANCE_NETWORK = "insurance_network"
    ACADEMIC = "academic"


class VerificationStatus(str, Enum):
    """Lifecycle status of any data record in the system."""

    PENDING = "pending"          # Ingested, not yet validated
    VERIFIED = "verified"        # Passed quality checks
    DISPUTED = "disputed"        # Flagged via correction workflow
    CORRECTED = "corrected"      # Updated after dispute resolution
    REMOVED = "removed"          # Removed from active profile (source retracted or expunged)
    STALE = "stale"              # Source has not been refreshed within the expected window


class EntityType(str, Enum):
    """NPI entity type as defined by CMS."""

    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class Gender(str, Enum):
    """Provider gender as reported in federal registries."""

    MALE = "M"
    FEMALE = "F"
    OTHER = "O"
    UNKNOWN = "U"


class LicenseStatus(str, Enum):
    """State medical board license status values (normalized across all boards)."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    SURRENDERED = "surrendered"
    PROBATION = "probation"
    UNKNOWN = "unknown"


class ExclusionSource(str, Enum):
    """Source registry for exclusion/debarment records."""

    OIG_LEIE = "oig_leie"
    SAM_GOV = "sam_gov"
    STATE_MEDICAID = "state_medicaid"


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class Address(BaseModel):
    """A US mailing or practice address."""

    model_config = ConfigDict(frozen=True)

    street_line_1: str = Field(..., max_length=200)
    street_line_2: str | None = Field(default=None, max_length=200)
    city: str = Field(..., max_length=100)
    state: StateCode
    postal_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")
    country: str = Field(default="US", max_length=3)
    phone: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="10-digit phone number, digits only.",
    )
    fax: str | None = Field(
        default=None,
        pattern=r"^\d{10}$",
        description="10-digit fax number, digits only.",
    )
    address_type: str | None = Field(
        default=None,
        description="'mailing' or 'practice' as reported by the source.",
    )


class ProviderName(BaseModel):
    """A provider's name as reported by a specific source. One provider may
    have multiple ProviderName records across sources."""

    model_config = ConfigDict(frozen=True)

    first: str = Field(..., max_length=100)
    last: str = Field(..., max_length=100)
    middle: str | None = Field(default=None, max_length=100)
    prefix: str | None = Field(default=None, max_length=20, description="e.g., 'Dr.'")
    suffix: str | None = Field(default=None, max_length=50, description="e.g., 'Jr.', 'III'")
    credentials: str | None = Field(
        default=None,
        max_length=100,
        description="Credential string as reported (e.g., 'MD', 'DO', 'MD, PhD').",
    )

    @property
    def full_name(self) -> str:
        """Best-effort display name."""
        parts = [self.prefix, self.first, self.middle, self.last, self.suffix, self.credentials]
        return " ".join(p for p in parts if p)

    @property
    def sort_key(self) -> str:
        """Normalized sort key for deduplication (last, first, middle)."""
        return f"{self.last.lower()},{self.first.lower()},{(self.middle or '').lower()}"


class TaxonomyCode(BaseModel):
    """NUCC Health Care Provider Taxonomy code record from NPPES."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(..., pattern=r"^[A-Z0-9]{10}$", description="10-character NUCC taxonomy code.")
    description: str = Field(..., max_length=300)
    primary: bool = Field(..., description="True if this is the provider's primary taxonomy.")
    license_number: str | None = Field(default=None, max_length=50)
    license_state: StateCode | None = Field(default=None)


class DataProvenance(BaseModel):
    """Tracks the origin of a data record: which source, when ingested, raw record hash."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(
        ...,
        max_length=20,
        description="Source identifier code (e.g., 'F1' for NPPES, 'S5' for CA Medical Board).",
        examples=["F1", "F2", "S10"],
    )
    source_name: str = Field(..., max_length=100, description="Human-readable source name.")
    source_category: SourceCategory
    source_record_id: str | None = Field(
        default=None,
        max_length=200,
        description="The record's identifier within the source system (e.g., NPI, case number).",
    )
    ingested_at: datetime = Field(
        description="UTC timestamp when this record was ingested into the system."
    )
    source_as_of: date | None = Field(
        default=None,
        description="Date the source data was current as of (bulk download date or API response date).",
    )
    raw_record_hash: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hex digest of the raw source record before normalization.",
    )
    schema_version: SchemaVersion = Field(default="v1")

    @classmethod
    def hash_raw(cls, raw: Any) -> str:
        """Compute SHA-256 hash of a raw record (JSON-serialized, sorted keys)."""
        serialized = json.dumps(raw, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()


# ---------------------------------------------------------------------------
# Base model with common config
# ---------------------------------------------------------------------------


class MedproBaseModel(BaseModel):
    """Base class for all medpro-review schema models. Sets shared config."""

    model_config = ConfigDict(
        frozen=False,       # Operational models are mutable; freeze at the sub-model level
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class ImmutableRecord(MedproBaseModel):
    """Base for all immutable records (source data, normalized records, audit events)."""

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=False,
        populate_by_name=True,
    )


def utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


def new_uuid() -> UUID:
    """Generate a new UUID4."""
    return uuid4()

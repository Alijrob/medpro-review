"""
registry.py — Schema version registry.

Provides versioned JSON Schema exports for all canonical models. Used by:
- C24 (Source Health Monitor): detects schema drift in incoming source data
- C9 (Source Connector Framework): validates NormalizedRecords before write
- C11 (Normalization Layer): confirms normalized output conforms to schema

Usage:
    from schema.registry import registry

    # Get a model's JSON Schema
    schema = registry.get_json_schema("NppesRecord")

    # Validate a dict against a model's schema
    errors = registry.validate("NppesRecord", data)

    # Check for drift (new fields in incoming data not in expected schema)
    drift = registry.detect_drift("NppesRecord", incoming_keys)
"""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel

from .v1 import (
    AuditEvent,
    CanonicalProviderProfile,
    ClinicalTrialRecord,
    CmsProviderRecord,
    CourtCaseRecord,
    DerivedSignal,
    Dispute,
    MedicaidEnrollmentRecord,
    MedicareEnrollmentRecord,
    NormalizedRecord,
    NpdbAggregateRecord,
    NppesRecord,
    OigLeieRecord,
    ProviderIdentity,
    PubMedRecord,
    Report,
    ReviewPlatformRecord,
    SamExclusionRecord,
    SourceHealthRecord,
    StateBoardDisciplinaryRecord,
    StateBoardLicenseRecord,
    UnifiedIdBundle,
    UseAgreement,
    User,
)

CURRENT_VERSION = "v1"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

# All models that are part of the canonical schema — keyed by model name.
# Add new models here when they are introduced.
_REGISTRY_V1: dict[str, Type[BaseModel]] = {
    # Identity
    "ProviderIdentity": ProviderIdentity,
    "UnifiedIdBundle": UnifiedIdBundle,
    # Normalized records
    "NormalizedRecord": NormalizedRecord,
    "NppesRecord": NppesRecord,
    "OigLeieRecord": OigLeieRecord,
    "SamExclusionRecord": SamExclusionRecord,
    "CmsProviderRecord": CmsProviderRecord,
    "MedicareEnrollmentRecord": MedicareEnrollmentRecord,
    "MedicaidEnrollmentRecord": MedicaidEnrollmentRecord,
    "StateBoardLicenseRecord": StateBoardLicenseRecord,
    "StateBoardDisciplinaryRecord": StateBoardDisciplinaryRecord,
    "CourtCaseRecord": CourtCaseRecord,
    "PubMedRecord": PubMedRecord,
    "ClinicalTrialRecord": ClinicalTrialRecord,
    "ReviewPlatformRecord": ReviewPlatformRecord,
    "NpdbAggregateRecord": NpdbAggregateRecord,
    # Profile
    "CanonicalProviderProfile": CanonicalProviderProfile,
    # Users / reports / disputes
    "UseAgreement": UseAgreement,
    "User": User,
    "Report": Report,
    "Dispute": Dispute,
    # Audit
    "AuditEvent": AuditEvent,
    # Source health + signals
    "SourceHealthRecord": SourceHealthRecord,
    "DerivedSignal": DerivedSignal,
}

_VERSION_MAP: dict[str, dict[str, Type[BaseModel]]] = {
    "v1": _REGISTRY_V1,
}


class SchemaRegistry:
    """
    Versioned schema registry. Provides JSON Schema export and validation
    for all canonical models.

    Thread-safe: all operations are read-only on the registry dict.
    """

    def __init__(self) -> None:
        # Cache JSON schemas lazily (model_json_schema() is expensive)
        self._cache: dict[str, dict[str, Any]] = {}

    def _cache_key(self, model_name: str, version: str = CURRENT_VERSION) -> str:
        return f"{version}:{model_name}"

    def get_model(
        self,
        model_name: str,
        version: str = CURRENT_VERSION,
    ) -> Type[BaseModel]:
        """Return the Pydantic model class for a given name and version."""
        version_map = _VERSION_MAP.get(version)
        if version_map is None:
            raise KeyError(f"Unknown schema version: {version!r}")
        model = version_map.get(model_name)
        if model is None:
            raise KeyError(f"Unknown model {model_name!r} in version {version!r}")
        return model

    def get_json_schema(
        self,
        model_name: str,
        version: str = CURRENT_VERSION,
    ) -> dict[str, Any]:
        """Return the JSON Schema dict for a given model name and version."""
        key = self._cache_key(model_name, version)
        if key not in self._cache:
            model = self.get_model(model_name, version)
            self._cache[key] = model.model_json_schema()
        return self._cache[key]

    def validate(
        self,
        model_name: str,
        data: dict[str, Any],
        version: str = CURRENT_VERSION,
    ) -> list[str]:
        """
        Validate a dict against the named model.

        Returns a list of validation error messages. An empty list means the
        data is valid. Does NOT raise on failure — returns errors for the caller
        to handle.
        """
        model = self.get_model(model_name, version)
        try:
            model.model_validate(data)
            return []
        except Exception as exc:
            # Return string representations of all validation errors
            if hasattr(exc, "errors"):
                return [str(e) for e in exc.errors()]  # type: ignore[attr-defined]
            return [str(exc)]

    def detect_drift(
        self,
        model_name: str,
        incoming_keys: set[str],
        version: str = CURRENT_VERSION,
    ) -> dict[str, list[str]]:
        """
        Compare a set of incoming field keys against the model's expected schema.

        Returns a dict with:
          - "unexpected": fields present in incoming_keys but not in the model
          - "missing_required": required fields absent from incoming_keys

        An empty dict means no drift. Used by C24 (Source Health Monitor).
        """
        schema = self.get_json_schema(model_name, version)
        expected_keys = set(schema.get("properties", {}).keys())
        required_keys = set(schema.get("required", []))

        unexpected = list(incoming_keys - expected_keys)
        missing_required = list(required_keys - incoming_keys)

        result: dict[str, list[str]] = {}
        if unexpected:
            result["unexpected"] = sorted(unexpected)
        if missing_required:
            result["missing_required"] = sorted(missing_required)
        return result

    def list_models(self, version: str = CURRENT_VERSION) -> list[str]:
        """Return a sorted list of all model names in a given version."""
        version_map = _VERSION_MAP.get(version)
        if version_map is None:
            raise KeyError(f"Unknown schema version: {version!r}")
        return sorted(version_map.keys())

    def list_versions(self) -> list[str]:
        """Return all registered schema versions."""
        return sorted(_VERSION_MAP.keys())


# Module-level singleton — import and use directly
registry = SchemaRegistry()

"""
contract.py — runtime schema-drift guard (component C9, addresses risk R6).

R6: "Schema drift breaks Source Adapters silently." Each adapter declares a
SchemaContract describing the top-level fields (and optionally their types) the
source is expected to return. The framework validates each raw record against it
during `run`; a violation raises SchemaDriftError, which the run turns into a
SCHEMA_DRIFT health status instead of silently producing malformed records.

This is the *runtime* facet of "contract testing." The reusable *test* harness for
adapters lives in testing.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import SchemaDriftError


@dataclass(frozen=True)
class SchemaContract:
    """The shape a source's raw record must have."""

    required_fields: frozenset[str]
    field_types: dict[str, type] = field(default_factory=dict)

    def validate(self, raw: dict[str, Any]) -> None:
        """Raise SchemaDriftError if `raw` is missing required fields or has wrong types."""
        missing = set(self.required_fields) - set(raw.keys())
        if missing:
            raise SchemaDriftError(f"missing required fields: {sorted(missing)}")
        for name, expected in self.field_types.items():
            value = raw.get(name)
            if value is not None and not isinstance(value, expected):
                raise SchemaDriftError(
                    f"field '{name}' has type {type(value).__name__}, expected {expected.__name__}"
                )

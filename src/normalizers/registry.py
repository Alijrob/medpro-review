"""
registry.py -- Normalizer registry for C11.

All SourceNormalizer subclasses self-register via the @register decorator.
Call get_normalizer(source_id) to retrieve the singleton normalizer for a
given source. Importing src/normalizers/sources/__init__.py triggers all
registrations.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import SourceNormalizer

_REGISTRY: dict[str, "SourceNormalizer"] = {}


def register(cls: type["SourceNormalizer"]) -> type["SourceNormalizer"]:
    """
    Class decorator that registers a SourceNormalizer subclass by its source_id.

    Usage::

        @register
        class NppesNormalizer(SourceNormalizer):
            source_id = "F1"
            ...
    """
    instance = cls()
    _REGISTRY[instance.source_id] = instance
    return cls


def get_normalizer(source_id: str) -> "SourceNormalizer":
    """
    Return the registered normalizer for source_id.

    Raises NormalizationError if no normalizer is registered for the given source.
    Import normalizers.sources to ensure all normalizers are registered before calling
    this function.
    """
    from .base import NormalizationError

    normalizer = _REGISTRY.get(source_id)
    if normalizer is None:
        raise NormalizationError(source_id, f"no normalizer registered for source {source_id!r}")
    return normalizer


def registered_source_ids() -> list[str]:
    """Return a sorted list of all registered source IDs."""
    return sorted(_REGISTRY.keys())

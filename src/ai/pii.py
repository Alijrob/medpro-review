"""
pii.py -- PII scrubber for AI prompt construction.

Strips PII fields from provider profile dicts before they are sent to any
external AI API. Matches the same field list as the Phase 1-D Sentry scrubber
(Entry 007).

Fields scrubbed (top-level and nested):
    home_address, personal_phone, personal_email, dob, ssn
"""
from __future__ import annotations

import copy
from typing import Any

# Canonical PII field names -- kept in sync with sentry_scrubber.py (Phase 1-D)
_PII_FIELDS: frozenset[str] = frozenset({
    "home_address",
    "personal_phone",
    "personal_email",
    "dob",
    "ssn",
})


def scrub_pii(data: Any, *, _depth: int = 0) -> Any:
    """
    Recursively remove PII fields from a dict (or list of dicts).

    Returns a deep copy of the input with PII keys removed.
    The original object is never mutated.

    Args:
        data: The dict, list, or scalar to scrub.

    Returns:
        Scrubbed copy (same type as input).
    """
    if _depth > 20:
        # Guard against pathological nesting
        return copy.deepcopy(data)

    if isinstance(data, dict):
        return {
            k: scrub_pii(v, _depth=_depth + 1)
            for k, v in data.items()
            if k not in _PII_FIELDS
        }
    if isinstance(data, list):
        return [scrub_pii(item, _depth=_depth + 1) for item in data]
    # Scalar (str, int, float, bool, None) -- return as-is
    return data

"""
store.py — in-memory Path B certification store (SHELL ONLY).

Stand-in for the Aurora `use_agreements` table (Phase 1-C migration 0001) until
DATABASE_URL is wired. Records that a given Auth0 `sub` has certified personal-use
only, keyed by sub. Process-local and non-durable by design — do NOT rely on it in
a deployed multi-replica service. The real implementation reads/writes
use_agreements with the `certified_personal_use_only = true` CHECK constraint.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4


@dataclass(frozen=True)
class CertificationRecord:
    agreement_id: UUID
    sub: str
    tos_version: str
    agreed_at: datetime


_certifications: dict[str, CertificationRecord] = {}


def record_certification(sub: str, tos_version: str, agreed_at: datetime) -> CertificationRecord:
    record = CertificationRecord(
        agreement_id=uuid4(), sub=sub, tos_version=tos_version, agreed_at=agreed_at
    )
    _certifications[sub] = record
    return record


def get_certification(sub: str) -> CertificationRecord | None:
    return _certifications.get(sub)


def clear() -> None:
    """Reset the store (used by tests)."""
    _certifications.clear()

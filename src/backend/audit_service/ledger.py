"""
ledger.py — the append-only, hash-chained audit ledger (component C5-audit).

This is the heart of Phase 1-I. It owns the chain that the canonical AuditEvent
model deliberately does NOT (see src/schema/v1/audit.py): assigning each event's
`prev_event_hash` from the chain head, computing `event_hash`, appending
immutably, and verifying integrity by recomputation.

Chains are **per target** — keyed by (target_type, target_id) — matching the
audit_events column semantics. Checkpoints are **per target_type**, mirroring the
audit_chain_checkpoints table.

SHELL: storage is in memory and process-local, a stand-in for the Aurora
`medpro_audit` database (migrations 0002/0003) until AUDIT_DATABASE_URL is wired.
Do NOT rely on it across replicas or restarts. The real implementation INSERTs as
the `medpro_audit_writer` role; UPDATE/DELETE are blocked by the deny_audit_mutation
trigger + RLS regardless, so the chain's immutability is enforced at the DB too.
"""
from __future__ import annotations

from uuid import uuid4

from schema.v1.audit import ActorType, AuditEvent, AuditEventType, TargetType
from schema.v1.common import utc_now

from .models import ChainCheckpoint, ChainVerification, LedgerVerification


class AuditLedger:
    """In-memory append-only ledger with per-target SHA-256 hash chaining."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        # (target_type, target_id) -> event_hash of the most recent event in that chain
        self._chain_heads: dict[tuple[str, str], str] = {}
        self._checkpoints: list[ChainCheckpoint] = []

    # -- write --------------------------------------------------------------
    def append(
        self,
        *,
        event_type: AuditEventType,
        actor_type: ActorType,
        target_type: TargetType,
        target_id: str,
        action: str,
        actor_id: str | None = None,
        session_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        before_hash: str | None = None,
        after_hash: str | None = None,
        metadata: dict | None = None,
    ) -> AuditEvent:
        """Record one event: link it to the chain head, compute its hash, append."""
        key = (target_type.value, target_id)
        prev = self._chain_heads.get(key)

        event = AuditEvent(
            event_type=event_type,
            actor_type=actor_type,
            target_type=target_type,
            target_id=target_id,
            action=action,
            actor_id=actor_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            before_hash=before_hash,
            after_hash=after_hash,
            prev_event_hash=prev,
            event_hash=None,
            metadata=metadata or {},
        )
        # AuditEvent is frozen; set the computed hash on a copy.
        event_hash = AuditEvent.compute_hash(event)
        event = event.model_copy(update={"event_hash": event_hash})

        self._events.append(event)
        self._chain_heads[key] = event_hash
        return event

    # -- read ---------------------------------------------------------------
    def get_chain(self, target_type: str, target_id: str) -> list[AuditEvent]:
        """All events for a target, in insertion order."""
        return [
            e for e in self._events
            if e.target_type.value == target_type and e.target_id == target_id
        ]

    def chain_keys(self) -> list[tuple[str, str]]:
        seen: list[tuple[str, str]] = []
        for e in self._events:
            k = (e.target_type.value, e.target_id)
            if k not in seen:
                seen.append(k)
        return seen

    # -- verify -------------------------------------------------------------
    def verify_chain(self, target_type: str, target_id: str) -> ChainVerification:
        """Walk a target's chain, recomputing each hash and checking the linkage.

        A mismatch means a canonical field was altered; a broken link means an event
        was removed, reordered, or inserted — either way the chain is tampered.
        """
        chain = self.get_chain(target_type, target_id)
        prev_hash: str | None = None
        for event in chain:
            recomputed = AuditEvent.compute_hash(event)
            if recomputed != event.event_hash:
                return ChainVerification(
                    target_type=target_type, target_id=target_id, ok=False,
                    event_count=len(chain), head_hash=self._chain_heads.get((target_type, target_id)),
                    broken_at_event_id=event.event_id,
                    reason="event_hash mismatch — event contents were altered",
                )
            if event.prev_event_hash != prev_hash:
                return ChainVerification(
                    target_type=target_type, target_id=target_id, ok=False,
                    event_count=len(chain), head_hash=self._chain_heads.get((target_type, target_id)),
                    broken_at_event_id=event.event_id,
                    reason="prev_event_hash linkage broken — chain was reordered or an event removed",
                )
            prev_hash = event.event_hash

        return ChainVerification(
            target_type=target_type, target_id=target_id, ok=True,
            event_count=len(chain), head_hash=prev_hash,
        )

    def verify_all(self) -> LedgerVerification:
        failures: list[ChainVerification] = []
        for tt, tid in self.chain_keys():
            result = self.verify_chain(tt, tid)
            if not result.ok:
                failures.append(result)
        keys = self.chain_keys()
        return LedgerVerification(
            ok=not failures,
            chains_checked=len(keys),
            chains_failed=len(failures),
            failures=failures,
        )

    # -- checkpoints --------------------------------------------------------
    def create_checkpoint(self, target_type: str) -> ChainCheckpoint | None:
        """Snapshot the head + count for a target_type (None if no such events yet)."""
        events = [e for e in self._events if e.target_type.value == target_type]
        if not events:
            return None
        head = events[-1]
        checkpoint = ChainCheckpoint(
            checkpoint_id=uuid4(),
            target_type=target_type,
            chain_head_event_id=head.event_id,
            chain_head_event_hash=head.event_hash,
            event_count=len(events),
            checkpointed_at=utc_now(),
        )
        self._checkpoints.append(checkpoint)
        return checkpoint

    def verify_checkpoint(self, checkpoint: ChainCheckpoint) -> ChainCheckpoint:
        """Re-derive the target_type head + count and confirm they match the snapshot."""
        events = [e for e in self._events if e.target_type.value == checkpoint.target_type]
        passed = bool(events) and (
            events[-1].event_id == checkpoint.chain_head_event_id
            and events[-1].event_hash == checkpoint.chain_head_event_hash
            and len(events) == checkpoint.event_count
            and AuditEvent.compute_hash(events[-1]) == checkpoint.chain_head_event_hash
        )
        return checkpoint.model_copy(
            update={"verified_at": utc_now(), "verification_passed": passed}
        )


# Process-local singleton (SHELL). Reset between tests.
_ledger = AuditLedger()


def get_ledger() -> AuditLedger:
    return _ledger


def reset_ledger() -> None:
    global _ledger
    _ledger = AuditLedger()

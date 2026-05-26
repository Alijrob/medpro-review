"""
repository.py -- ReportRepository: Aurora persistence for ProviderReport objects (Phase 2-I).

Sync SQLAlchemy (no asyncio ORM).  The same engine is used from the FastAPI routes
(one engine per process) and from the persist_report Temporal activity (one engine
per worker process).

Table: reports  (see 0001 + 0005 migrations)

Key operations:
    create_row(npi, workflow_id)               -- INSERT status='queued', return UUID
    set_workflow_id(report_id, workflow_id)    -- UPDATE temporal_workflow_id
    mark_started(report_id)                   -- UPDATE status='in_progress', started_at=NOW()
    mark_complete(report_id, ...)             -- UPDATE status + JSON + HTML + sources
    mark_failed(report_id, error_message)     -- UPDATE status='failed'
    get_row(report_id) -> dict | None         -- SELECT full row as dict

IMPORTANT: all operations use text() SQL to avoid importing a full ORM model class
that would pull in the schema package (which depends on psycopg2).  The repository
is safe to import in test environments that have SQLAlchemy but no live DB.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa

log = logging.getLogger(__name__)


class ReportRepository:
    """
    Sync SQLAlchemy wrapper around the `reports` table.

    Construct with a live database URL.  Check `is_configured` before using
    (returns False when created with an empty URL).

    Not thread-safe across multiple engine instances -- use one per process.
    """

    _TOS_VERSION_MVP = "mvp-1.0"
    _EXPIRES_DAYS = 30

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        if database_url:
            self._engine: sa.engine.Engine | None = sa.create_engine(
                database_url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
        else:
            self._engine = None

    @property
    def is_configured(self) -> bool:
        return self._engine is not None

    def create_row(self, npi: str, workflow_id: str | None = None) -> UUID:
        """
        INSERT a new report row with status='queued'.

        Returns the UUID assigned to report_id (generated in Python so the
        caller has it before the workflow starts).

        Skips user_id and use_agreement_id (nullable after migration 0005 --
        wired at Phase 2-J when the payment flow ships).
        """
        if self._engine is None:
            raise RuntimeError("ReportRepository: database not configured.")

        report_id = uuid4()
        requested_at = datetime.now(tz=timezone.utc)
        expires_at = requested_at + timedelta(days=self._EXPIRES_DAYS)

        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO reports
                        (report_id, provider_npi, status, tos_version_at_purchase,
                         temporal_workflow_id, requested_at, expires_at)
                    VALUES
                        (:report_id, :npi, 'queued', :tos_version,
                         :workflow_id, :requested_at, :expires_at)
                    """
                ),
                {
                    "report_id": str(report_id),
                    "npi": npi,
                    "tos_version": self._TOS_VERSION_MVP,
                    "workflow_id": workflow_id,
                    "requested_at": requested_at,
                    "expires_at": expires_at,
                },
            )
        log.debug("ReportRepository.create_row: npi=%s report_id=%s", npi, report_id)
        return report_id

    def set_workflow_id(self, report_id: UUID, workflow_id: str) -> None:
        """UPDATE temporal_workflow_id after the workflow has been dispatched."""
        if self._engine is None:
            raise RuntimeError("ReportRepository: database not configured.")
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    "UPDATE reports SET temporal_workflow_id = :wid WHERE report_id = :rid"
                ),
                {"wid": workflow_id, "rid": str(report_id)},
            )

    def mark_started(self, report_id: UUID) -> None:
        """UPDATE status='in_progress', started_at=NOW()."""
        if self._engine is None:
            raise RuntimeError("ReportRepository: database not configured.")
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    UPDATE reports
                       SET status = 'in_progress',
                           started_at = NOW() AT TIME ZONE 'UTC'
                     WHERE report_id = :rid
                    """
                ),
                {"rid": str(report_id)},
            )

    def mark_complete(
        self,
        report_id: UUID,
        report_json: dict,
        report_html: str,
        sources_attempted: list[str],
        sources_succeeded: list[str],
        sources_failed: list[str],
        is_partial: bool,
        html_max_bytes: int = 500_000,
    ) -> None:
        """
        UPDATE status='complete' (or 'partial' if is_partial), persist JSON + HTML.

        HTML is truncated to NULL if it exceeds html_max_bytes (S3 storage is Phase 5-C).
        """
        if self._engine is None:
            raise RuntimeError("ReportRepository: database not configured.")

        status = "partial" if is_partial else "complete"
        html_to_store: str | None = report_html
        if html_to_store and len(html_to_store.encode("utf-8")) > html_max_bytes:
            log.warning(
                "ReportRepository.mark_complete: HTML exceeds %d bytes for report_id=%s -- not storing",
                html_max_bytes,
                report_id,
            )
            html_to_store = None

        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    UPDATE reports
                       SET status             = :status,
                           completed_at       = NOW() AT TIME ZONE 'UTC',
                           report_json        = :report_json::jsonb,
                           report_html        = :report_html,
                           sources_attempted  = :sources_attempted,
                           sources_succeeded  = :sources_succeeded,
                           sources_failed     = :sources_failed,
                           is_partial         = :is_partial
                     WHERE report_id = :rid
                    """
                ),
                {
                    "status": status,
                    "report_json": json.dumps(report_json),
                    "report_html": html_to_store,
                    "sources_attempted": sources_attempted,
                    "sources_succeeded": sources_succeeded,
                    "sources_failed": sources_failed,
                    "is_partial": is_partial,
                    "rid": str(report_id),
                },
            )

    def mark_failed(self, report_id: UUID, error_message: str) -> None:
        """UPDATE status='failed', completed_at=NOW()."""
        if self._engine is None:
            raise RuntimeError("ReportRepository: database not configured.")
        with self._engine.begin() as conn:
            conn.execute(
                sa.text(
                    """
                    UPDATE reports
                       SET status       = 'failed',
                           completed_at = NOW() AT TIME ZONE 'UTC'
                     WHERE report_id = :rid
                    """
                ),
                {"rid": str(report_id)},
            )
        log.warning(
            "ReportRepository.mark_failed: report_id=%s error=%s", report_id, error_message
        )

    def get_row(self, report_id: UUID) -> dict | None:
        """
        SELECT report row as a plain dict.

        Returns None if not found.
        Converts datetime/UUID fields to strings for safe JSON serialisation.
        """
        if self._engine is None:
            raise RuntimeError("ReportRepository: database not configured.")

        with self._engine.connect() as conn:
            row = conn.execute(
                sa.text(
                    """
                    SELECT report_id, provider_npi, status, is_partial,
                           requested_at, started_at, completed_at, expires_at,
                           temporal_workflow_id,
                           sources_attempted, sources_succeeded, sources_failed,
                           report_json, report_html,
                           payment_status
                      FROM reports
                     WHERE report_id = :rid
                    """
                ),
                {"rid": str(report_id)},
            ).fetchone()

        if row is None:
            return None

        def _fmt(v: object) -> object:
            if isinstance(v, datetime):
                return v.isoformat()
            if isinstance(v, UUID):
                return str(v)
            return v

        return {
            "report_id": str(row.report_id),
            "npi": row.provider_npi,
            "status": row.status,
            "is_partial": row.is_partial,
            "requested_at": _fmt(row.requested_at),
            "started_at": _fmt(row.started_at),
            "completed_at": _fmt(row.completed_at),
            "expires_at": _fmt(row.expires_at),
            "temporal_workflow_id": row.temporal_workflow_id,
            "sources_attempted": list(row.sources_attempted or []),
            "sources_succeeded": list(row.sources_succeeded or []),
            "sources_failed": list(row.sources_failed or []),
            "report": row.report_json,       # already a dict from JSONB
            "has_html": bool(row.report_html),
            "report_html": row.report_html,  # raw HTML string (may be None)
            "payment_status": row.payment_status,
        }

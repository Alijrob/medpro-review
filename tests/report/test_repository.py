"""
test_repository.py -- Tests for ReportRepository (Phase 2-I).

Unit tests (no mark): verify class structure + not-configured guard.
Integration tests (@pytest.mark.integration): require DATABASE_URL or
REPORT_DATABASE_URL and a live PostgreSQL instance with migrations applied
through 0005.
"""
from __future__ import annotations

import pytest

from backend.report_service.repository import ReportRepository


# ---------------------------------------------------------------------------
# Unit tests -- no database required
# ---------------------------------------------------------------------------


class TestReportRepositoryUnit:
    """Class-structure and guard tests -- no live DB needed."""

    def test_not_configured_when_empty_url(self):
        repo = ReportRepository("")
        assert repo.is_configured is False

    def test_engine_is_none_when_empty_url(self):
        repo = ReportRepository("")
        assert repo._engine is None

    def test_create_row_raises_when_not_configured(self):
        repo = ReportRepository("")
        with pytest.raises(RuntimeError, match="not configured"):
            repo.create_row(npi="1234567890")

    def test_mark_started_raises_when_not_configured(self):
        from uuid import uuid4
        repo = ReportRepository("")
        with pytest.raises(RuntimeError, match="not configured"):
            repo.mark_started(uuid4())

    def test_mark_complete_raises_when_not_configured(self):
        from uuid import uuid4
        repo = ReportRepository("")
        with pytest.raises(RuntimeError, match="not configured"):
            repo.mark_complete(
                report_id=uuid4(),
                report_json={},
                report_html="",
                sources_attempted=[],
                sources_succeeded=[],
                sources_failed=[],
                is_partial=False,
            )

    def test_mark_failed_raises_when_not_configured(self):
        from uuid import uuid4
        repo = ReportRepository("")
        with pytest.raises(RuntimeError, match="not configured"):
            repo.mark_failed(uuid4(), "some error")

    def test_get_row_raises_when_not_configured(self):
        from uuid import uuid4
        repo = ReportRepository("")
        with pytest.raises(RuntimeError, match="not configured"):
            repo.get_row(uuid4())

    def test_tos_version_constant_is_string(self):
        assert isinstance(ReportRepository._TOS_VERSION_MVP, str)
        assert len(ReportRepository._TOS_VERSION_MVP) > 0

    def test_expires_days_is_positive(self):
        assert ReportRepository._EXPIRES_DAYS > 0


# ---------------------------------------------------------------------------
# Integration tests -- require DATABASE_URL + live PostgreSQL + migration 0005
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestReportRepositoryIntegration:
    """Live DB tests. Skipped unless DATABASE_URL is set."""

    @pytest.fixture
    def repo(self) -> ReportRepository:
        import os
        db_url = os.environ.get("REPORT_DATABASE_URL") or os.environ.get("DATABASE_URL", "")
        if not db_url:
            pytest.skip("DATABASE_URL not set")
        return ReportRepository(db_url)

    def test_create_row_returns_uuid(self, repo):
        from uuid import UUID
        report_id = repo.create_row(npi="1234567890")
        assert isinstance(report_id, UUID)

    def test_create_row_status_is_queued(self, repo):
        report_id = repo.create_row(npi="1234567891")
        row = repo.get_row(report_id)
        assert row is not None
        assert row["status"] == "queued"

    def test_get_row_returns_correct_npi(self, repo):
        npi = "9876543210"
        report_id = repo.create_row(npi=npi)
        row = repo.get_row(report_id)
        assert row["npi"] == npi

    def test_mark_started_updates_status(self, repo):
        report_id = repo.create_row(npi="1111111111")
        repo.mark_started(report_id)
        row = repo.get_row(report_id)
        assert row["status"] == "in_progress"
        assert row["started_at"] is not None

    def test_mark_complete_updates_status(self, repo):
        report_id = repo.create_row(npi="2222222222")
        repo.mark_complete(
            report_id=report_id,
            report_json={"npi": "2222222222", "is_partial": False},
            report_html="<html></html>",
            sources_attempted=["F1", "F2"],
            sources_succeeded=["F1", "F2"],
            sources_failed=[],
            is_partial=False,
        )
        row = repo.get_row(report_id)
        assert row["status"] == "complete"
        assert row["completed_at"] is not None

    def test_mark_complete_stores_report_json(self, repo):
        report_id = repo.create_row(npi="3333333333")
        report_data = {"npi": "3333333333", "is_partial": False, "test": True}
        repo.mark_complete(
            report_id=report_id,
            report_json=report_data,
            report_html="",
            sources_attempted=["F1"],
            sources_succeeded=["F1"],
            sources_failed=[],
            is_partial=False,
        )
        row = repo.get_row(report_id)
        assert row["report"]["npi"] == "3333333333"

    def test_mark_complete_sets_has_html_true_when_html_provided(self, repo):
        report_id = repo.create_row(npi="4444444444")
        repo.mark_complete(
            report_id=report_id,
            report_json={"npi": "4444444444"},
            report_html="<!DOCTYPE html><html></html>",
            sources_attempted=["F1"],
            sources_succeeded=["F1"],
            sources_failed=[],
            is_partial=False,
        )
        row = repo.get_row(report_id)
        assert row["has_html"] is True

    def test_mark_failed_updates_status(self, repo):
        report_id = repo.create_row(npi="5555555555")
        repo.mark_failed(report_id, "connector error")
        row = repo.get_row(report_id)
        assert row["status"] == "failed"
        assert row["completed_at"] is not None

    def test_partial_pipeline_stores_partial_status(self, repo):
        report_id = repo.create_row(npi="6666666666")
        repo.mark_complete(
            report_id=report_id,
            report_json={"npi": "6666666666", "is_partial": True},
            report_html="",
            sources_attempted=["F1", "F2"],
            sources_succeeded=["F1"],
            sources_failed=["F2"],
            is_partial=True,
        )
        row = repo.get_row(report_id)
        assert row["status"] == "partial"
        assert row["is_partial"] is True

    def test_get_row_returns_none_for_missing_id(self, repo):
        from uuid import uuid4
        row = repo.get_row(uuid4())
        assert row is None

    def test_set_workflow_id(self, repo):
        report_id = repo.create_row(npi="7777777777")
        wf_id = f"report-7777777777-{report_id}"
        repo.set_workflow_id(report_id, wf_id)
        row = repo.get_row(report_id)
        assert row["temporal_workflow_id"] == wf_id

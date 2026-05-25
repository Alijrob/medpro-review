"""
tests/data/test_source_health_history.py

Unit tests for migration 0004 (source_health_history table).

Uses text-file inspection (same pattern as test_migrations.py) -- no database
connection or SQLAlchemy import required.

Coverage:
  - Revision metadata (revision, down_revision, chain)
  - Table structure (columns, types, constraints)
  - Indexes (all 4 expected indexes present)
  - Append-only design documented in docstring
  - Source_health_records relationship documented
  - Seed rows for I1, I2, A1, A2 in upgrade
  - ON CONFLICT DO NOTHING on seeds
  - Downgrade drops table
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path("src/data/migrations/versions")
MIGRATION_FILE = MIGRATIONS_DIR / "0004_source_health_history.py"


@pytest.fixture(scope="module")
def migration_text() -> str:
    return MIGRATION_FILE.read_text()


class TestMigration0004Metadata:
    def test_revision(self, migration_text) -> None:
        # matches both `revision = "0004"` and `revision: str = "0004"`
        match = re.search(r'^revision(?::\s*str)?\s*=\s*"(\w+)"', migration_text, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "0004"

    def test_down_revision(self, migration_text) -> None:
        match = re.search(r'^down_revision(?::\s*\S+)?\s*=\s*"(\w+)"', migration_text, re.MULTILINE)
        assert match is not None
        assert match.group(1) == "0003"

    def test_chain_is_sequential(self, migration_text) -> None:
        """0004 must chain directly from 0003."""
        assert re.search(r'down_revision(?::\s*\S+)?\s*=\s*"0003"', migration_text)
        assert re.search(r'revision(?::\s*str)?\s*=\s*"0004"', migration_text)

    def test_docstring_mentions_append_only(self, migration_text) -> None:
        assert "append-only" in migration_text.lower()

    def test_docstring_mentions_source_health_records(self, migration_text) -> None:
        assert "source_health_records" in migration_text


class TestMigration0004TableStructure:
    def test_table_name(self, migration_text) -> None:
        assert "source_health_history" in migration_text

    def test_primary_key_column(self, migration_text) -> None:
        assert "history_id" in migration_text

    def test_source_id_column_not_null(self, migration_text) -> None:
        # sa.Column("source_id", ... nullable=False)
        assert "source_id" in migration_text
        assert "nullable=False" in migration_text

    def test_status_column(self, migration_text) -> None:
        assert '"status"' in migration_text or "'status'" in migration_text

    def test_fetch_status_column(self, migration_text) -> None:
        assert "fetch_status" in migration_text

    def test_schema_drift_column(self, migration_text) -> None:
        assert "schema_drift_detected" in migration_text

    def test_accumulated_failures_column(self, migration_text) -> None:
        assert "accumulated_failures" in migration_text

    def test_accumulated_successes_column(self, migration_text) -> None:
        assert "accumulated_successes" in migration_text

    def test_recorded_at_column(self, migration_text) -> None:
        assert "recorded_at" in migration_text

    def test_errors_jsonb_column(self, migration_text) -> None:
        assert "JSONB" in migration_text or "jsonb" in migration_text.lower()


class TestMigration0004Indexes:
    def test_source_id_index(self, migration_text) -> None:
        assert "ix_health_history_source_id" in migration_text

    def test_recorded_at_index(self, migration_text) -> None:
        assert "ix_health_history_recorded_at" in migration_text

    def test_status_index(self, migration_text) -> None:
        assert "ix_health_history_status" in migration_text

    def test_composite_index(self, migration_text) -> None:
        assert "ix_health_history_source_recorded" in migration_text


class TestMigration0004Seeds:
    def test_seeds_i1(self, migration_text) -> None:
        assert "'I1'" in migration_text or '"I1"' in migration_text

    def test_seeds_i2(self, migration_text) -> None:
        assert "'I2'" in migration_text or '"I2"' in migration_text

    def test_seeds_a1(self, migration_text) -> None:
        assert "'A1'" in migration_text or '"A1"' in migration_text

    def test_seeds_a2(self, migration_text) -> None:
        assert "'A2'" in migration_text or '"A2"' in migration_text

    def test_conflict_do_nothing(self, migration_text) -> None:
        assert "ON CONFLICT" in migration_text and "DO NOTHING" in migration_text


class TestMigration0004Downgrade:
    def test_downgrade_drops_history_table(self, migration_text) -> None:
        assert "drop_table" in migration_text
        assert "source_health_history" in migration_text

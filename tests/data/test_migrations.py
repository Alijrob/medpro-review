"""
test_migrations.py — Migration structure and integration tests.

Unit tests (no mark): verify migration file structure, revision chain, and
constraint definitions without a live database.

Integration tests (@pytest.mark.integration): require DATABASE_URL and
AUDIT_DATABASE_URL. Verify migrations actually run against PostgreSQL.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path("src/data/migrations/versions")
EXPECTED_REVISIONS = ["0001", "0002", "0003", "0004", "0005", "0006", "0007", "0008"]

# ---------------------------------------------------------------------------
# Unit tests — no database required
# ---------------------------------------------------------------------------


class TestMigrationFiles:
    """Verify migration files exist and are structurally correct."""

    def test_all_revision_files_exist(self):
        files = {f.stem.split("_")[0] for f in MIGRATIONS_DIR.glob("*.py")}
        for rev in EXPECTED_REVISIONS:
            assert rev in files, f"Migration revision {rev} not found in {MIGRATIONS_DIR}"

    def test_revision_chain_is_linear(self):
        """Each migration (except 0001) must reference the previous revision."""
        revisions = {}
        for f in sorted(MIGRATIONS_DIR.glob("*.py")):
            text = f.read_text()
            rev_match = re.search(r'^revision:\s*str\s*=\s*"(\w+)"', text, re.MULTILINE)
            down_match = re.search(r'^down_revision.*?=\s*(?:"(\w+)"|None)', text, re.MULTILINE)
            if rev_match:
                revisions[rev_match.group(1)] = down_match.group(1) if down_match else None

        assert revisions.get("0001") is None, "0001 must have no down_revision"
        assert revisions.get("0002") == "0001", "0002 must reference 0001"
        assert revisions.get("0003") == "0002", "0003 must reference 0002"
        assert revisions.get("0004") == "0003", "0004 must reference 0003"
        assert revisions.get("0005") == "0004", "0005 must reference 0004"
        assert revisions.get("0006") == "0005", "0006 must reference 0005"
        assert revisions.get("0007") == "0006", "0007 must reference 0006"
        assert revisions.get("0008") == "0007", "0008 must reference 0007"

    def test_0001_creates_all_main_tables(self):
        text = (MIGRATIONS_DIR / "0001_baseline_schema.py").read_text()
        expected_tables = [
            "unified_id_bundles",
            "normalized_records",
            "canonical_provider_profiles",
            "users",
            "use_agreements",
            "reports",
            "disputes",
            "source_health_records",
            "derived_signals",
        ]
        for table in expected_tables:
            assert f'"{table}"' in text or f"'{table}'" in text, (
                f"Table {table!r} not found in 0001 migration"
            )

    def test_0001_path_b_constraint_present(self):
        """UseAgreement.certified_personal_use_only CHECK constraint must be in 0001."""
        text = (MIGRATIONS_DIR / "0001_baseline_schema.py").read_text()
        assert "certified_personal_use_only = true" in text, (
            "Path B check constraint (certified_personal_use_only = true) missing from 0001"
        )

    def test_0001_explanation_constraint_present(self):
        """DerivedSignal.explanation CHECK constraint must enforce non-empty."""
        text = (MIGRATIONS_DIR / "0001_baseline_schema.py").read_text()
        assert "ck_explanation_nonempty" in text, (
            "explanation length check constraint missing from derived_signals"
        )

    def test_0002_creates_audit_tables(self):
        text = (MIGRATIONS_DIR / "0002_audit_schema.py").read_text()
        assert '"audit_events"' in text or "'audit_events'" in text
        assert '"audit_chain_checkpoints"' in text or "'audit_chain_checkpoints'" in text

    def test_0002_append_only_triggers_present(self):
        """Deny UPDATE and DELETE triggers must be in 0002."""
        text = (MIGRATIONS_DIR / "0002_audit_schema.py").read_text()
        assert "trg_audit_events_no_update" in text, "No-update trigger missing from 0002"
        assert "trg_audit_events_no_delete" in text, "No-delete trigger missing from 0002"
        assert "deny_audit_mutation" in text, "deny_audit_mutation function missing from 0002"

    def test_0002_hash_format_constraints_present(self):
        """SHA-256 format constraints must be present on audit_events."""
        text = (MIGRATIONS_DIR / "0002_audit_schema.py").read_text()
        assert "ck_event_hash_format" in text
        assert "[a-f0-9]{64}" in text, "SHA-256 regex check missing from 0002"

    def test_0003_creates_three_roles(self):
        text = (MIGRATIONS_DIR / "0003_db_roles_and_rls.py").read_text()
        assert "medpro_app" in text
        assert "medpro_audit_writer" in text
        assert "medpro_readonly" in text

    def test_0003_rls_enabled_on_audit_events(self):
        text = (MIGRATIONS_DIR / "0003_db_roles_and_rls.py").read_text()
        assert "ENABLE ROW LEVEL SECURITY" in text
        assert "FORCE ROW LEVEL SECURITY" in text

    def test_0003_no_update_delete_granted_to_audit_writer(self):
        """audit_writer must never receive UPDATE or DELETE grants."""
        text = (MIGRATIONS_DIR / "0003_db_roles_and_rls.py").read_text()
        # Find all GRANT lines that reference medpro_audit_writer
        grant_lines = [
            line for line in text.splitlines()
            if "medpro_audit_writer" in line and "GRANT" in line.upper()
        ]
        for line in grant_lines:
            assert "UPDATE" not in line.upper(), (
                f"medpro_audit_writer should not receive UPDATE grant: {line}"
            )
            assert "DELETE" not in line.upper(), (
                f"medpro_audit_writer should not receive DELETE grant: {line}"
            )

    def test_0003_seeds_p1_source_health_records(self):
        """Migration 0003 must seed all 9 P1 federal/academic sources."""
        text = (MIGRATIONS_DIR / "0003_db_roles_and_rls.py").read_text()
        p1_sources = ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"]
        for source in p1_sources:
            assert f"'{source}'" in text, f"P1 source {source} not seeded in 0003"

    def test_each_migration_has_downgrade(self):
        """Every migration must have a downgrade() implementation."""
        for f in MIGRATIONS_DIR.glob("*.py"):
            text = f.read_text()
            assert "def downgrade()" in text, f"{f.name} is missing downgrade()"
            # downgrade() should do more than just 'pass'
            downgrade_body = text.split("def downgrade()")[1]
            assert "pass" not in downgrade_body[:50], (
                f"{f.name} downgrade() appears to be a no-op stub"
            )

    def test_0005_file_exists(self):
        assert (MIGRATIONS_DIR / "0005_report_json_storage.py").exists(), (
            "Migration 0005 file not found"
        )

    def test_0005_adds_report_json_column(self):
        text = (MIGRATIONS_DIR / "0005_report_json_storage.py").read_text()
        assert "report_json" in text, "0005 must add report_json column to reports"

    def test_0005_adds_report_html_column(self):
        text = (MIGRATIONS_DIR / "0005_report_json_storage.py").read_text()
        assert "report_html" in text, "0005 must add report_html column to reports"

    def test_0005_alters_user_id_nullable(self):
        """user_id must be made nullable so pre-payment reports can be created."""
        text = (MIGRATIONS_DIR / "0005_report_json_storage.py").read_text()
        assert "user_id" in text, "0005 must alter user_id nullable"
        assert "nullable" in text, "0005 alter_column call must set nullable"

    def test_0005_alters_use_agreement_id_nullable(self):
        """use_agreement_id must be made nullable for MVP (pre-payment phase)."""
        text = (MIGRATIONS_DIR / "0005_report_json_storage.py").read_text()
        assert "use_agreement_id" in text, "0005 must alter use_agreement_id nullable"

    def test_0005_targets_reports_table(self):
        text = (MIGRATIONS_DIR / "0005_report_json_storage.py").read_text()
        assert '"reports"' in text or "'reports'" in text, (
            "0005 must operate on the reports table"
        )

    def test_0005_has_downgrade(self):
        text = (MIGRATIONS_DIR / "0005_report_json_storage.py").read_text()
        assert "def downgrade()" in text
        # Should drop the added columns in downgrade
        assert "drop_column" in text, "0005 downgrade must drop the added columns"

    # 0006 -- Payment Columns
    def test_0006_file_exists(self):
        assert (MIGRATIONS_DIR / "0006_payment_columns.py").exists(), (
            "Migration 0006 file not found"
        )

    def test_0006_adds_stripe_checkout_session_id(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert "stripe_checkout_session_id" in text, (
            "0006 must add stripe_checkout_session_id column to reports"
        )

    def test_0006_adds_payment_status_column(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert "payment_status" in text, (
            "0006 must add payment_status column to reports"
        )

    def test_0006_payment_status_has_default_unpaid(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert "unpaid" in text, (
            "0006 payment_status default must be 'unpaid'"
        )

    def test_0006_payment_status_check_constraint_present(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert "ck_reports_payment_status" in text, (
            "0006 must include CHECK constraint on payment_status"
        )

    def test_0006_allowed_payment_status_values_in_constraint(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        for value in ("unpaid", "pending", "paid", "refunded"):
            assert value in text, f"0006 CHECK constraint must include '{value}'"

    def test_0006_stripe_session_index_present(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert "ix_reports_stripe_session_id" in text, (
            "0006 must create an index on stripe_checkout_session_id"
        )

    def test_0006_has_downgrade(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert "def downgrade()" in text
        assert "drop_column" in text, "0006 downgrade must drop the added columns"

    def test_0006_targets_reports_table(self):
        text = (MIGRATIONS_DIR / "0006_payment_columns.py").read_text()
        assert '"reports"' in text or "'reports'" in text, (
            "0006 must operate on the reports table"
        )


class TestMigration0007:
    """Migration 0007 -- State Board seed rows in source_health_records."""

    def test_0007_file_exists(self):
        assert (MIGRATIONS_DIR / "0007_state_board_seeds.py").exists(), (
            "Migration 0007 file not found"
        )

    def test_0007_references_0006(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        assert 'down_revision' in text and '"0006"' in text, (
            "0007 must reference 0006 as down_revision"
        )

    def test_0007_seeds_all_five_state_boards(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        for source_id in ("state_board_ca", "state_board_ny", "state_board_tx",
                          "state_board_fl", "state_board_il"):
            assert source_id in text, f"0007 must seed '{source_id}'"

    def test_0007_uses_on_conflict_do_nothing(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        assert "ON CONFLICT" in text.upper() and "DO NOTHING" in text.upper(), (
            "0007 seed INSERT must be idempotent (ON CONFLICT DO NOTHING)"
        )

    def test_0007_targets_source_health_records(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        assert "source_health_records" in text, (
            "0007 must INSERT into source_health_records"
        )

    def test_0007_has_downgrade(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        assert "def downgrade()" in text
        assert "DELETE" in text.upper(), "0007 downgrade must DELETE the seeded rows"

    def test_0007_downgrade_targets_state_board_ids(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        assert "state_board_ca" in text, "0007 downgrade must reference state_board_ca"

    def test_0007_sets_state_board_category(self):
        text = (MIGRATIONS_DIR / "0007_state_board_seeds.py").read_text()
        assert "state_board" in text, (
            "0007 seeded rows must use 'state_board' as source_category"
        )


class TestMigration0008:
    """Migration 0008 -- Phase 3-B state board seed rows (GA/PA/OH/MI/NC)."""

    def test_0008_file_exists(self):
        assert (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").exists(), (
            "Migration 0008 file not found"
        )

    def test_0008_references_0007(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        assert 'down_revision' in text and '"0007"' in text, (
            "0008 must reference 0007 as down_revision"
        )

    def test_0008_seeds_all_five_phase3b_state_boards(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        for source_id in ("state_board_ga", "state_board_pa", "state_board_oh",
                          "state_board_mi", "state_board_nc"):
            assert source_id in text, f"0008 must seed '{source_id}'"

    def test_0008_does_not_seed_phase3a_boards(self):
        """Phase 3-A boards (CA/NY/TX/FL/IL) must not be re-seeded in 0008."""
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        for source_id in ("state_board_ca", "state_board_ny", "state_board_tx",
                          "state_board_fl", "state_board_il"):
            assert source_id not in text, (
                f"0008 must not duplicate {source_id} (already seeded in 0007)"
            )

    def test_0008_uses_on_conflict_do_nothing(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        assert "ON CONFLICT" in text.upper() and "DO NOTHING" in text.upper(), (
            "0008 seed INSERT must be idempotent (ON CONFLICT DO NOTHING)"
        )

    def test_0008_targets_source_health_records(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        assert "source_health_records" in text, (
            "0008 must INSERT into source_health_records"
        )

    def test_0008_sets_state_board_category(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        assert "state_board" in text, (
            "0008 seeded rows must use 'state_board' as source_category"
        )

    def test_0008_has_downgrade(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        assert "def downgrade()" in text
        assert "DELETE" in text.upper(), "0008 downgrade must DELETE the seeded rows"

    def test_0008_downgrade_targets_phase3b_ids_only(self):
        text = (MIGRATIONS_DIR / "0008_state_board_seeds_batch2.py").read_text()
        downgrade_section = text.split("def downgrade()")[1]
        for source_id in ("state_board_ga", "state_board_pa", "state_board_oh",
                          "state_board_mi", "state_board_nc"):
            assert source_id in downgrade_section, (
                f"0008 downgrade must reference '{source_id}'"
            )


class TestOpenSearchTemplate:
    """Verify OpenSearch index template structure."""

    def test_template_is_valid_json(self):
        path = Path("src/data/opensearch/providers_index_template.json")
        assert path.exists(), "providers_index_template.json not found"
        data = json.loads(path.read_text())
        assert "template" in data
        assert "mappings" in data["template"]
        assert "settings" in data["template"]

    def test_template_has_npi_field(self):
        data = json.loads(
            Path("src/data/opensearch/providers_index_template.json").read_text()
        )
        props = data["template"]["mappings"]["properties"]
        assert "primary_npi" in props, "primary_npi field missing from OpenSearch template"
        assert props["primary_npi"]["type"] == "keyword"

    def test_template_has_name_fields(self):
        data = json.loads(
            Path("src/data/opensearch/providers_index_template.json").read_text()
        )
        props = data["template"]["mappings"]["properties"]
        assert "primary_name" in props
        name_props = props["primary_name"]["properties"]
        assert "first" in name_props
        assert "last" in name_props

    def test_template_has_risk_fields(self):
        data = json.loads(
            Path("src/data/opensearch/providers_index_template.json").read_text()
        )
        props = data["template"]["mappings"]["properties"]
        assert "has_active_exclusion" in props
        assert "has_active_discipline" in props
        assert "overall_risk_score" in props

    def test_template_index_pattern_matches_env_convention(self):
        data = json.loads(
            Path("src/data/opensearch/providers_index_template.json").read_text()
        )
        patterns = data.get("index_patterns", [])
        assert any("providers-*" in p for p in patterns), (
            "Index pattern must match providers-{env} convention"
        )


class TestRedisKeyspaceDoc:
    """Verify Redis keyspace strategy document covers required domains."""

    def test_doc_exists(self):
        assert Path("src/data/redis/keyspace-strategy.md").exists()

    def test_doc_covers_required_domains(self):
        text = Path("src/data/redis/keyspace-strategy.md").read_text()
        required = [
            "rate",       # rate limiting
            "report",     # report status
            "session",    # auth session cache
            "profile",    # provider profile cache
            "search",     # search results cache
            "TTL",        # TTL policy required on all keys
        ]
        for keyword in required:
            assert keyword in text, f"Redis keyspace doc missing coverage of: {keyword}"


# ---------------------------------------------------------------------------
# Integration tests — require live PostgreSQL
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMigrationsRun:
    """Verify migrations actually create expected tables in PostgreSQL."""

    def test_main_tables_exist(self, migrated_db):
        engine, _ = migrated_db
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "unified_id_bundles",
            "normalized_records",
            "canonical_provider_profiles",
            "users",
            "use_agreements",
            "reports",
            "disputes",
            "source_health_records",
            "derived_signals",
        }
        missing = expected - tables
        assert not missing, f"Missing tables after migration: {missing}"

    def test_audit_tables_exist(self, migrated_db):
        _, audit_engine = migrated_db
        from sqlalchemy import inspect

        inspector = inspect(audit_engine)
        tables = set(inspector.get_table_names())
        assert "audit_events" in tables
        assert "audit_chain_checkpoints" in tables

    def test_path_b_constraint_enforced(self, migrated_db):
        """Inserting use_agreement with certified_personal_use_only=false must fail."""
        engine, _ = migrated_db
        from sqlalchemy import text

        with engine.connect() as conn:
            # Insert a user first
            conn.execute(text("""
                INSERT INTO users (user_id, email, role)
                VALUES ('00000000-0000-0000-0000-000000000001', 'test@example.com', 'consumer')
                ON CONFLICT DO NOTHING
            """))
            conn.commit()

            with pytest.raises(Exception, match="ck_certified_personal_use_only|CHECK"):
                conn.execute(text("""
                    INSERT INTO use_agreements
                        (user_id, tos_version, certified_personal_use_only)
                    VALUES (
                        '00000000-0000-0000-0000-000000000001',
                        'tos-v1.0',
                        false
                    )
                """))
                conn.commit()

    def test_audit_events_insert_succeeds(self, migrated_db):
        """audit_events should accept valid INSERTs."""
        _, audit_engine = migrated_db
        from sqlalchemy import text

        with audit_engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO audit_events (
                    event_type, actor_type, target_type, target_id, action, event_hash
                ) VALUES (
                    'user.created', 'system', 'user',
                    '00000000-0000-0000-0000-000000000002',
                    'Test user created during migration test',
                    'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890'
                )
            """))
            conn.commit()

    def test_audit_events_update_blocked(self, migrated_db):
        """audit_events UPDATE must be blocked by trigger."""
        _, audit_engine = migrated_db
        from sqlalchemy import text

        with audit_engine.connect() as conn:
            with pytest.raises(Exception, match="append-only|forbidden"):
                conn.execute(text("""
                    UPDATE audit_events
                    SET action = 'tampered'
                    WHERE event_type = 'user.created'
                """))
                conn.commit()

    def test_p1_source_health_records_seeded(self, migrated_db):
        engine, _ = migrated_db
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT source_id FROM source_health_records ORDER BY source_id")
            )
            source_ids = {row[0] for row in result}

        expected = {"F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9"}
        assert expected.issubset(source_ids), (
            f"Missing seeded P1 sources: {expected - source_ids}"
        )

    def test_normalized_records_deduplication_index(self, migrated_db):
        """raw_record_hash unique index must prevent duplicate ingestion."""
        engine, _ = migrated_db
        from sqlalchemy import text

        test_hash = "a" * 64
        test_npi = "1234567890"

        with engine.connect() as conn:
            # Ensure bundle exists
            conn.execute(text("""
                INSERT INTO unified_id_bundles
                    (primary_npi, entity_type, primary_name, identity_confidence)
                VALUES (:npi, 'individual', '{"first":"Test","last":"Provider"}'::jsonb, 0.99)
                ON CONFLICT (primary_npi) DO NOTHING
            """), {"npi": test_npi})
            conn.commit()

            conn.execute(text("""
                INSERT INTO normalized_records
                    (primary_npi, source_id, source_name, source_category,
                     record_type, raw_record_hash, data, provenance)
                VALUES (:npi, 'F1', 'NPPES', 'federal', 'identity',
                        :hash, '{}'::jsonb, '{}'::jsonb)
            """), {"npi": test_npi, "hash": test_hash})
            conn.commit()

            with pytest.raises(Exception, match="unique|duplicate"):
                conn.execute(text("""
                    INSERT INTO normalized_records
                        (primary_npi, source_id, source_name, source_category,
                         record_type, raw_record_hash, data, provenance)
                    VALUES (:npi, 'F1', 'NPPES', 'federal', 'identity',
                            :hash, '{}'::jsonb, '{}'::jsonb)
                """), {"npi": test_npi, "hash": test_hash})
                conn.commit()

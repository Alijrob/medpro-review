"""DB roles, privileges, and row-level security

Creates the application database roles and enforces least-privilege access.
Must be run as the superuser (medpro_admin) — not as the app roles themselves.

Roles created:
  medpro_app          — application read/write on main tables; no access to audit_events
  medpro_audit_writer — INSERT only on audit_events; no UPDATE/DELETE ever
  medpro_readonly     — SELECT only (analytics, admin dashboard read queries)

Row-level security on audit_events:
  - Blocks UPDATE and DELETE for all roles including medpro_audit_writer
  - medpro_audit_writer: INSERT allowed
  - medpro_app: SELECT allowed (for audit lookups)
  - medpro_readonly: SELECT allowed

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Main tables (in medpro DB) — medpro_app gets full read/write
MAIN_TABLES = [
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

# Audit tables (in medpro_audit DB) — only medpro_audit_writer can INSERT
AUDIT_TABLES = [
    "audit_events",
    "audit_chain_checkpoints",
]


def upgrade() -> None:
    # -----------------------------------------------------------------
    # Create roles (idempotent — IF NOT EXISTS)
    # -----------------------------------------------------------------
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'medpro_app') THEN
            CREATE ROLE medpro_app LOGIN PASSWORD NULL;
          END IF;
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'medpro_audit_writer') THEN
            CREATE ROLE medpro_audit_writer LOGIN PASSWORD NULL;
          END IF;
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'medpro_readonly') THEN
            CREATE ROLE medpro_readonly LOGIN PASSWORD NULL;
          END IF;
        END $$
    """)
    # Note: passwords are managed via AWS Secrets Manager in deployed envs.
    # Local dev: set passwords manually after running migrations.

    # -----------------------------------------------------------------
    # medpro_app — application role (main database)
    # Reads and writes all main tables. Zero access to audit_events.
    # -----------------------------------------------------------------
    op.execute("GRANT CONNECT ON DATABASE medpro TO medpro_app")
    op.execute("GRANT USAGE ON SCHEMA public TO medpro_app")
    for table in MAIN_TABLES:
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO medpro_app"
        )
    # Future tables: grant automatically
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO medpro_app"
    )

    # -----------------------------------------------------------------
    # medpro_readonly — read-only role (analytics, admin dashboard reads)
    # -----------------------------------------------------------------
    op.execute("GRANT CONNECT ON DATABASE medpro TO medpro_readonly")
    op.execute("GRANT USAGE ON SCHEMA public TO medpro_readonly")
    for table in MAIN_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO medpro_readonly")
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT ON TABLES TO medpro_readonly"
    )

    # -----------------------------------------------------------------
    # medpro_audit_writer — audit INSERT only (medpro_audit DB)
    # Written synchronously by AuditLedgerService before every commit.
    # -----------------------------------------------------------------
    op.execute("GRANT CONNECT ON DATABASE medpro_audit TO medpro_audit_writer")
    op.execute("GRANT USAGE ON SCHEMA public TO medpro_audit_writer")
    for table in AUDIT_TABLES:
        op.execute(f"GRANT INSERT ON {table} TO medpro_audit_writer")
    # Explicitly NO UPDATE, NO DELETE — these are never granted

    # medpro_app can SELECT from audit tables (for audit lookups in admin UI)
    op.execute("GRANT CONNECT ON DATABASE medpro_audit TO medpro_app")
    op.execute("GRANT USAGE ON SCHEMA public TO medpro_app")
    for table in AUDIT_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO medpro_app")

    op.execute("GRANT CONNECT ON DATABASE medpro_audit TO medpro_readonly")
    for table in AUDIT_TABLES:
        op.execute(f"GRANT SELECT ON {table} TO medpro_readonly")

    # -----------------------------------------------------------------
    # Row-Level Security on audit_events
    # Ensures that even if a role has broad privileges, it cannot
    # UPDATE or DELETE audit rows.
    # -----------------------------------------------------------------
    op.execute("ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_events FORCE ROW LEVEL SECURITY")

    # INSERT policy: medpro_audit_writer only
    op.execute("""
        CREATE POLICY audit_insert_policy ON audit_events
        FOR INSERT
        TO medpro_audit_writer
        WITH CHECK (true)
    """)

    # SELECT policy: medpro_app and medpro_readonly
    op.execute("""
        CREATE POLICY audit_select_policy ON audit_events
        FOR SELECT
        TO medpro_app, medpro_readonly
        USING (true)
    """)

    # No UPDATE policy — UPDATE is silently blocked for all roles
    # No DELETE policy — DELETE is silently blocked for all roles
    # (Combined with the deny_audit_mutation trigger from 0002 for defense-in-depth)

    # Same RLS for audit_chain_checkpoints
    op.execute("ALTER TABLE audit_chain_checkpoints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_chain_checkpoints FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY checkpoint_insert_policy ON audit_chain_checkpoints
        FOR INSERT
        TO medpro_audit_writer
        WITH CHECK (true)
    """)
    op.execute("""
        CREATE POLICY checkpoint_select_policy ON audit_chain_checkpoints
        FOR SELECT
        TO medpro_app, medpro_readonly
        USING (true)
    """)

    # -----------------------------------------------------------------
    # Revoke superuser defaults from app roles
    # Belt-and-suspenders: ensure app roles can't bypass RLS
    # -----------------------------------------------------------------
    op.execute("ALTER ROLE medpro_app NOSUPERUSER NOCREATEDB NOCREATEROLE")
    op.execute("ALTER ROLE medpro_audit_writer NOSUPERUSER NOCREATEDB NOCREATEROLE")
    op.execute("ALTER ROLE medpro_readonly NOSUPERUSER NOCREATEDB NOCREATEROLE")

    # -----------------------------------------------------------------
    # Seed: initial source health records (one row per P1 source)
    # These are inserted at migration time so C24 (Source Health Monitor)
    # has rows to update rather than needing to INSERT on first check.
    # -----------------------------------------------------------------
    op.execute("""
        INSERT INTO source_health_records
            (source_id, source_name, source_category, status, updated_at)
        VALUES
            ('F1',  'NPPES NPI Registry',           'federal',   'unknown', NOW()),
            ('F2',  'OIG LEIE Exclusion Database',  'federal',   'unknown', NOW()),
            ('F3',  'SAM.gov Exclusions',            'federal',   'unknown', NOW()),
            ('F4',  'CMS Care Compare',              'federal',   'unknown', NOW()),
            ('F5',  'DEA Controlled Substances',     'federal',   'unknown', NOW()),
            ('F6',  'NPDB (Aggregate Only)',         'federal',   'unknown', NOW()),
            ('F7',  'CMS Medicare Provider Data',   'federal',   'unknown', NOW()),
            ('F8',  'ClinicalTrials.gov',            'academic',  'unknown', NOW()),
            ('F9',  'PubMed',                        'academic',  'unknown', NOW())
        ON CONFLICT (source_id) DO NOTHING
    """)


def downgrade() -> None:
    # Remove RLS policies
    op.execute("DROP POLICY IF EXISTS checkpoint_select_policy ON audit_chain_checkpoints")
    op.execute("DROP POLICY IF EXISTS checkpoint_insert_policy ON audit_chain_checkpoints")
    op.execute("ALTER TABLE audit_chain_checkpoints DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS audit_select_policy ON audit_events")
    op.execute("DROP POLICY IF EXISTS audit_insert_policy ON audit_events")
    op.execute("ALTER TABLE audit_events DISABLE ROW LEVEL SECURITY")

    # Revoke privileges
    for table in AUDIT_TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM medpro_readonly")
        op.execute(f"REVOKE ALL ON {table} FROM medpro_app")
        op.execute(f"REVOKE ALL ON {table} FROM medpro_audit_writer")

    for table in MAIN_TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM medpro_readonly")
        op.execute(f"REVOKE ALL ON {table} FROM medpro_app")

    # Drop roles
    op.execute("DROP ROLE IF EXISTS medpro_readonly")
    op.execute("DROP ROLE IF EXISTS medpro_audit_writer")
    op.execute("DROP ROLE IF EXISTS medpro_app")

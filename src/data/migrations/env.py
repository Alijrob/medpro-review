"""
Alembic env.py — medpro-review

Reads DATABASE_URL from environment. Supports both synchronous (run_migrations_offline)
and async (run_migrations_online) execution modes.

Usage:
    alembic -c src/data/migrations/alembic.ini upgrade head
    alembic -c src/data/migrations/alembic.ini downgrade -1

For the audit database (medpro_audit), set AUDIT_DATABASE_URL.
Both databases are migrated in sequence by the same Alembic config.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to the .ini file values
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Database URLs (injected via environment — never hardcoded)
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")
AUDIT_DATABASE_URL = os.environ.get("AUDIT_DATABASE_URL")

if DATABASE_URL is None:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Set it to the Aurora PostgreSQL connection string before running Alembic. "
        "Example: postgresql+psycopg2://medpro_admin:password@host:5432/medpro"
    )

# ---------------------------------------------------------------------------
# Metadata — unused here (we write DDL explicitly rather than using ORM metadata)
# so target_metadata stays None for Alembic autogenerate purposes.
# Explicit migrations are preferred over autogenerate for audit-grade DDL.
# ---------------------------------------------------------------------------
target_metadata = None


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generates SQL without a live connection.
    Useful for review before applying to production.
    """
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode — connects to the database directly.
    """
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""
conftest.py — Test fixtures for data layer tests.

Integration tests (marked with @pytest.mark.integration) require a live
PostgreSQL instance. Run them with:

    docker compose -f docker-compose.dev.yml up -d postgres
    DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro \
    AUDIT_DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro_audit \
    pytest tests/data/ -v -m integration

Unit tests (no mark) run without any database.
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Marker registration
# ---------------------------------------------------------------------------
# Registered in pyproject.toml [tool.pytest.ini_options] markers section.
# @pytest.mark.integration = requires a live PostgreSQL instance.


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set — skipping integration test")
    return url


@pytest.fixture(scope="session")
def audit_database_url() -> str:
    url = os.environ.get("AUDIT_DATABASE_URL")
    if not url:
        pytest.skip("AUDIT_DATABASE_URL not set — skipping integration test")
    return url


@pytest.fixture(scope="session")
def db_engine(database_url: str):
    """SQLAlchemy engine for the main medpro database."""
    from sqlalchemy import create_engine

    engine = create_engine(database_url, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def audit_engine(audit_database_url: str):
    """SQLAlchemy engine for the medpro_audit database."""
    from sqlalchemy import create_engine

    engine = create_engine(audit_database_url, echo=False)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def migrated_db(db_engine, audit_engine):
    """
    Run all Alembic migrations against both databases and return a tuple of engines.
    Rolled back (downgrade to base) after the test session.
    """
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("src/data/migrations/alembic.ini")

    # Run up
    command.upgrade(alembic_cfg, "head")

    yield (db_engine, audit_engine)

    # Tear down
    command.downgrade(alembic_cfg, "base")

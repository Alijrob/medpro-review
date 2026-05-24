-- dev-init-postgres.sql
-- Runs once when the Docker PostgreSQL container first starts.
-- Creates the audit database and grants basic access.
-- The application roles (medpro_app, medpro_audit_writer, medpro_readonly)
-- are created by Alembic migration 0003.

CREATE DATABASE medpro_audit
    WITH OWNER = medpro_admin
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TEMPLATE = template0;

\connect medpro_audit
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

\connect medpro
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

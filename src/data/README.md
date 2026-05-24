# Data Layer — researchyourdoctor.com

Phase 1-C deliverable. Contains database migrations, OpenSearch index templates, and Redis keyspace strategy.

---

## Migrations (Alembic)

**Location:** `src/data/migrations/`

| Revision | Description |
|----------|-------------|
| `0001` | Baseline schema — all main tables (medpro DB) |
| `0002` | Audit schema — audit_events + append-only triggers (medpro_audit DB) |
| `0003` | DB roles, RLS, privileges, P1 source health seeds |

### Run migrations (local dev)

```bash
# Start postgres
docker compose -f docker-compose.dev.yml up -d postgres

# Wait for it to be healthy, then run:
DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro \
  alembic -c src/data/migrations/alembic.ini upgrade head

AUDIT_DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro_audit \
  alembic -c src/data/migrations/alembic.ini upgrade head
```

### Run migrations (production)

Set `DATABASE_URL` to the Aurora writer endpoint (from Secrets Manager). Never hardcode credentials.

---

## OpenSearch Index Templates

**Location:** `src/data/opensearch/`

| File | Index pattern | Purpose |
|------|--------------|---------|
| `providers_index_template.json` | `providers-*` | Provider search (C14) |

### Apply template (local dev)

```bash
# Start OpenSearch
docker compose -f docker-compose.dev.yml up -d opensearch

# Apply template
curl -XPUT http://localhost:9200/_index_template/providers-template \
  -H "Content-Type: application/json" \
  -d @src/data/opensearch/providers_index_template.json

# Create dev index
curl -XPUT http://localhost:9200/providers-dev
```

---

## Redis Keyspace Strategy

**Location:** `src/data/redis/keyspace-strategy.md`

Documents all Redis key patterns, TTLs, and usage notes. Read before adding any new cache keys.

Key domains:
- `rate:` — API rate limiting (per user + per IP)
- `report:status:` — Report job status polling
- `search:` — Provider search results cache
- `profile:` — CanonicalProviderProfile cache
- `session:` — JWT session cache
- `source:health:` — Source health status cache
- `idem:` — Idempotency keys for report requests
- `workflow:report:` — Temporal workflow deduplication

---

## Local Dev Stack

```bash
# Start all data stores
docker compose -f docker-compose.dev.yml up -d

# Stop and wipe data (clean slate)
docker compose -f docker-compose.dev.yml down -v
```

| Service | Local URL | Credentials |
|---------|-----------|-------------|
| PostgreSQL | `localhost:5432` | `medpro_admin` / `devpass` |
| Redis | `localhost:6379` | password: `devredispass` |
| OpenSearch | `localhost:9200` | security disabled in dev |
| OpenSearch Dashboards | `localhost:5601` | — |

---

## Tests

```bash
# Unit tests (no database required) — included in default test run
PYTHONPATH=src pytest tests/data/ -v -m "not integration"

# Integration tests (requires running postgres)
docker compose -f docker-compose.dev.yml up -d postgres
DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro \
AUDIT_DATABASE_URL=postgresql+psycopg2://medpro_admin:devpass@localhost:5432/medpro_audit \
  PYTHONPATH=src pytest tests/data/ -v -m integration
```

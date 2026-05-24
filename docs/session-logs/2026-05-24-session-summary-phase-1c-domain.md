# Session Log — 2026-05-24
## Phase 1-B + Phase 1-C + Domain Lock

---

## What Was Built

### Domain Lock (DECISIONS.md Entry 008)
Jay registered **researchyourdoctor.com**. The domain was propagated across all project files: README, onboarding, DECISIONS.md, env.hcl files for dev/staging/production, and the phase tracker. Entry 008 was added to DECISIONS.md.

---

### Phase 1-B — Terraform/Terragrunt IaC Skeleton (non-deployed)

Full IaC skeleton for all AWS infrastructure. **Not deployed** — Entry 003 (AWS account/region) blocks `apply`.

**Structure:**
- `src/infrastructure/terragrunt.hcl` — Root config. S3 remote state backend, AWS provider generation with default tags, reads `env.hcl` from parent dirs.
- `src/infrastructure/environments/{dev,staging,production}/env.hcl` — Per-environment locals: account (PLACEHOLDER), region (PLACEHOLDER), domain, vpc_cidr, versions. PLACEHOLDER guard in Makefile + CI blocks accidental apply.
- `src/infrastructure/_envcommon/*.hcl` — 9 shared input files (vpc, kms, s3, ecr, iam, aurora, elasticache, opensearch, eks). Dependency blocks with `mock_outputs` for `validate`/`plan` without live state.
- `src/infrastructure/environments/{dev,staging,production}/{module}/terragrunt.hcl` — 27 env-specific overrides. Dev: single NAT, public API endpoint, no deletion protection. Production: larger nodes, 2 Aurora readers, 3 Redis nodes.

**Modules (9):**
- **vpc** — 3-tier subnets (public/private/database), NAT gateways (single or per-AZ), VPC endpoints (S3 Gateway, ECR, Secrets Manager Interface), VPC flow logs to S3.
- **kms** — 6 KMS keys (aurora, audit-worm, opensearch, elasticache, eks-secrets, s3-reports). Customer-managed, 7-year retention.
- **s3** — 3 buckets: reports (versioned, lifecycle to IA/Glacier), audit-worm (Object Lock COMPLIANCE 7yr, WORM — cannot delete even as root per DECISIONS.md Entry 005), access-logs.
- **ecr** — 12 repos, immutable tags, scan_on_push, lifecycle (expire untagged after 1 day, keep last 30 tagged).
- **iam** — IRSA roles per namespace via WebIdentity trust policy. `audit_writer` policy: PutObject + PutObjectRetention + DenyDelete on WORM bucket only.
- **aurora** — Aurora PostgreSQL 15, random master password in Secrets Manager, enhanced monitoring, `create_audit_database` flag for medpro_audit.
- **elasticache** — Redis 7.0, auth token in Secrets Manager, at-rest + transit encryption, multi-AZ when nodes > 1.
- **opensearch** — OpenSearch 2.11, fine-grained access control, zone awareness, KMS + node-to-node + enforce_https, CloudWatch slow logs.
- **eks** — EKS cluster, private API endpoint, KMS envelope encryption for secrets, OIDC provider for IRSA, 3 node groups (system/application/workers), 4 addons.

**CI/CD:**
- `.github/workflows/infra-validate.yml` — terraform fmt check + validate per module (matrix), placeholder-guard job fails build if PLACEHOLDER found in production env.hcl.
- `Makefile` — Real infra-init/plan/apply/validate/fmt targets with PLACEHOLDER guard.

**Commits:** 1a7f9ce (initial 1-B), subsequent commits during session (see git log from a7f9ce to 3de6ebd range).

---

### Phase 1-C — Data Store Baseline

All data store infrastructure defined and tested. **Not deployed** — local dev stack via docker-compose.

#### Alembic Migrations (`src/data/migrations/versions/`)

**0001_baseline_schema.py** — 9 main tables in `medpro` DB:
- `unified_id_bundles` — Provider identity anchor (primary_npi unique key)
- `normalized_records` — Raw ingest records, `raw_record_hash` UNIQUE (deduplication index)
- `canonical_provider_profiles` — Assembled profiles, status enum
- `users` — User accounts, `role` enum (consumer/admin/auditor)
- `use_agreements` — ToS acceptance. **Path B DB enforcement:** `ck_certified_personal_use_only` CHECK constrains `certified_personal_use_only = true` — cannot insert false at DB level
- `reports` — Report jobs, status enum, soft-delete flag
- `disputes` — Consumer dispute submissions
- `source_health_records` — Source availability tracking
- `derived_signals` — AI/ML outputs. `ck_explanation_nonempty` CHECK (length >= 10) enforces non-empty explanations
- Extensions: uuid-ossp, pg_trgm
- `set_updated_at()` trigger on all mutable tables

**0002_audit_schema.py** — Append-only audit tables in `medpro_audit` DB:
- `audit_events` — Immutable event log. `deny_audit_mutation()` SECURITY DEFINER function raises EXCEPTION on any UPDATE/DELETE. Triggers: `trg_audit_events_no_update`, `trg_audit_events_no_delete`.
- SHA-256 format CHECKs: `ck_event_hash_format`, `ck_before_hash_format`, `ck_after_hash_format`, `ck_prev_event_hash_format` (all check `~ '^[a-f0-9]{64}$'`).
- `event_hash` UNIQUE index (tamper indicator).
- `audit_chain_checkpoints` — Chain verification support.

**0003_db_roles_and_rls.py** — Roles, RLS, P1 seeds:
- 3 roles: `medpro_app` (CRUD on medpro), `medpro_audit_writer` (INSERT-only on audit tables — no UPDATE/DELETE ever), `medpro_readonly`.
- RLS: `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on both audit tables. Policies: INSERT for audit_writer, SELECT for app + readonly.
- Seeds 9 P1 sources: F1 (NPPES), F2 (OIG LEIE), F3 (SAM.gov), F4 (CMS Care Compare), F5 (DEA), F6 (NPDB), F7 (CMS Medicare), F8 (ClinicalTrials.gov), F9 (PubMed).

#### OpenSearch (`src/data/opensearch/providers_index_template.json`)
- Index pattern: `providers-*`
- Custom `name_analyzer` (ngram min=3/max=10 + lowercase + asciifolding) and `name_search_analyzer` (no ngram at query time)
- Fields: primary_npi (keyword), primary_name (nested text+keyword), name_variants, specialty, risk flags (has_active_exclusion/discipline/license), overall_risk_score, identity_confidence

#### Redis (`src/data/redis/keyspace-strategy.md`)
- 8 key domains with TTLs: rate (60s), report:status (24h), search (300s), profile (600s), session (JWT exp), source:health:all (30s), idem (24h), workflow:report (30min)
- Policy: allkeys-lru, no PII in Redis

#### Local Dev Stack (`docker-compose.dev.yml`)
- PostgreSQL 15 (port 5432, medpro_admin/devpass)
- Redis 7.0 (port 6379, requirepass devredispass, maxmemory 256mb allkeys-lru)
- OpenSearch 2.11 (port 9200, security disabled in dev)
- OpenSearch Dashboards (port 5601)
- `scripts/dev-init-postgres.sql` — creates medpro_audit DB + installs uuid-ossp

#### Tests (`tests/data/`)
- **20 unit tests** across 3 classes — all pass without any database:
  - `TestMigrationFiles` (13): revision chain, table presence, constraint presence, trigger presence, hash format checks, role grants
  - `TestOpenSearchTemplate` (5): valid JSON, npi field, name fields, risk fields, index pattern
  - `TestRedisKeyspaceDoc` (2): file exists, covers required domains
- **7 integration tests** (`@pytest.mark.integration`) — require DATABASE_URL + AUDIT_DATABASE_URL. Test: main tables exist, audit tables exist, Path B constraint enforced at DB level, audit INSERT succeeds, audit UPDATE blocked by trigger, P1 sources seeded, deduplication index enforced.
- **pyproject.toml** updated: data package added, alembic/sqlalchemy/psycopg2-binary dependencies, integration marker registered.

**Phase 1-C commit:** 8e04567

---

## Key Decisions Made This Session

| Entry | Decision |
|-------|----------|
| 008 | Domain locked: researchyourdoctor.com |

Entries 001-007 were already locked. Entry 003 (AWS account/region) remains the only open blocker for IaC deployment.

---

## Test State at Session End

```
tests/schema/    — 44 passed (Pydantic v2 schema models)
tests/data/      — 20 passed (data layer unit tests, no DB)
Total            — 64 passed
```

All tests run from `medpro-review/` root with `PYTHONPATH=src pytest tests/ -m "not integration"`.

---

## Commits This Session

| SHA | Message |
|-----|---------|
| 1a7f9ce | feat(infra): Phase 1-B Terraform/Terragrunt IaC skeleton |
| (several) | Phase 1-B module and env file commits |
| 8e04567 | feat(data): Phase 1-C data store baseline |
| 63a928d | docs: update onboarding for Phase 1-C complete, 1-D up next |

**HEAD at session end:** `63a928d`
**Repo:** https://github.com/Alijrob/medpro-review/commit/63a928d

---

## Open Blockers (unchanged from session start)

1. **Phase 0 Legal Gate** — FCRA determination blocking production deployment. Engineering work (IaC, schema, data layer) can continue.
2. **Auth0 vs. Okta** — Must be locked before Phase 1-F (Auth Service). See DECISIONS.md Entry 002.
3. **AWS account / region** — PLACEHOLDER in all env.hcl files. Must be filled in before `terragrunt apply`. See DECISIONS.md Entry 003.
4. **Ground truth dataset** — Required for C12 identity resolution (>98% precision). Owner must be assigned before Phase 2-E.

---

## Phase 1-D Preview (next session)

**Observability Stack Config:**
- OpenTelemetry collector config (traces + metrics + logs) — Kubernetes DaemonSet/Sidecar config files
- Prometheus scrape rules and alerting rules (provider pipeline SLOs, source health, audit chain lag)
- Grafana dashboard definitions (JSON) — pipeline SLO board, source health board, audit board
- Sentry DSN wiring per service (Python SDK config, error grouping rules)
- All configs non-deployed — same pattern as IaC: code the config, apply when Entry 003 resolved

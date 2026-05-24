# Redis Keyspace Strategy — researchyourdoctor.com

**Version:** 1.0
**Phase:** 1-C
**Redis version:** 7.0 (ElastiCache)

All keys are namespaced as `{env}:{domain}:{key}` to avoid collisions across environments sharing a cluster (dev/staging). Production uses a dedicated cluster.

TTLs are enforced on all keys — no persistent Redis data. Aurora PostgreSQL is the system of record.

---

## Key Patterns

### 1. API Rate Limiting

**Purpose:** Prevent abuse of the report request and search endpoints.
**Used by:** C8 (API Gateway) via OPA rate limit policy.

```
rate:{user_id}:{endpoint}          TTL: 60s
rate:ip:{ip_address}:{endpoint}    TTL: 60s
```

**Values:** Integer (INCR counter). Checked against limit thresholds in OPA policy.

**Limits (initial):**
| Endpoint | Per-user limit | Per-IP limit |
|----------|---------------|--------------|
| POST /reports | 5/min | 10/min |
| GET /search | 30/min | 60/min |
| POST /disputes | 3/min | 5/min |

---

### 2. Report Job Status

**Purpose:** Fast status polling without hitting Aurora on every request.
**Used by:** Frontend (Next.js) polling during report generation.

```
report:status:{report_id}          TTL: 24h
```

**Value (JSON string):**
```json
{
  "report_id": "uuid",
  "status": "in_progress",
  "sources_succeeded": ["F1", "F2"],
  "sources_failed": [],
  "sources_pending": ["S5", "S10"],
  "started_at": "2026-05-24T10:00:00Z",
  "estimated_completion": "2026-05-24T10:10:00Z"
}
```

Written by the Temporal workflow activity on each status transition.
Evicted after 24h or on report completion (whichever first).

---

### 3. Provider Search Cache

**Purpose:** Cache OpenSearch results for popular searches to reduce OS query load.
**Used by:** C14 (Provider Search Service).

```
search:{query_hash}                TTL: 300s (5 min)
```

**Key:** `query_hash` = SHA-256 of the normalized search parameters (name, state, specialty).
**Value (JSON string):** First page of OpenSearch results (up to 20 providers).

Not cached: searches with zero results (prevents empty-result cache poisoning).

---

### 4. Provider Profile Cache

**Purpose:** Cache the CanonicalProviderProfile for providers with recent report activity.
**Used by:** C17 (Report Generation Service) during report assembly.

```
profile:{primary_npi}              TTL: 600s (10 min)
```

**Value:** JSON-serialized `CanonicalProviderProfile` (truncated to fields needed for report).

Invalidated explicitly when C13 (Entity Linking & Merge) rebuilds the profile.
Pattern: `DEL profile:{primary_npi}` on profile rebuild.

---

### 5. Session / Auth Cache

**Purpose:** Cache decoded JWT claims to avoid re-validating tokens on every request.
**Used by:** C8 (API Gateway) auth middleware.

```
session:{jti}                      TTL: matches JWT exp claim (max 1h)
```

**Value (JSON string):**
```json
{
  "user_id": "uuid",
  "role": "consumer",
  "email": "user@example.com",
  "has_current_agreement": true
}
```

Invalidated on logout: `DEL session:{jti}`.
JTI = JWT ID claim (unique per token, included by Auth0/Okta).

---

### 6. Source Health Cache

**Purpose:** Cache the current health status of all sources for fast OPA policy decisions.
**Used by:** C8 (OPA sidecar) when deciding whether to attempt a source during report generation.

```
source:health:all                  TTL: 30s
```

**Value (JSON string):** Map of `source_id -> SourceStatus` for all sources.

Updated by C24 (Source Health Monitor) after each health check. The 30s TTL means
the API gateway may briefly route to a degraded source — acceptable for MVP.

---

### 7. Idempotency Keys (Report Requests)

**Purpose:** Prevent duplicate report creation if the client retries a failed POST /reports.
**Used by:** C8 (API Gateway) idempotency layer.

```
idem:{idempotency_key}             TTL: 24h
```

**Value:** `report_id` (string UUID) of the original report created for this key.

Client generates `idempotency_key` (UUID) and sends it as `X-Idempotency-Key` header.
On retry: gateway returns the original report_id without creating a new one.

---

### 8. Temporal Workflow Deduplication

**Purpose:** Prevent duplicate Temporal workflow starts for the same report.
**Used by:** Report request handler before calling Temporal SDK.

```
workflow:report:{report_id}        TTL: 30min
```

**Value:** Temporal workflow run ID (string).

If key exists when a start is attempted, the handler checks if the workflow is
still running (via Temporal SDK query) rather than starting a new one.

---

## Operational Notes

- **Max memory policy:** `allkeys-lru` — evict least-recently-used keys when memory full.
- **Cluster mode:** Enabled in staging/production. All keys use hash tags if they need to land on the same shard (not applicable here — all keys are independent).
- **Key expiry monitoring:** CloudWatch alert if `expired_keys` rate spikes (may indicate under-provisioned TTL or cache stampede).
- **No sensitive PII in Redis:** User email and other PII are never cached. Session cache stores only role and flags.
- **Auth token:** Redis auth token is fetched from Secrets Manager at application startup. Never stored in code.

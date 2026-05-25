# Audit Ledger Service (C5-audit) — Phase 1-I shell

The append-only, hash-chained audit ledger that replaces QLDB (DECISIONS.md Entry
005). Every data write, report generation, correction, access, and user action in
the platform emits one `AuditEvent`; this service owns the chain and verifies it.
Non-deployed shell; runnable locally.

---

## What it does

| Concern | Where | Behavior |
|---------|-------|----------|
| Append | `ledger.py::AuditLedger.append` | links the event to its per-target chain head, computes `event_hash`, appends immutably |
| Hash chaining | `ledger.py` | `prev_event_hash` per `(target_type, target_id)`; `event_hash` via `AuditEvent.compute_hash` |
| Verify | `ledger.py::verify_chain / verify_all` | recompute every hash + check linkage; detects altered contents **and** removed/reordered events |
| Checkpoints | `ledger.py::create_checkpoint` | per-`target_type` head + count snapshot (mirrors `audit_chain_checkpoints`) |

The canonical `AuditEvent` model (`src/schema/v1/audit.py`) deliberately does **not**
own the chain — it carries the fields and `compute_hash`; this service assigns
`prev_event_hash`/`event_hash`. Callers never supply those.

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/healthz` | Liveness. |
| GET | `/readyz` | Readiness; reports whether the Aurora audit DB is wired. |
| POST | `/v1/audit/events` | Append an event (201; returns it with computed hashes). |
| GET | `/v1/audit/chains/{target_type}/{target_id}` | The per-target chain. |
| GET | `/v1/audit/chains/{target_type}/{target_id}/verify` | Verify that chain (409 if tampered). |
| POST | `/v1/audit/checkpoints/{target_type}` | Snapshot a target_type's head (404 if none). |
| GET | `/v1/audit/verify` | Verify every chain (409 if any fail). |

---

## Topology

Runs in the **`workers`** namespace with service account **`workers-sa`** (IRSA from
the 1-B iam module; DECISIONS.md Entry 013 — the internal writer has no dedicated
namespace in the locked Entry 011 topology). **Internal only** — a ClusterIP Service,
no Ingress; reached intra-cluster from the services that emit events, gated by the
`workers` NetworkPolicy baseline (`deploy/networkpolicies.yaml`). Deployed by the
`audit-service` ArgoCD Application (`workloads` project). Image is PLACEHOLDER until
built and Entry 003 resolves; the deploy guard blocks sync until then.

In deploy it connects to the Aurora **`medpro_audit`** DB as the INSERT-only
**`medpro_audit_writer`** role (migration 0003). UPDATE/DELETE are blocked by the
`deny_audit_mutation` trigger + RLS regardless. The S3 WORM export of the chain is
**Phase 4-F**, not 1-I.

---

## Shell limitation

Storage is in memory and process-local (`ledger.py`), a stand-in for the Aurora audit
DB until `AUDIT_DATABASE_URL` is wired. Do not rely on it across replicas or restarts.

---

## Run + test

```bash
make run-audit                                            # uvicorn on :8001, /docs
PYTHONPATH=src pytest tests/backend/test_audit_service.py -v   # 15 behavior tests
kustomize build src/backend/audit_service/deploy          # Deployment + Service + NetworkPolicies
```

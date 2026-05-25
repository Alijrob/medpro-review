# OPA Policy Bundle (component C2) — Phase 1-H baseline

This directory is the source of truth for the medpro-review authorization and
privacy policies enforced by **Open Policy Agent (OPA, component C2)**. Status:
**NON-DEPLOYED** (no cluster — DECISIONS.md Entry 003).

## What's here

| File | Package | Purpose |
|------|---------|---------|
| `authz.rego` | `medpro.authz` | Baseline API authorization. `data.medpro.authz.allow` is the boolean the gateway queries. |
| `redaction.rego` | `medpro.redaction` | Privacy redaction — suppresses physician personal PII (home address, etc.) from consumer output (DECISIONS.md Entry 007). |
| `*_test.rego` | (same packages) | `opa test` unit tests. Excluded from the runtime ConfigMap. |
| `kustomization.yaml` | — | Generates the `opa-policy` ConfigMap into the `api-gateway` namespace. |

## How it runs

OPA is deployed as a **per-service sidecar** (the recommended OPA model — host-local
decisions, no extra network hop, no shared-availability risk). In Phase 1-H only the
api-gateway has a sidecar:

```
api-gateway pod
├── api-gateway container  ── HTTP ──▶ 127.0.0.1:8181 (OPA decision API, localhost only)
└── opa sidecar            ── mounts ─▶ /policy  (this bundle, via the opa-policy ConfigMap)
```

The `opa-policy` ConfigMap is delivered by its own ArgoCD app
(`src/gitops/argocd/workloads/opa-policy.yaml`, **sync-wave -1**) so it exists before
the gateway pod (wave 0) starts. The gateway's `require_authz` hook is switched on
in-cluster via `OPA_ENABLED=true` + `OPA_URL=http://127.0.0.1:8181` on the Deployment;
the Python default stays `opa_enabled=false` so `make run-gateway` works locally with no
sidecar.

When a second service gets an OPA sidecar (the report service, C17, Phase 2), it mounts
the **same bundle** in its own namespace via an analogous app.

## Authz contract

`src/backend/api_gateway/opa.py::require_authz` sends:

```json
{ "subject": "auth0|…", "roles": ["consumer"], "permissions": ["create:report"],
  "action": "create", "resource": "report" }
```

`allow` defaults to **deny**. Rules: a `consumer` may `create` a `report` and `read` the
consumer surfaces; a scoped `"<action>:<resource>"` permission grant overrides the role
rules; an `admin` is allowed only on the `admin*` surface.

## Redaction contract

`medpro.redaction` takes `{ "audience": "consumer"|"provider_self"|"internal", "profile": {…} }`
and exposes `redact` (the set of profile keys to suppress) and `redacted` (the profile with
those keys removed). Consumers never see `home_address`, `personal_phone`, `personal_email`,
`date_of_birth`, or `ssn`. Public-record professional data (license, NPI, disciplinary
actions, practice address) is always retained. `provider_self` (the CCPA portal, C22) and
`internal` audiences see everything.

## Validate locally

```bash
make opa-test          # opa check + opa test (requires the opa CLI)
opa test src/policy -v # 16 unit tests
kustomize build src/policy   # renders the opa-policy ConfigMap
```

CI: `.github/workflows/opa-validate.yml` runs `opa check` + `opa test` on every change here.

# Session Log: 2026-05-24
## Phase 1-E — GitOps + CI/CD Skeleton (ArgoCD app-of-apps)

---

## Summary (readable cold)

This session built Phase 1-E, the GitOps / continuous-delivery layer, on top of the already-complete Phase 1-B IaC and Phase 1-D observability config. The deliverable is an ArgoCD app-of-apps defined entirely in `src/gitops/`: a single root Application renders thirteen child Applications, one per platform component, each carrying an `argocd.argoproj.io/sync-wave` annotation that encodes the documented deploy order across six waves (External Secrets Operator + namespace, then the External Secrets CRs, then kube-prometheus-stack which installs the monitoring CRDs, then Loki/Tempo/ServiceMonitors/PrometheusRules/the OTel pipeline ConfigMap, then the OTel gateway+agent and Grafana provisioning ConfigMaps, then Grafana last). Helm chart versions are pinned in a single `charts-lock.yaml` and enforced by the test suite, so no Application can drift from the lock or use a floating revision. Two awkward Phase 1-D shapes were handled without duplication: the raw Prometheus rule groups (not valid CRDs) are wrapped in `PrometheusRule` CRDs under `argocd/monitoring/` with a parity test that fails CI if they diverge from the source; and the Grafana datasource/dashboard files plus the OTel gateway pipeline are turned into ConfigMaps by kustomize `configMapGenerator` overlays co-located with the 1-D files (so kustomize stays within its own root and ArgoCD's default RootOnly load restrictor is preserved). A deploy-time PLACEHOLDER guard blocks any sync while account-specific values remain unresolved. Everything is non-deployed, matching the 1-B and 1-D pattern, and waits on DECISIONS.md Entry 003 (AWS account/region) plus the ArgoCD bootstrap step. New decision logged as Entry 010.

---

## Repo URLs

- Code: https://github.com/Alijrob/medpro-review
- Tracker (pagios-ops): https://github.com/Alijrob/pagios-ops/blob/main/trackers/medpro-review-phase-tracker.md

---

## Commit SHAs

| Repo | SHA | Message |
|------|-----|---------|
| medpro-review | 3b37035 | Phase 1-E: GitOps + CI/CD skeleton (ArgoCD app-of-apps, sync waves, pinned charts) |

**medpro-review HEAD before this session:** 3594fe7 (matched the logged resume SHA — no drift)

---

## What Was Built (Phase 1-E)

All under `src/gitops/` unless noted. Non-deployed config only.

### Pinned versions
- `charts-lock.yaml`: repoURL + chart + version for argo-cd, external-secrets, kube-prometheus-stack, loki, tempo-distributed, grafana, opentelemetry-collector, plus the git source. Single source of truth; cross-checked by tests.

### Bootstrap
- `argocd/bootstrap/namespace.yaml`: argocd namespace.
- `argocd/bootstrap/install-values.yaml`: argo-cd Helm values (HA control plane, system node group, insecure-behind-ALB). Default RootOnly kustomize restrictor kept.
- `argocd/bootstrap/root-app.yaml`: the app-of-apps root Application, watches `argocd/apps/`.

### Project
- `argocd/projects/platform.yaml`: AppProject. Source-repo allowlist = git repo + 6 chart repos. Destinations = in-cluster argocd/observability/external-secrets. Cluster + namespace resource whitelists (platform project manages CRDs/namespaces).

### Child Applications (13, sync-waved)
- wave 0: `external-secrets-operator` (Helm), `observability-namespace` (directory).
- wave 1: `external-secrets-config` (directory).
- wave 2: `kube-prometheus-stack` (Helm multi-source) — installs monitoring CRDs.
- wave 3: `loki`, `tempo` (Helm multi-source); `service-monitors`, `prometheus-rules`, `otel-collector-config` (directory/kustomize).
- wave 4: `otel-collector-gateway`, `otel-collector-agent` (Helm multi-source); `grafana-config` (kustomize).
- wave 5: `grafana` (Helm multi-source).

### Rule wrappers + agent values
- `argocd/monitoring/recording-prometheusrule.yaml`, `alerting-prometheusrule.yaml`: PrometheusRule CRDs wrapping the 1-D rule groups verbatim (parity-tested).
- `argocd/otel/agent-values.yaml`: Phase 1-E agent (DaemonSet) Helm values — forward-only OTLP to the gateway (1-D shipped gateway values only).

### Kustomize overlays (co-located with 1-D files)
- `src/observability/grafana/kustomization.yaml`: configMapGenerator → `medpro-grafana-datasources` (label grafana_datasource) + `medpro-grafana-dashboards` (label grafana_dashboard, folder medpro-review).
- `src/observability/otel-collector/kustomization.yaml`: configMapGenerator → `otel-gateway-pipeline` from collector-config.yaml.

### Guard, CI, tests, docs
- `scripts/gitops-guard.sh` + `make gitops-guard`: deploy-time PLACEHOLDER guard.
- `.github/workflows/gitops-validate.yml`: pytest + `kustomize build` (guard is deploy-time, not CI).
- `Makefile`: `gitops-validate`, `gitops-guard` targets.
- `tests/gitops/test_gitops_config.py`: 138 unit tests.
- `DECISIONS.md` Entry 010; `src/gitops/README.md`; onboarding updated.

---

## Phase Status

- Phase 1-E: COMPLETE (commit 3b37035).
- Phase 1-F (Auth Service Shell): UP NEXT. Blocked on Entry 002 (Auth0 vs Okta) + Entry 009 (Sentry hosting).
- Phases 0 through 1-D: complete (prior sessions).

---

## Next Likely Step

Phase 1-F: Auth Service Shell — first FastAPI application service (auth overlay on Auth0/Okta), added as the first child Application in a workload-scoped AppProject. Requires Entry 002 and Entry 009 locked first.

---

## Known Blockers

1. Phase 0 legal gate: FCRA determination pending. Config can continue; no running services until it clears.
2. AWS account/region: PLACEHOLDER everywhere. Blocks any deploy. Domain locked (researchyourdoctor.com, Entry 008).
3. Auth0 vs Okta: must lock before Phase 1-F (Entry 002).
4. Sentry SaaS vs self-hosted: open (Entry 009), PII residency. Decide before Phase 1-F.
5. Ground truth dataset: needed before Phase 2-E (C12).

---

## Verified Checks

- medpro-review HEAD before work = 3594fe7 == logged resume SHA (no drift). pagios-ops at f1a1a6d (real git repo, re-cloned prior session).
- Full suite: `PYTHONPATH=src pytest tests/ -m "not integration"` => 241 passed, 7 deselected (44 schema + 20 data + 39 observability + 138 gitops). No regressions in prior phases.
- `kustomize build src/observability/grafana` and `.../otel-collector` both render their ConfigMaps under default RootOnly restrictor (kustomize v5.8.1).
- `scripts/gitops-guard.sh` correctly exits 1 while PLACEHOLDERs survive (deploy blocked).
- No secrets in committed gitops files (DSN-shape + AWS access-key scans clean).
- PrometheusRule wrappers parity-equal to the 1-D source rules (test).

---

## Blocked Checks

- No live ArgoCD/cluster validation: no EKS cluster exists (Entry 003). ArgoCD Application manifests are not validated against the live ArgoCD CRD schema, and Helm value compatibility is not confirmed by a live chart render.
- 7 integration tests (tests/data) still not run: require a live PostgreSQL.

---

## Unverified Items

- Pinned Helm chart versions in charts-lock.yaml are a known-good set as of 2026-05-24, not verified against a live cluster or `helm template`. Re-verify before first deploy.
- OTel gateway config-mount wiring: the gateway must mount the `otel-gateway-pipeline` ConfigMap and run with `--config` pointing at it; the exact opentelemetry-collector chart keys are pinned against the live chart version at deploy (DECISIONS.md Entry 010). Left out of the manifest to avoid an unverified chart binding.
- Per-environment value overlays (staging/production root apps) are noted but not authored; layered in Phase 1-F when env configs and services exist.

---

## Tests Run

```
PYTHONPATH=src pytest tests/ -m "not integration"
=> 241 passed, 7 deselected
   44  tests/schema/test_v1_models.py
   20  tests/data/test_migrations.py
   39  tests/observability/test_observability_config.py
   138 tests/gitops/test_gitops_config.py

kustomize build src/observability/grafana          # 2 ConfigMaps
kustomize build src/observability/otel-collector   # 1 ConfigMap
scripts/gitops-guard.sh                            # exit 1 (PLACEHOLDERs present — deploy blocked)
```

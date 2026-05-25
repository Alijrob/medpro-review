# GitOps / Continuous Delivery — researchyourdoctor.com

Phase 1-E deliverable (component **C3**, GitOps layer). ArgoCD **app-of-apps** that
deploys the Phase 1-D observability stack (and, from Phase 1-F, the application
services) onto the EKS cluster provisioned by the Phase 1-B IaC.

**Status: NON-DEPLOYED.** These are manifests only. Nothing syncs until the EKS
cluster exists (DECISIONS.md Entry 003 — AWS account/region) and ArgoCD is
bootstrapped onto it. Same pattern as the 1-B IaC and 1-D observability skeletons.

---

## Layout

```
src/gitops/
  charts-lock.yaml              # pinned Helm chart versions (single source of truth)
  argocd/
    bootstrap/
      namespace.yaml            # argocd namespace
      install-values.yaml       # argo-cd Helm values (the GitOps engine itself)
      root-app.yaml             # the app-of-apps root Application
    projects/
      platform.yaml             # AppProject scoping repos + destinations
    apps/                       # one child Application per component (sync-waved)
      external-secrets-operator.yaml   loki.yaml             otel-collector-agent.yaml
      observability-namespace.yaml     tempo.yaml            grafana-config.yaml
      external-secrets-config.yaml     service-monitors.yaml grafana.yaml
      kube-prometheus-stack.yaml       prometheus-rules.yaml
      otel-collector-config.yaml       otel-collector-gateway.yaml
    monitoring/                 # PrometheusRule CRD wrappers (parity-tested vs 1-D)
      recording-prometheusrule.yaml
      alerting-prometheusrule.yaml
    otel/
      agent-values.yaml         # Phase 1-E agent (DaemonSet) Helm values
```

Two kustomize overlays live next to the 1-D files they wrap (so kustomize stays
within its own root): `src/observability/grafana/kustomization.yaml` and
`src/observability/otel-collector/kustomization.yaml`.

---

## App-of-apps + sync waves

`root-app.yaml` is the only manifest applied by hand. It renders every child in
`apps/`. Each child carries an `argocd.argoproj.io/sync-wave` so ArgoCD applies
them in dependency order:

| Wave | Applications | Why |
|------|--------------|-----|
| 0 | `external-secrets-operator`, `observability-namespace` | CRDs + namespace must exist first |
| 1 | `external-secrets-config` | SecretStore/ExternalSecret CRs need ESO CRDs + the namespace |
| 2 | `kube-prometheus-stack` | installs the `monitoring.coreos.com` CRDs (ServiceMonitor, PrometheusRule) |
| 3 | `loki`, `tempo`, `service-monitors`, `prometheus-rules`, `otel-collector-config` | need the monitoring CRDs; OTel pipeline ConfigMap rendered |
| 4 | `otel-collector-gateway`, `otel-collector-agent`, `grafana-config` | gateway/agent + Grafana provisioning ConfigMaps |
| 5 | `grafana` | last, so datasources, dashboards, backends, and admin secret all exist |

---

## Pinned chart versions

`charts-lock.yaml` is the single source of truth. Each chart-backed Application is
a multi-source app: the chart comes from the pinned upstream repo, the value file
comes from this git repo via the `$values` ref. `make gitops-validate` fails if an
Application's `repoURL`/`chart`/`targetRevision` drifts from the lock or uses a
floating revision.

> Versions are pinned to a known-good set as of 2026-05-24 and are **not** verified
> against a live cluster. Re-verify each version and run `helm template` before the
> first deploy.

## How the 1-D config is consumed

- **Helm value files** (`prometheus-values.yaml`, `loki-values.yaml`, etc.) — passed
  to the upstream chart via `$values/...`.
- **Raw CRDs already valid as manifests** (`namespace.yaml`, `external-secrets.yaml`,
  `servicemonitors.yaml`) — applied as directory sources with `directory.include`.
- **Prometheus rule groups** — the 1-D `rules/*.yaml` are raw rule groups, not CRDs,
  so they are wrapped in `PrometheusRule` CRDs under `monitoring/`. A parity test
  keeps the wrappers identical to the source: edit the 1-D file, then mirror it.
- **Grafana datasources/dashboards** and the **OTel gateway pipeline** — turned into
  ConfigMaps by kustomize `configMapGenerator` overlays (no duplication; the real
  1-D files are the input).

### Collector config injection (open wiring)

The `otel-collector-config` app renders `collector-config.yaml` into the
`otel-gateway-pipeline` ConfigMap. The gateway Deployment must mount that ConfigMap
and run with `--config` pointing at it; the exact opentelemetry-collector chart keys
are pinned against the live chart version before first deploy. Tracked in
DECISIONS.md Entry 010.

---

## Deploy (once Entry 003 is resolved)

```bash
# 0. Cluster exists (Phase 1-B applied) and kubeconfig points at it.
scripts/gitops-guard.sh                       # must pass — no PLACEHOLDERs left

# 1. Install ArgoCD
kubectl apply -f src/gitops/argocd/bootstrap/namespace.yaml
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd -n argocd --version 7.7.5 \
  -f src/gitops/argocd/bootstrap/install-values.yaml

# 2. Register the projects and the platform root app-of-apps
kubectl apply -f src/gitops/argocd/projects/platform.yaml
kubectl apply -f src/gitops/argocd/projects/workloads.yaml
kubectl apply -f src/gitops/argocd/bootstrap/root-app.yaml
# ArgoCD now syncs every platform child in wave order.

# 3. Once the platform is healthy, register the workloads app-of-apps
kubectl apply -f src/gitops/argocd/bootstrap/workloads-root-app.yaml
# Renders the application services (api-gateway, ...) under the `workloads` project.
```

### Two app-of-apps

- **platform** (`bootstrap/root-app.yaml` → `apps/`) — cluster add-ons, observability,
  secrets. Trusted with cluster-scoped resources (CRDs, namespaces).
- **workloads** (`bootstrap/workloads-root-app.yaml` → `workloads/`) — application
  services in per-group namespaces (`api-gateway`, `identity`, `reports`, `workers`;
  DECISIONS.md Entry 011). Tightly scoped: git repo only, namespaced resources only.
  The api-gateway (C8) is the first service; its deploy bundle lives in
  `src/backend/api_gateway/deploy/`. The **opa-policy** app (sync-wave -1) delivers the
  OPA policy bundle (`src/policy`) as the `opa-policy` ConfigMap into the `api-gateway`
  namespace before the gateway pod (wave 0) starts — the gateway's OPA sidecar mounts it
  (Phase 1-H; DECISIONS.md Entry 012).

### PLACEHOLDER guard

`scripts/gitops-guard.sh` (`make gitops-guard`) scans the config ArgoCD renders
(`src/observability/`, `src/gitops/argocd/otel/`, `src/backend/api_gateway/deploy/`,
`src/policy/`) and blocks deploy while any PLACEHOLDER survives. Resolve DECISIONS.md
Entry 003 first. CI does **not** run the guard — PLACEHOLDERs are expected in this
non-deployed phase.

---

## Validate locally

```bash
make gitops-validate                          # 138 structural + parity tests, no cluster

# Or directly:
PYTHONPATH=src pytest tests/gitops/ -v
kustomize build src/observability/grafana     # ConfigMaps render
kustomize build src/observability/otel-collector
```

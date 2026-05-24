# Observability Stack — researchyourdoctor.com

Phase 1-D deliverable (component **C4**). OpenTelemetry-based, vendor-neutral observability config for the medpro-review platform.

**Status: NON-DEPLOYED.** These are config files only. Nothing runs until the EKS cluster exists (DECISIONS.md Entry 003 — AWS account/region) and the Phase 1-E GitOps layer (ArgoCD) applies them. Same pattern as the Phase 1-B IaC skeleton.

---

## Signal flow

```
  12 services (OTLP SDK)                     pull (/metrics)
        │                                          │
        ▼                                          ▼
  otel-agent (DaemonSet) ──► otel-gateway ──► Prometheus ◄── ServiceMonitors
                                  │  (collector-config.yaml)      │
                  ┌───────────────┼───────────────┐              │
                  ▼               ▼               ▼              ▼
               Tempo          Prometheus         Loki         Grafana
              (traces)        (metrics)         (logs)      (dashboards)
                  └───────────────┴───────────────┴──────────────┘
                              errors ──► Sentry (PII-scrubbed)
```

All services push traces, metrics, and logs via OTLP to the collector gateway, which fans out to Tempo (traces), Prometheus (metrics, via remote_write), and Loki (logs). Grafana reads all three and correlates traces↔logs↔metrics. Sentry receives errors directly from each service SDK, with PII scrubbed at the source.

---

## Layout

| Path | Purpose |
|------|---------|
| `otel-collector/collector-config.yaml` | Gateway pipeline: OTLP receivers → Tempo/Prometheus/Loki exporters, k8s enrichment, PII scrub |
| `otel-collector/values.yaml` | Helm values for the collector (gateway mode) |
| `prometheus/prometheus-values.yaml` | kube-prometheus-stack Helm values (Prometheus + Alertmanager; bundled Grafana disabled) |
| `prometheus/rules/recording-rules.yaml` | Pre-computed SLIs (service RED metrics, pipeline, audit) |
| `prometheus/rules/alerting-rules.yaml` | Alerts: `service_slo`, `source_health`, `audit_ledger`, `pipeline` |
| `prometheus/servicemonitors.yaml` | ServiceMonitor covering all 12 services |
| `loki/loki-values.yaml` | Loki Helm values (S3 backend, 30-day retention) |
| `tempo/tempo-values.yaml` | Tempo Helm values (S3 backend, 14-day retention, span metrics) |
| `grafana/datasources.yaml` | Prometheus/Loki/Tempo datasources + trace↔log correlation |
| `grafana/grafana-values.yaml` | Grafana Helm values (admin pw via External Secrets) |
| `grafana/dashboards/*.json` | Pipeline SLO, Source Health, Audit Ledger dashboards |
| `sentry/sentry_config.py` | Shared Python Sentry init with mandatory PII scrubbing |
| `k8s/namespace.yaml` | `observability` namespace |
| `k8s/external-secrets.yaml` | Pulls Grafana admin pw + Sentry DSNs from AWS Secrets Manager |

---

## PII handling (non-negotiable)

This platform handles regulated healthcare-adjacent data. Provider/user identifiers must never reach a telemetry backend. Scrubbing happens at **two layers**:

1. **OTel collector** — `attributes/scrub_pii` processor deletes/hashes known sensitive span and log attributes before export.
2. **Sentry SDK** — `before_send` / `before_send_transaction` in `sentry_config.py` drop PII keys and redact SSN/email patterns; `send_default_pii=False`, `max_request_body_size="never"`.

Anyone adding a new metric, log field, or span attribute must confirm it carries no PII.

---

## Deploy (Phase 1-E, once Entry 003 is resolved)

Each tool is an ArgoCD Application pointing at these files. Chart versions are pinned in the Application manifests (not here). Deploy order:

1. `k8s/namespace.yaml` + External Secrets Operator (cluster add-on)
2. `k8s/external-secrets.yaml`
3. kube-prometheus-stack (`prometheus/`) → Tempo (`tempo/`) → Loki (`loki/`)
4. OTel collector (`otel-collector/`)
5. Grafana (`grafana/`) with datasources + dashboards

### PLACEHOLDER guard

Account-specific values are `PLACEHOLDER-*` (S3 bucket names, AWS region, Secrets Manager path prefix). `make obs-validate` and the CI workflow fail if a PLACEHOLDER survives into a deploy. Resolve DECISIONS.md Entry 003 first.

---

## Validate locally

```bash
# Structure + syntax checks (no cluster required)
make obs-validate

# Or directly:
PYTHONPATH=src pytest tests/observability/ -v
```

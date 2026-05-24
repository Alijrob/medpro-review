"""
test_observability_config.py — Phase 1-D config validation.

Unit tests (no mark, no live cluster): verify that every observability config
file parses, contains the required structure, scrubs PII, and embeds no secrets.
Mirrors the Phase 1-C data-layer test approach.

Run:
    PYTHONPATH=src pytest tests/observability/ -v
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

OBS = Path(__file__).resolve().parents[2] / "src" / "observability"

# The 12 deployable services (must match src/infrastructure/_envcommon/ecr.hcl).
SERVICES = [
    "api-gateway",
    "identity-resolver",
    "normalization-worker",
    "entity-linker",
    "report-generator",
    "source-adapter",
    "source-health-monitor",
    "data-quality",
    "dispute-worker",
    "notifications",
    "audit-writer",
    "opa-sidecar",
]


def _load_yaml(rel: str):
    return yaml.safe_load((OBS / rel).read_text())


def _load_yaml_all(rel: str):
    return list(yaml.safe_load_all((OBS / rel).read_text()))


def _load_json(rel: str):
    return json.loads((OBS / rel).read_text())


# ---------------------------------------------------------------------------
class TestFilesParse:
    """Every YAML and JSON config must parse."""

    @pytest.mark.parametrize(
        "rel",
        [
            "otel-collector/collector-config.yaml",
            "otel-collector/values.yaml",
            "prometheus/prometheus-values.yaml",
            "prometheus/rules/recording-rules.yaml",
            "prometheus/rules/alerting-rules.yaml",
            "prometheus/servicemonitors.yaml",
            "loki/loki-values.yaml",
            "tempo/tempo-values.yaml",
            "grafana/datasources.yaml",
            "grafana/grafana-values.yaml",
            "k8s/namespace.yaml",
            "k8s/external-secrets.yaml",
        ],
    )
    def test_yaml_parses(self, rel):
        # multi-doc files parse via safe_load_all; single via safe_load
        docs = _load_yaml_all(rel)
        assert docs, f"{rel} produced no documents"
        assert all(d is not None for d in docs), f"{rel} has an empty document"

    @pytest.mark.parametrize(
        "rel",
        [
            "grafana/dashboards/provider-pipeline-slo.json",
            "grafana/dashboards/source-health.json",
            "grafana/dashboards/audit-ledger.json",
        ],
    )
    def test_json_parses(self, rel):
        assert _load_json(rel) is not None


# ---------------------------------------------------------------------------
class TestOtelCollector:
    def setup_method(self):
        self.cfg = _load_yaml("otel-collector/collector-config.yaml")

    def test_has_otlp_receiver(self):
        assert "otlp" in self.cfg["receivers"]
        protos = self.cfg["receivers"]["otlp"]["protocols"]
        assert "grpc" in protos and "http" in protos

    def test_three_pipelines(self):
        pipelines = self.cfg["service"]["pipelines"]
        assert {"traces", "metrics", "logs"} <= set(pipelines)

    def test_exporters_present(self):
        exp = self.cfg["exporters"]
        assert "otlp/tempo" in exp
        assert "prometheusremotewrite" in exp
        assert "otlphttp/loki" in exp

    def test_pii_scrub_in_trace_and_log_pipelines(self):
        pipelines = self.cfg["service"]["pipelines"]
        for sig in ("traces", "logs"):
            assert "attributes/scrub_pii" in pipelines[sig]["processors"], (
                f"{sig} pipeline missing PII scrub processor"
            )

    def test_memory_limiter_first(self):
        # memory_limiter must run before batch in every pipeline.
        for sig, p in self.cfg["service"]["pipelines"].items():
            procs = p["processors"]
            assert procs[0] == "memory_limiter", f"{sig}: memory_limiter not first"


# ---------------------------------------------------------------------------
class TestPrometheusRules:
    def setup_method(self):
        self.alerts = _load_yaml("prometheus/rules/alerting-rules.yaml")
        self.recording = _load_yaml("prometheus/rules/recording-rules.yaml")

    def test_required_alert_groups(self):
        names = {g["name"] for g in self.alerts["groups"]}
        assert {"service_slo", "source_health", "audit_ledger", "pipeline"} <= names

    def test_every_alert_well_formed(self):
        for group in self.alerts["groups"]:
            for rule in group["rules"]:
                assert "alert" in rule
                assert "expr" in rule and rule["expr"].strip()
                assert "labels" in rule and "severity" in rule["labels"]
                assert "annotations" in rule
                assert rule["labels"]["severity"] in {"page", "ticket", "info"}

    def test_audit_alerts_are_page_severity(self):
        audit = next(g for g in self.alerts["groups"] if g["name"] == "audit_ledger")
        for rule in audit["rules"]:
            assert rule["labels"]["severity"] == "page", (
                f"{rule['alert']} must page — audit integrity is compliance-critical"
            )

    def test_recording_rules_well_formed(self):
        for group in self.recording["groups"]:
            for rule in group["rules"]:
                assert "record" in rule
                assert ":" in rule["record"], "recording rule must use level:metric:op naming"
                assert rule["expr"].strip()

    def test_alert_exprs_reference_recording_rules(self):
        recorded = {
            rule["record"]
            for g in self.recording["groups"]
            for rule in g["rules"]
        }
        all_alert_expr = " ".join(
            rule["expr"] for g in self.alerts["groups"] for rule in g["rules"]
        )
        # At least the SLO + audit recording rules should be consumed by alerts.
        assert any(rec in all_alert_expr for rec in recorded)


# ---------------------------------------------------------------------------
class TestServiceMonitors:
    def test_covers_all_twelve_services(self):
        docs = _load_yaml_all("prometheus/servicemonitors.yaml")
        sm = next(d for d in docs if d.get("kind") == "ServiceMonitor")
        values = []
        for expr in sm["spec"]["selector"]["matchExpressions"]:
            if expr["key"] == "app.kubernetes.io/part-of":
                values = expr["values"]
        assert set(values) == set(SERVICES), (
            "ServiceMonitor must cover exactly the 12 ECR services"
        )


# ---------------------------------------------------------------------------
class TestGrafana:
    DASHBOARDS = [
        "grafana/dashboards/provider-pipeline-slo.json",
        "grafana/dashboards/source-health.json",
        "grafana/dashboards/audit-ledger.json",
    ]

    @pytest.mark.parametrize("rel", DASHBOARDS)
    def test_dashboard_shape(self, rel):
        d = _load_json(rel)
        assert d["uid"]
        assert d["title"]
        assert isinstance(d["panels"], list) and d["panels"]

    @pytest.mark.parametrize("rel", DASHBOARDS)
    def test_panels_have_targets(self, rel):
        d = _load_json(rel)
        for panel in d["panels"]:
            assert panel.get("targets"), f"{rel}: panel '{panel.get('title')}' has no targets"
            for t in panel["targets"]:
                assert t["expr"].strip()

    def test_datasources_present(self):
        ds = _load_yaml("grafana/datasources.yaml")
        types = {d["type"] for d in ds["datasources"]}
        assert {"prometheus", "loki", "tempo"} <= types

    def test_unique_dashboard_uids(self):
        uids = [_load_json(rel)["uid"] for rel in self.DASHBOARDS]
        assert len(uids) == len(set(uids))


# ---------------------------------------------------------------------------
class TestSentry:
    def test_init_sentry_disabled_without_dsn(self, monkeypatch):
        import sys

        sys.path.insert(0, str(OBS.parents[0]))  # src/
        from observability.sentry.sentry_config import init_sentry

        monkeypatch.delenv("SENTRY_DSN", raising=False)
        assert init_sentry("api-gateway") is False

    def test_scrub_removes_pii_keys_and_patterns(self):
        from observability.sentry.sentry_config import _scrub

        event = {
            "user": {"email": "jane@example.com", "ssn": "123-45-6789", "id": 7},
            "extra": {"note": "contact bob@test.org or 987-65-4321"},
            "tags": ["ok"],
        }
        cleaned = _scrub(event)
        assert cleaned["user"]["email"] == "[redacted]"
        assert cleaned["user"]["ssn"] == "[redacted]"
        assert cleaned["user"]["id"] == 7  # non-PII preserved
        assert "bob@test.org" not in cleaned["extra"]["note"]
        assert "987-65-4321" not in cleaned["extra"]["note"]


# ---------------------------------------------------------------------------
class TestNoSecretsOrStalePlaceholders:
    """No embedded secrets; PLACEHOLDERs only where account-resolution is pending."""

    ALL_FILES = list(OBS.rglob("*.yaml")) + list(OBS.rglob("*.json")) + list(
        OBS.rglob("*.py")
    )

    def test_no_hardcoded_sentry_dsn(self):
        dsn_re = re.compile(r"https://[0-9a-f]+@[\w.-]+/\d+")  # sentry DSN shape
        for f in self.ALL_FILES:
            assert not dsn_re.search(f.read_text()), f"possible hardcoded DSN in {f}"

    def test_no_aws_access_keys(self):
        akid = re.compile(r"AKIA[0-9A-Z]{16}")
        for f in self.ALL_FILES:
            assert not akid.search(f.read_text()), f"possible AWS key in {f}"

    def test_s3_backends_use_placeholder(self):
        # Loki/Tempo buckets must stay PLACEHOLDER until Entry 003 resolves.
        assert "PLACEHOLDER-LOKI-BUCKET" in (OBS / "loki/loki-values.yaml").read_text()
        assert "PLACEHOLDER-TEMPO-BUCKET" in (OBS / "tempo/tempo-values.yaml").read_text()

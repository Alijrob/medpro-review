"""
test_gitops_config.py — Phase 1-E GitOps/ArgoCD config validation.

Unit tests (no mark, no live cluster): verify that every ArgoCD manifest parses,
that Helm charts are pinned to charts-lock.yaml, that value-file and directory
sources point at files that actually exist, that sync waves encode the documented
deploy order, and that the PrometheusRule wrappers stay identical to the Phase 1-D
source rules. Mirrors the Phase 1-C / 1-D test approach.

Run:
    PYTHONPATH=src pytest tests/gitops/ -v
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
GITOPS = ROOT / "src" / "gitops"
APPS = GITOPS / "argocd" / "apps"
OBS = ROOT / "src" / "observability"

GIT_REPO_URL = "https://github.com/Alijrob/medpro-review.git"

# Expected child Application -> sync wave (the documented deploy order).
EXPECTED_WAVES = {
    "external-secrets-operator": 0,
    "observability-namespace": 0,
    "external-secrets-config": 1,
    "kube-prometheus-stack": 2,
    "loki": 3,
    "tempo": 3,
    "service-monitors": 3,
    "prometheus-rules": 3,
    "otel-collector-config": 3,
    "otel-collector-gateway": 4,
    "otel-collector-agent": 4,
    "grafana-config": 4,
    "grafana": 5,
}

# Chart-backed Application name -> charts-lock.yaml key.
APP_CHART_KEY = {
    "external-secrets-operator": "external-secrets",
    "kube-prometheus-stack": "kube-prometheus-stack",
    "loki": "loki",
    "tempo": "tempo-distributed",
    "otel-collector-gateway": "opentelemetry-collector",
    "otel-collector-agent": "opentelemetry-collector",
    "grafana": "grafana",
}


def _load_yaml(path: Path):
    return yaml.safe_load(path.read_text())


def _load_yaml_all(path: Path):
    return [d for d in yaml.safe_load_all(path.read_text()) if d is not None]


def _charts_lock():
    return _load_yaml(GITOPS / "charts-lock.yaml")


def _app(name: str):
    return _load_yaml(APPS / f"{name}.yaml")


def _sources(app: dict):
    spec = app["spec"]
    if "sources" in spec:
        return spec["sources"]
    return [spec["source"]]


def _norm(obj):
    """Recursively whitespace-collapse every string so parity comparison ignores
    YAML formatting (block scalars, indentation) but catches real rule changes."""
    if isinstance(obj, str):
        return " ".join(obj.split())
    if isinstance(obj, list):
        return [_norm(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _norm(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
class TestFilesParse:
    """Every YAML config under src/gitops must parse."""

    @pytest.mark.parametrize("path", sorted(GITOPS.rglob("*.yaml")), ids=lambda p: p.name)
    def test_yaml_parses(self, path):
        docs = _load_yaml_all(path)
        assert docs, f"{path} produced no documents"


# ---------------------------------------------------------------------------
class TestChartsLock:
    def setup_method(self):
        self.lock = _charts_lock()

    def test_has_all_charts(self):
        names = set(self.lock["charts"].keys())
        assert {
            "argo-cd",
            "external-secrets",
            "kube-prometheus-stack",
            "loki",
            "tempo-distributed",
            "grafana",
            "opentelemetry-collector",
        } <= names

    def test_every_chart_pinned(self):
        for name, c in self.lock["charts"].items():
            assert c["repoURL"].startswith("https://"), f"{name} repoURL"
            assert c["chart"], f"{name} chart"
            # A pinned version: digits-and-dots, never 'latest'/'*'/empty.
            ver = str(c["version"])
            assert re.fullmatch(r"\d+\.\d+\.\d+", ver), f"{name} version not pinned: {ver}"

    def test_git_source(self):
        assert self.lock["gitSource"]["repoURL"] == GIT_REPO_URL


# ---------------------------------------------------------------------------
class TestApplicationInventory:
    def test_exactly_the_expected_apps(self):
        on_disk = {p.stem for p in APPS.glob("*.yaml")}
        assert on_disk == set(EXPECTED_WAVES), (
            f"apps/ drift: missing={set(EXPECTED_WAVES) - on_disk} "
            f"extra={on_disk - set(EXPECTED_WAVES)}"
        )

    @pytest.mark.parametrize("name", sorted(EXPECTED_WAVES))
    def test_application_shape(self, name):
        app = _app(name)
        assert app["apiVersion"] == "argoproj.io/v1alpha1"
        assert app["kind"] == "Application"
        assert app["metadata"]["name"] == name
        assert app["metadata"]["namespace"] == "argocd"
        assert app["spec"]["project"] == "platform"
        dest = app["spec"]["destination"]
        assert dest["server"] == "https://kubernetes.default.svc"
        assert dest["namespace"], f"{name} missing destination namespace"

    @pytest.mark.parametrize("name", sorted(EXPECTED_WAVES))
    def test_sync_wave_annotation(self, name):
        app = _app(name)
        ann = app["metadata"].get("annotations", {})
        wave = ann.get("argocd.argoproj.io/sync-wave")
        assert wave is not None, f"{name} missing sync-wave annotation"
        assert int(wave) == EXPECTED_WAVES[name], f"{name} wave {wave} != {EXPECTED_WAVES[name]}"

    @pytest.mark.parametrize("name", sorted(EXPECTED_WAVES))
    def test_automated_sync_policy(self, name):
        app = _app(name)
        assert "automated" in app["spec"]["syncPolicy"], f"{name} not auto-synced"


# ---------------------------------------------------------------------------
class TestChartsPinnedToLock:
    """Every chart-backed Application uses the repoURL/chart/version in the lock."""

    @pytest.mark.parametrize("name", sorted(APP_CHART_KEY))
    def test_chart_matches_lock(self, name):
        lock = _charts_lock()["charts"][APP_CHART_KEY[name]]
        chart_sources = [s for s in _sources(_app(name)) if "chart" in s]
        assert len(chart_sources) == 1, f"{name} should have exactly one chart source"
        src = chart_sources[0]
        assert src["repoURL"] == lock["repoURL"], f"{name} repoURL"
        assert src["chart"] == lock["chart"], f"{name} chart"
        assert str(src["targetRevision"]) == str(lock["version"]), (
            f"{name} targetRevision {src['targetRevision']} != lock {lock['version']}"
        )

    @pytest.mark.parametrize("name", sorted(APP_CHART_KEY))
    def test_no_floating_revisions(self, name):
        for s in _sources(_app(name)):
            if "chart" in s:
                rev = str(s["targetRevision"]).lower()
                assert rev not in {"latest", "*", "", "head"}, f"{name} floating chart revision"


# ---------------------------------------------------------------------------
class TestValueFilesAndSourcesExist:
    """$values valueFiles and directory paths must resolve to real files."""

    @pytest.mark.parametrize("name", sorted(EXPECTED_WAVES))
    def test_helm_value_files_exist(self, name):
        for s in _sources(_app(name)):
            for vf in s.get("helm", {}).get("valueFiles", []):
                assert vf.startswith("$values/"), f"{name}: valueFile must use $values ref: {vf}"
                rel = vf[len("$values/"):]
                assert (ROOT / rel).is_file(), f"{name}: value file missing: {rel}"

    @pytest.mark.parametrize("name", sorted(EXPECTED_WAVES))
    def test_multisource_has_values_ref(self, name):
        srcs = _sources(_app(name))
        # If any source references $values, there must be a git source with ref: values.
        uses_values = any(
            vf.startswith("$values/")
            for s in srcs
            for vf in s.get("helm", {}).get("valueFiles", [])
        )
        if uses_values:
            refs = [s for s in srcs if s.get("ref") == "values"]
            assert len(refs) == 1, f"{name}: missing git source with ref: values"
            assert refs[0]["repoURL"] == GIT_REPO_URL

    @pytest.mark.parametrize("name", sorted(EXPECTED_WAVES))
    def test_directory_sources_exist(self, name):
        for s in _sources(_app(name)):
            if "path" in s and "chart" not in s:
                path = ROOT / s["path"]
                assert path.is_dir(), f"{name}: source path missing: {s['path']}"
                include = s.get("directory", {}).get("include")
                if include and not any(ch in include for ch in "*?{["):
                    assert (path / include).is_file(), (
                        f"{name}: directory.include file missing: {s['path']}/{include}"
                    )


# ---------------------------------------------------------------------------
class TestSyncWaveOrdering:
    """Dependency invariants between waves."""

    def test_eso_before_external_secrets(self):
        assert EXPECTED_WAVES["external-secrets-operator"] < EXPECTED_WAVES["external-secrets-config"]

    def test_namespace_before_secrets(self):
        assert EXPECTED_WAVES["observability-namespace"] < EXPECTED_WAVES["external-secrets-config"]

    def test_prometheus_crds_before_consumers(self):
        kps = EXPECTED_WAVES["kube-prometheus-stack"]
        for consumer in ("service-monitors", "prometheus-rules", "loki", "tempo"):
            assert kps < EXPECTED_WAVES[consumer], f"{consumer} must be after kube-prometheus-stack"

    def test_otel_config_before_gateway(self):
        assert EXPECTED_WAVES["otel-collector-config"] <= EXPECTED_WAVES["otel-collector-gateway"]

    def test_grafana_config_before_grafana(self):
        assert EXPECTED_WAVES["grafana-config"] <= EXPECTED_WAVES["grafana"]

    def test_grafana_is_last(self):
        assert EXPECTED_WAVES["grafana"] == max(EXPECTED_WAVES.values())


# ---------------------------------------------------------------------------
class TestRootAppAndProject:
    def test_root_app_is_app_of_apps(self):
        root = _load_yaml(GITOPS / "argocd" / "bootstrap" / "root-app.yaml")
        assert root["kind"] == "Application"
        assert root["spec"]["project"] == "platform"
        src = root["spec"]["source"]
        assert src["repoURL"] == GIT_REPO_URL
        assert src["path"] == "src/gitops/argocd/apps"

    def test_root_app_points_at_real_dir(self):
        root = _load_yaml(GITOPS / "argocd" / "bootstrap" / "root-app.yaml")
        assert (ROOT / root["spec"]["source"]["path"]).is_dir()

    def test_project_allows_repo_and_chart_repos(self):
        proj = _load_yaml(GITOPS / "argocd" / "projects" / "platform.yaml")
        assert proj["kind"] == "AppProject"
        allowed = set(proj["spec"]["sourceRepos"])
        assert GIT_REPO_URL in allowed
        lock = _charts_lock()["charts"]
        for c in lock.values():
            assert c["repoURL"] in allowed, f"project missing source repo {c['repoURL']}"

    def test_project_destinations_cover_app_namespaces(self):
        proj = _load_yaml(GITOPS / "argocd" / "projects" / "platform.yaml")
        dest_ns = {d["namespace"] for d in proj["spec"]["destinations"]}
        used_ns = {_app(n)["spec"]["destination"]["namespace"] for n in EXPECTED_WAVES}
        assert used_ns <= dest_ns, f"project destinations missing {used_ns - dest_ns}"


# ---------------------------------------------------------------------------
class TestPrometheusRuleParity:
    """The wrapped PrometheusRule CRDs must match the Phase 1-D source rules."""

    CASES = [
        ("rules/recording-rules.yaml", "recording-prometheusrule.yaml"),
        ("rules/alerting-rules.yaml", "alerting-prometheusrule.yaml"),
    ]

    @pytest.mark.parametrize("src_rel,wrap_rel", CASES)
    def test_wrapper_is_valid_crd(self, src_rel, wrap_rel):
        crd = _load_yaml(GITOPS / "argocd" / "monitoring" / wrap_rel)
        assert crd["apiVersion"] == "monitoring.coreos.com/v1"
        assert crd["kind"] == "PrometheusRule"
        assert crd["spec"]["groups"]

    @pytest.mark.parametrize("src_rel,wrap_rel", CASES)
    def test_groups_match_source(self, src_rel, wrap_rel):
        source = _load_yaml(OBS / "prometheus" / src_rel)["groups"]
        wrapped = _load_yaml(GITOPS / "argocd" / "monitoring" / wrap_rel)["spec"]["groups"]
        assert _norm(wrapped) == _norm(source), (
            f"{wrap_rel} drifted from {src_rel} — edit the 1-D source then mirror it"
        )


# ---------------------------------------------------------------------------
class TestKustomizations:
    """The two kustomize overlays generate their ConfigMaps from real files and
    stay within their own root (no '../'), matching ArgoCD's default restrictor."""

    GRAFANA = OBS / "grafana" / "kustomization.yaml"
    OTEL = OBS / "otel-collector" / "kustomization.yaml"

    def test_kustomizations_exist(self):
        assert self.GRAFANA.is_file()
        assert self.OTEL.is_file()

    @pytest.mark.parametrize("kpath", [GRAFANA, OTEL])
    def test_generator_files_exist_and_local(self, kpath):
        k = _load_yaml(kpath)
        base = kpath.parent
        for gen in k["configMapGenerator"]:
            for f in gen["files"]:
                # "key=path" or "path"
                rel = f.split("=", 1)[1] if "=" in f else f
                assert ".." not in rel, f"{kpath.name}: '{rel}' escapes the kustomize root"
                assert (base / rel).is_file(), f"{kpath.name}: generator file missing: {rel}"

    def test_grafana_labels(self):
        k = _load_yaml(self.GRAFANA)
        labels = {
            lbl
            for gen in k["configMapGenerator"]
            for lbl in gen.get("options", {}).get("labels", {})
        }
        assert {"grafana_datasource", "grafana_dashboard"} <= labels

    def test_otel_generates_pipeline_configmap(self):
        k = _load_yaml(self.OTEL)
        names = {gen["name"] for gen in k["configMapGenerator"]}
        assert "otel-gateway-pipeline" in names


# ---------------------------------------------------------------------------
class TestNoSecrets:
    ALL_FILES = list(GITOPS.rglob("*.yaml")) + list(GITOPS.rglob("*.sh"))

    def test_no_hardcoded_sentry_dsn(self):
        dsn_re = re.compile(r"https://[0-9a-f]+@[\w.-]+/\d+")
        for f in self.ALL_FILES:
            assert not dsn_re.search(f.read_text()), f"possible hardcoded DSN in {f}"

    def test_no_aws_access_keys(self):
        akid = re.compile(r"AKIA[0-9A-Z]{16}")
        for f in self.ALL_FILES:
            assert not akid.search(f.read_text()), f"possible AWS key in {f}"


# ---------------------------------------------------------------------------
class TestWorkloads:
    """Phase 1-G: workloads AppProject, api-gateway child app, deploy bundle."""

    PROJECT = GITOPS / "argocd" / "projects" / "workloads.yaml"
    APP = GITOPS / "argocd" / "workloads" / "api-gateway.yaml"
    ROOT_APP = GITOPS / "argocd" / "bootstrap" / "workloads-root-app.yaml"
    DEPLOY = ROOT / "src" / "backend" / "api_gateway" / "deploy"

    WORKLOAD_NS = {"api-gateway", "identity", "reports", "workers"}

    def test_workloads_project(self):
        p = _load_yaml(self.PROJECT)
        assert p["kind"] == "AppProject"
        assert GIT_REPO_URL in p["spec"]["sourceRepos"]
        dest_ns = {d["namespace"] for d in p["spec"]["destinations"]}
        assert dest_ns == self.WORKLOAD_NS
        # Workloads may only create their own Namespace at cluster scope.
        cluster = p["spec"]["clusterResourceWhitelist"]
        assert cluster == [{"group": "", "kind": "Namespace"}]

    def test_api_gateway_app(self):
        a = _load_yaml(self.APP)
        assert a["kind"] == "Application"
        assert a["spec"]["project"] == "workloads"
        assert a["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"] == "0"
        assert a["spec"]["destination"]["namespace"] == "api-gateway"
        path = ROOT / a["spec"]["source"]["path"]
        assert path.is_dir(), f"api-gateway source path missing: {a['spec']['source']['path']}"

    def test_workloads_root_is_app_of_apps(self):
        r = _load_yaml(self.ROOT_APP)
        assert r["kind"] == "Application"
        # The orchestration object lives in platform; the services run in workloads.
        assert r["spec"]["project"] == "platform"
        assert r["spec"]["source"]["path"] == "src/gitops/argocd/workloads"
        assert (ROOT / r["spec"]["source"]["path"]).is_dir()

    def test_deploy_manifests_parse(self):
        docs = _load_yaml_all(self.DEPLOY / "deployment.yaml")
        dep = next(d for d in docs if d["kind"] == "Deployment")
        assert dep["metadata"]["namespace"] == "api-gateway"
        assert dep["spec"]["template"]["spec"]["serviceAccountName"] == "api-gateway-sa"
        labels = dep["spec"]["template"]["metadata"]["labels"]
        assert labels["app.kubernetes.io/part-of"] == "api-gateway"
        svc = _load_yaml(self.DEPLOY / "service.yaml")
        assert svc["kind"] == "Service"
        port_names = {p["name"] for p in svc["spec"]["ports"]}
        assert "metrics" in port_names  # scraped by the 1-D ServiceMonitor

    def test_deploy_image_is_placeholder(self):
        dep = next(
            d for d in _load_yaml_all(self.DEPLOY / "deployment.yaml") if d["kind"] == "Deployment"
        )
        image = dep["spec"]["template"]["spec"]["containers"][0]["image"]
        assert "PLACEHOLDER" in image, "image must stay PLACEHOLDER until built + Entry 003"

    def test_deploy_kustomization_local(self):
        k = _load_yaml(self.DEPLOY / "kustomization.yaml")
        for r in k["resources"]:
            assert ".." not in r, f"deploy kustomization escapes its root: {r}"
            assert (self.DEPLOY / r).is_file()


# ---------------------------------------------------------------------------
class TestServiceMonitorNamespaceReconciled:
    """DECISIONS.md Entry 011: ServiceMonitor selects the per-group workload
    namespaces, and the api-gateway Deployment lands in one of them."""

    def test_servicemonitor_selects_workload_namespaces(self):
        docs = _load_yaml_all(OBS / "prometheus" / "servicemonitors.yaml")
        sm = next(d for d in docs if d.get("kind") == "ServiceMonitor")
        names = set(sm["spec"]["namespaceSelector"]["matchNames"])
        assert names == {"api-gateway", "identity", "reports", "workers"}
        assert "medpro" not in names

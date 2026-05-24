#!/usr/bin/env bash
# =============================================================================
# gitops-guard.sh — deploy-time PLACEHOLDER guard for the GitOps layer
# =============================================================================
# Phase 1-E. Blocks an ArgoCD deploy while any account-specific value is still a
# PLACEHOLDER (DECISIONS.md Entry 003 — AWS account / region / S3 buckets /
# Secrets Manager paths). Mirrors the infra-validate placeholder-guard, but scans
# the config ArgoCD actually renders: the observability Helm value files and raw
# manifests, plus the Phase 1-E agent values.
#
# Usage (run before `argocd app sync` / before promoting to an environment):
#   scripts/gitops-guard.sh
#
# Exit 0 = no placeholders, safe to sync. Exit 1 = placeholders remain, blocked.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Paths whose contents are pulled into the cluster by the ArgoCD Applications.
SCAN_PATHS=(
  "src/observability"
  "src/gitops/argocd/otel"
)

echo "GitOps placeholder guard: scanning rendered config for PLACEHOLDER values..."

if grep -rln "PLACEHOLDER" "${SCAN_PATHS[@]/#/$ROOT/}" 2>/dev/null; then
  echo ""
  echo "ERROR: PLACEHOLDER values found in deployable GitOps config (listed above)."
  echo "Resolve DECISIONS.md Entry 003 (AWS account / region / S3 buckets /"
  echo "Secrets Manager paths) and replace every PLACEHOLDER before syncing ArgoCD."
  exit 1
fi

echo "OK: no PLACEHOLDER values in deployable GitOps config. Safe to sync."

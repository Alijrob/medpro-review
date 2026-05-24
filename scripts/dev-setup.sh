#!/usr/bin/env bash
# dev-setup.sh — Medical Professionals Review
# Idempotent local development environment setup.
# Run: bash scripts/dev-setup.sh
# Safe to re-run at any time.

set -euo pipefail

echo "=== Medical Professionals Review — Dev Setup ==="

# --- Python ---
if ! command -v python3.11 &>/dev/null; then
  echo "[INFO] Python 3.11 not found. Install via pyenv or your system package manager."
  echo "       pyenv install 3.11 && pyenv local 3.11"
  exit 1
fi
echo "[OK] Python: $(python3.11 --version)"

# --- Poetry ---
if ! command -v poetry &>/dev/null; then
  echo "[INSTALL] Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3 -
fi
echo "[OK] Poetry: $(poetry --version)"

# --- Node.js ---
if ! command -v node &>/dev/null; then
  echo "[INFO] Node.js not found. Install via nvm:"
  echo "       curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
  echo "       nvm install --lts"
  exit 1
fi
echo "[OK] Node: $(node --version)"

# --- AWS CLI ---
if ! command -v aws &>/dev/null; then
  echo "[INFO] AWS CLI not found. Install from: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  echo "[SKIP] AWS CLI — install manually, then re-run."
else
  echo "[OK] AWS CLI: $(aws --version)"
fi

# --- kubectl ---
if ! command -v kubectl &>/dev/null; then
  echo "[SKIP] kubectl not found — install when Kubernetes access is needed (Phase 1-B+)"
else
  echo "[OK] kubectl: $(kubectl version --client --short 2>/dev/null || kubectl version --client)"
fi

# --- helm ---
if ! command -v helm &>/dev/null; then
  echo "[SKIP] helm not found — install when Helm charts are needed (Phase 1-B+)"
else
  echo "[OK] helm: $(helm version --short)"
fi

# --- terragrunt ---
if ! command -v terragrunt &>/dev/null; then
  echo "[SKIP] terragrunt not found — install when IaC work begins (Phase 1-B+)"
else
  echo "[OK] terragrunt: $(terragrunt --version)"
fi

# --- direnv ---
if ! command -v direnv &>/dev/null; then
  echo "[INFO] direnv not found. Install via: brew install direnv (macOS) or apt install direnv (Linux)"
  echo "[SKIP] direnv"
else
  echo "[OK] direnv: $(direnv --version)"
fi

echo ""
echo "=== Setup complete ==="
echo "Backend:  make run-backend   (available from Phase 1-F)"
echo "Frontend: make run-frontend  (available from Phase 2-K)"
echo "Tests:    make test"
echo "Lint:     make lint"

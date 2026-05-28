#!/usr/bin/env bash
# pm2-start.sh -- Manage PM2 processes for medpro-review on Hostinger.
#
# Loads .env.hostinger, optionally builds the Next.js frontend, then
# delegates to PM2 using ecosystem.config.js.
#
# Usage:
#   bash scripts/pm2-start.sh start     # build frontend + start all processes
#   bash scripts/pm2-start.sh restart   # reload env + restart all processes
#   bash scripts/pm2-start.sh stop      # stop all processes
#   bash scripts/pm2-start.sh status    # pm2 status
#   bash scripts/pm2-start.sh logs      # stream all logs
#   bash scripts/pm2-start.sh health    # curl /healthz on every backend service
#
# One-time setup (run once after deploy):
#   pm2 startup                         # install PM2 as a systemd service
#   bash scripts/pm2-start.sh start
#   pm2 save                            # persist process list across reboots

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env.hostinger"
ECOSYSTEM="$REPO_ROOT/ecosystem.config.js"
FRONTEND_DIR="$REPO_ROOT/src/frontend"

CMD="${1:-start}"

# ---------------------------------------------------------------------------
# Load .env.hostinger for commands that need it
# ---------------------------------------------------------------------------
load_env() {
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found." >&2
    echo "       Copy .env.hostinger.example, fill in values, then retry." >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  echo "[pm2-start] Loaded $ENV_FILE"
}

# ---------------------------------------------------------------------------
# Build Next.js frontend (required before first `npm run start`)
# ---------------------------------------------------------------------------
build_frontend() {
  echo "[pm2-start] Building Next.js frontend..."
  (
    cd "$FRONTEND_DIR"
    # Pass Auth0 + app URL vars so the build can embed NEXT_PUBLIC_* values.
    NEXT_PUBLIC_APP_URL="${NEXT_PUBLIC_APP_URL:-https://researchyourdoctor.com}" \
      npm run build
  )
  echo "[pm2-start] Frontend build complete."
}

# ---------------------------------------------------------------------------
# Smoke-check all backend /healthz endpoints
# ---------------------------------------------------------------------------
run_health() {
  local -A SERVICES=(
    ["auth-service"]="8000"
    ["api-gateway"]="8080"
    ["audit-service"]="8001"
    ["source-monitor"]="8002"
    ["search-service"]="8003"
    ["report-service"]="8004"
    ["payment-service"]="8005"
  )
  local ok=0 fail=0
  for name in "${!SERVICES[@]}"; do
    port="${SERVICES[$name]}"
    status=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 \
      "http://127.0.0.1:${port}/healthz" 2>/dev/null || echo "000")
    if [[ "$status" == "200" ]]; then
      echo "  OK  $name :$port"
      ((ok++)) || true
    else
      echo "  FAIL $name :$port  (HTTP $status)"
      ((fail++)) || true
    fi
  done
  echo "---"
  echo "$ok OK / $fail FAIL"
  [[ $fail -eq 0 ]]
}

# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------
case "$CMD" in
  start)
    load_env
    build_frontend
    echo "[pm2-start] Starting all processes..."
    pm2 start "$ECOSYSTEM"
    pm2 save
    echo ""
    echo "[pm2-start] All processes started. Run 'pm2 status' to verify."
    echo "            First-time setup: run 'pm2 startup' to persist across reboots."
    ;;

  restart)
    load_env
    echo "[pm2-start] Restarting all processes..."
    # Delete existing processes and re-register so updated env vars take effect.
    pm2 delete all 2>/dev/null || true
    pm2 start "$ECOSYSTEM"
    pm2 save
    echo "[pm2-start] Restart complete."
    ;;

  stop)
    pm2 stop all
    ;;

  status)
    pm2 status
    ;;

  logs)
    pm2 logs
    ;;

  health)
    run_health
    ;;

  *)
    echo "Usage: $0 {start|restart|stop|status|logs|health}" >&2
    exit 1
    ;;
esac

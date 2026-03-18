#!/usr/bin/env bash
# start.sh — Native shell startup for opencli-admin (no Docker required)
# Reuses the native opencli and Chrome/Chromium already installed on the system.
#
# Usage:
#   ./start.sh                   # start all: Chrome + backend + frontend
#   ./start.sh --no-chrome       # skip Chrome (if CDP not needed)
#   ./start.sh --no-frontend     # skip Vite dev server
#   ./start.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors ────────────────────────────────────────────────────────────────────
_blue='\033[0;34m'; _green='\033[0;32m'; _yellow='\033[1;33m'; _red='\033[0;31m'; _nc='\033[0m'
info() { echo -e "${_blue}[info]${_nc}  $*"; }
ok()   { echo -e "${_green}[ ok]${_nc}  $*"; }
warn() { echo -e "${_yellow}[warn]${_nc}  $*"; }
die()  { echo -e "${_red}[err]${_nc}  $*" >&2; exit 1; }

# ── PID tracking ──────────────────────────────────────────────────────────────
PIDS=()
cleanup() {
  echo ""
  info "Stopping all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  ok "Stopped."
}
trap cleanup SIGINT SIGTERM

# ── Options (parsed early for --help; ports resolved after .env load) ─────────
SKIP_CHROME=false
SKIP_FRONTEND=false
_ARG_API_PORT=""
_ARG_FRONTEND_PORT=""
_ARG_CDP_PORT=""
CHROME_PROFILE="${HOME}/.opencli-admin/chrome-profile"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-chrome)     SKIP_CHROME=true ;;
    --no-frontend)   SKIP_FRONTEND=true ;;
    --api-port)      _ARG_API_PORT="$2"; shift ;;
    --frontend-port) _ARG_FRONTEND_PORT="$2"; shift ;;
    --cdp-port)      _ARG_CDP_PORT="$2"; shift ;;
    -h|--help)
      echo "Usage: $0 [--no-chrome] [--no-frontend] [--api-port N] [--frontend-port N] [--cdp-port N]"
      exit 0 ;;
    *) die "Unknown option: $1" ;;
  esac
  shift
done

echo ""
echo "┌─────────────────────────────────────┐"
echo "│      opencli-admin  (native)        │"
echo "└─────────────────────────────────────┘"
echo ""

# ── Load .env ─────────────────────────────────────────────────────────────────
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  ok ".env loaded"
fi

# Priority: CLI arg > .env > hardcoded default
API_PORT="${_ARG_API_PORT:-${API_PORT:-8031}}"
FRONTEND_PORT="${_ARG_FRONTEND_PORT:-${FRONTEND_PORT:-8030}}"
CDP_PORT="${_ARG_CDP_PORT:-${CDP_PORT:-9222}}"

# ── Check Python ──────────────────────────────────────────────────────────────
PYTHON="${PYTHON:-python3}"
"$PYTHON" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" \
  || die "Python 3.11+ required (found: $("$PYTHON" --version 2>&1))"
ok "Python $("$PYTHON" --version)"

# ── Create/activate venv ──────────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  info "Creating Python virtual environment (.venv)..."
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
# Ensure pip is available (may be absent on some distros)
if ! python -m pip --version &>/dev/null 2>&1; then
  info "pip not found, installing via ensurepip..."
  python -m ensurepip --upgrade
fi
ok "venv active"

# ── Install Python deps ───────────────────────────────────────────────────────
info "Checking backend dependencies..."
python -m pip install -q -e . 2>&1 | tail -1
ok "Backend deps ready"

# ── Check opencli ─────────────────────────────────────────────────────────────
if command -v opencli &>/dev/null; then
  ok "opencli: $(opencli --version 2>/dev/null | head -1 || echo 'found')"
else
  warn "opencli not found — opencli channel will be unavailable"
  warn "  Install: npm install -g @jackwener/opencli"
fi

# ── Find Chrome binary ────────────────────────────────────────────────────────
find_chrome() {
  local candidates=(
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
    "$(command -v google-chrome-stable 2>/dev/null)"
    "$(command -v google-chrome 2>/dev/null)"
    "$(command -v chromium 2>/dev/null)"
    "$(command -v chromium-browser 2>/dev/null)"
  )
  for c in "${candidates[@]}"; do
    [[ -n "$c" && ( -f "$c" || -x "$c" ) ]] && { echo "$c"; return 0; }
  done
  return 1
}

# ── Start Chrome in CDP mode (with auto-restart loop) ────────────────────────
CHROME_PID=""
if [[ "$SKIP_CHROME" == false ]]; then
  if CHROME_BIN="$(find_chrome)"; then
    mkdir -p "$CHROME_PROFILE"
    info "Starting Chrome (CDP :$CDP_PORT)  profile: $CHROME_PROFILE"
    # Wrap in a restart loop — Chrome may exit on its own (e.g. after idle)
    (
      trap 'kill $(jobs -p) 2>/dev/null; exit' TERM INT
      while true; do
        "$CHROME_BIN" \
          --remote-debugging-port="$CDP_PORT" \
          --remote-debugging-address=127.0.0.1 \
          --remote-allow-origins='*' \
          --user-data-dir="$CHROME_PROFILE" \
          --no-first-run \
          --no-default-browser-check \
          --window-size=1280,900 \
          about:blank &>/dev/null
        sleep 2
      done
    ) &
    CHROME_PID=$!
    PIDS+=("$CHROME_PID")
    sleep 1
    if kill -0 "$CHROME_PID" 2>/dev/null; then
      ok "Chrome started (pid $CHROME_PID)"
      export OPENCLI_CDP_ENDPOINT="http://127.0.0.1:$CDP_PORT"
    else
      warn "Chrome failed to start — opencli channel may not work"
      CHROME_PID=""
    fi
  else
    warn "Chrome/Chromium not found — skipping CDP browser"
    warn "  macOS: install Google Chrome or Chromium"
    warn "  Linux: apt install chromium-browser"
  fi
fi

# Export CDP endpoint for the backend (falls back to default if Chrome not started)
export OPENCLI_CDP_ENDPOINT="${OPENCLI_CDP_ENDPOINT:-http://127.0.0.1:$CDP_PORT}"

# ── Start backend API ─────────────────────────────────────────────────────────
info "Starting backend API on http://localhost:$API_PORT ..."
uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "$API_PORT" \
  --reload \
  --reload-dir backend \
  &
PIDS+=($!)
ok "Backend API started"

# ── Start frontend dev server ──────────────────────────────────────────────────
if [[ "$SKIP_FRONTEND" == false ]]; then
  if ! command -v node &>/dev/null; then
    warn "Node.js not found — skipping frontend dev server"
    warn "  Install Node.js 18+ from https://nodejs.org"
  else
    info "Installing frontend dependencies..."
    (cd frontend && npm install -q --legacy-peer-deps 2>&1 | tail -1)
    info "Starting frontend dev server on http://localhost:$FRONTEND_PORT ..."
    # VITE_API_PROXY_TARGET tells vite.config.ts where to proxy /api requests
    (cd frontend && VITE_API_PROXY_TARGET="http://localhost:$API_PORT" \
      npm run dev -- --host --port "$FRONTEND_PORT") &
    PIDS+=($!)
    ok "Frontend dev server started"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "  管理界面   →   http://localhost:$FRONTEND_PORT"
echo "  API 文档   →   http://localhost:$API_PORT/docs"
if [[ -n "$CHROME_PID" ]]; then
  echo ""
  echo "  Chrome 已在后台启动，请打开需要采集的平台网址并登录账号。"
  echo "  登录状态持久保存在: $CHROME_PROFILE"
fi
echo ""
echo "  按 Ctrl+C 停止所有服务"
echo ""

# ── Wait for all background processes ────────────────────────────────────────
wait

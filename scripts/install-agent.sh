#!/usr/bin/env bash
# install-agent.sh — Install and start the OpenCLI Agent on a remote node.
#
# This script is served dynamically by the center API at:
#   GET /api/v1/nodes/install/agent.sh
# The center pre-fills CENTRAL_API_URL so you can install with one command:
#   curl -fsSL http://<center>:8031/api/v1/nodes/install/agent.sh | bash
#
# Manual usage:
#   CENTRAL_API_URL=http://192.168.1.1:8031 bash install-agent.sh [docker|python] [--install-chrome]
#
# Environment variables (override at runtime):
#   CENTRAL_API_URL    Center API base URL (required)
#   AGENT_REGISTER     Registration mode: http | ws (default: ws)
#   AGENT_PORT         Agent HTTP port (default: 19823)
#   AGENT_LABEL        Human-readable label (default: hostname)
#   AGENT_MODE         Chrome connection mode: cdp | bridge (default: cdp)
#   INSTALL_CHROME     Embed Chromium in Docker image: true | false (default: false)
#                      true  → uses image tag suffix "-chrome" (~450 MB, self-contained)
#                      false → uses base image (~100 MB), connect to host Chrome via CDP
#   HTTP_PROXY         HTTP proxy for agent → center (optional)
#   HTTPS_PROXY        HTTPS proxy for agent → center (optional)
#   IMAGE_TAG          Docker image tag (default: injected by center API)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Injected by center API ────────────────────────────────────────────────────
CENTRAL_API_URL="${CENTRAL_API_URL:-__CENTRAL_API_URL__}"

# ── Defaults ──────────────────────────────────────────────────────────────────
AGENT_REGISTER="${AGENT_REGISTER:-ws}"
AGENT_PORT="${AGENT_PORT:-19823}"
AGENT_LABEL="${AGENT_LABEL:-$(hostname)}"
AGENT_MODE="${AGENT_MODE:-cdp}"
IMAGE_TAG="${IMAGE_TAG:-__IMAGE_TAG__}"
INSTALL_CHROME="${INSTALL_CHROME:-false}"
INSTALL_MODE="${1:-docker}"

# Parse --install-chrome flag from any positional argument
for arg in "$@"; do
  case "$arg" in
    --install-chrome) INSTALL_CHROME=true ;;
    --no-chrome)      INSTALL_CHROME=false ;;
  esac
done

# Select image tag suffix based on Chrome preference
if [[ "$INSTALL_CHROME" == "true" ]]; then
  CHROME_SUFFIX="-chrome"
else
  CHROME_SUFFIX=""
fi
AGENT_IMAGE="xjh1994/opencli-admin-agent:${IMAGE_TAG}${CHROME_SUFFIX}"

# ─────────────────────────────────────────────────────────────────────────────

info()  { printf '\e[32m[INFO]\e[0m  %s\n' "$*"; }
warn()  { printf '\e[33m[WARN]\e[0m  %s\n' "$*"; }
die()   { printf '\e[31m[ERROR]\e[0m %s\n' "$*" >&2; exit 1; }

[[ -z "$CENTRAL_API_URL" ]] && die "CENTRAL_API_URL is required"

info "OpenCLI Agent Installer"
info "  Center:         $CENTRAL_API_URL"
info "  Register:       $AGENT_REGISTER"
info "  Port:           $AGENT_PORT"
info "  Label:          $AGENT_LABEL"
info "  Mode:           $INSTALL_MODE"
info "  Agent Mode:     $AGENT_MODE"
info "  Install Chrome: $INSTALL_CHROME"
info "  Image:          $AGENT_IMAGE"
echo

# ── Docker install ─────────────────────────────────────────────────────────────
install_docker() {
  command -v docker >/dev/null 2>&1 || die "Docker is not installed. Visit https://docs.docker.com/get-docker/"

  CONTAINER_NAME="opencli-agent"

  # Stop and remove existing container with same name
  if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    warn "Existing container '$CONTAINER_NAME' found — removing..."
    docker rm -f "$CONTAINER_NAME" >/dev/null
  fi

  # Auto-find a free port starting from AGENT_PORT
  ORIG_PORT="$AGENT_PORT"
  while docker ps --format '{{.Ports}}' | grep -q "0.0.0.0:${AGENT_PORT}->"; do
    AGENT_PORT=$(( AGENT_PORT + 1 ))
  done
  [[ "$AGENT_PORT" != "$ORIG_PORT" ]] && warn "Port $ORIG_PORT in use, using $AGENT_PORT instead"

  # Inside Docker, 'localhost'/'127.0.0.1' refers to the container itself, not the host.
  # Translate to host.docker.internal (works on Docker Desktop + Linux with --add-host).
  DOCKER_CENTRAL_URL=$(echo "$CENTRAL_API_URL" | sed 's|localhost|host.docker.internal|g; s|127\.0\.0\.1|host.docker.internal|g')
  [[ "$DOCKER_CENTRAL_URL" != "$CENTRAL_API_URL" ]] && warn "Docker networking: using $DOCKER_CENTRAL_URL inside container"

  PROXY_ARGS=""
  [[ -n "${HTTP_PROXY:-}" ]]  && PROXY_ARGS="$PROXY_ARGS -e HTTP_PROXY=$HTTP_PROXY"
  [[ -n "${HTTPS_PROXY:-}" ]] && PROXY_ARGS="$PROXY_ARGS -e HTTPS_PROXY=$HTTPS_PROXY"

  info "Starting container '$CONTAINER_NAME'..."
  # shellcheck disable=SC2086
  # --add-host makes host.docker.internal work on Linux (no-op on Docker Desktop)
  docker run -d \
    --name "$CONTAINER_NAME" \
    --restart unless-stopped \
    --add-host=host.docker.internal:host-gateway \
    -e CENTRAL_API_URL="$DOCKER_CENTRAL_URL" \
    -e AGENT_REGISTER="$AGENT_REGISTER" \
    -e AGENT_PORT="$AGENT_PORT" \
    -e AGENT_LABEL="$AGENT_LABEL" \
    -e AGENT_MODE="${AGENT_MODE}" \
    -e AGENT_DEPLOY_TYPE="docker" \
    $PROXY_ARGS \
    -p "${AGENT_PORT}:${AGENT_PORT}" \
    "$AGENT_IMAGE"

  info "Container started. Waiting for registration..."
  sleep 3
  if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
    info "Agent is running!"
  else
    die "Container failed to start. Check: docker logs $CONTAINER_NAME"
  fi
}

# ── Python/pip install ─────────────────────────────────────────────────────────
install_python() {
  command -v python3 >/dev/null 2>&1 || die "Python 3 is not installed"

  AGENT_DIR="$HOME/.opencli-agent"
  mkdir -p "$AGENT_DIR/backend"

  # ── Download agent_server.py from center ──────────────────────────────────
  info "Downloading agent_server.py from center..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$CENTRAL_API_URL/api/v1/nodes/install/agent_server.py" \
      -o "$AGENT_DIR/backend/agent_server.py"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$AGENT_DIR/backend/agent_server.py" \
      "$CENTRAL_API_URL/api/v1/nodes/install/agent_server.py"
  else
    die "Neither curl nor wget found — cannot download agent_server.py"
  fi
  touch "$AGENT_DIR/backend/__init__.py"

  # ── Install Python dependencies ───────────────────────────────────────────
  info "Installing Python dependencies..."
  VENV_DIR="$AGENT_DIR/venv"
  if python3 -m venv "$VENV_DIR" 2>/dev/null; then
    "$VENV_DIR/bin/pip" install --quiet fastapi "uvicorn[standard]" httpx pyyaml websockets
    UVICORN_BIN="$VENV_DIR/bin/uvicorn"
    info "Installed into virtualenv: $VENV_DIR"
  elif python3 -m pip install --user --quiet fastapi "uvicorn[standard]" httpx pyyaml websockets 2>/dev/null; then
    UVICORN_BIN="uvicorn"
  else
    die "Could not install Python dependencies. Try: python3 -m venv ~/.opencli-agent/venv && source ~/.opencli-agent/venv/bin/activate && pip install fastapi 'uvicorn[standard]' httpx pyyaml websockets"
  fi

  # ── Check / install opencli ───────────────────────────────────────────────
  if command -v opencli >/dev/null 2>&1; then
    info "opencli: $(opencli --version 2>/dev/null | head -1 || echo 'found')"
  elif command -v npm >/dev/null 2>&1; then
    if [ -t 0 ]; then
      read -r -p "opencli not found. Install now via npm? [Y/n] " _reply </dev/tty || _reply="Y"
    else
      _reply="Y"
      info "opencli not found — installing via npm (non-interactive)..."
    fi
    if [[ "${_reply:-Y}" =~ ^[Yy]$ ]]; then
      npm install -g @jackwener/opencli
      info "opencli: $(opencli --version 2>/dev/null | head -1 || echo 'installed')"
    else
      warn "Skipped — opencli channel will be unavailable"
    fi
  else
    warn "npm not found — opencli channel will be unavailable"
    warn "  Install Node.js from https://nodejs.org then run: npm install -g @jackwener/opencli"
  fi

  # ── Find Chrome binary ────────────────────────────────────────────────────
  find_chrome() {
    local candidates=(
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
      "/Applications/Chromium.app/Contents/MacOS/Chromium"
      "$(command -v google-chrome-stable 2>/dev/null || true)"
      "$(command -v google-chrome 2>/dev/null || true)"
      "$(command -v chromium 2>/dev/null || true)"
      "$(command -v chromium-browser 2>/dev/null || true)"
    )
    for c in "${candidates[@]}"; do
      [[ -n "$c" && ( -f "$c" || -x "$c" ) ]] && { echo "$c"; return 0; }
    done
    return 1
  }

  # ── Start Chrome in CDP mode ──────────────────────────────────────────────
  CDP_PORT="${CDP_PORT:-9222}"
  CHROME_PROFILE="$AGENT_DIR/chrome-profile"

  if [[ "${AGENT_MODE}" == "cdp" ]]; then
    if CHROME_BIN="$(find_chrome)"; then
      mkdir -p "$CHROME_PROFILE"
      CHROME_LOG="/tmp/opencli-chrome.log"
      # Remove stale profile locks left by previous crashes
      find "$CHROME_PROFILE" -name 'SingletonLock' -o -name 'SingletonCookie' -o -name 'SingletonSocket' \
        2>/dev/null | xargs rm -f 2>/dev/null || true
      CHROME_EXTRA_FLAGS=()
      if [[ "$(id -u)" == "0" ]]; then
        CHROME_EXTRA_FLAGS+=("--no-sandbox")
      fi
      if [[ -z "${DISPLAY:-}" ]]; then
        CHROME_EXTRA_FLAGS+=("--headless=new" "--disable-gpu")
      fi
      info "Starting Chrome (CDP :$CDP_PORT)  profile: $CHROME_PROFILE"
      nohup "$CHROME_BIN" \
        --remote-debugging-port="$CDP_PORT" \
        --remote-debugging-address=127.0.0.1 \
        --remote-allow-origins='*' \
        --user-data-dir="$CHROME_PROFILE" \
        --no-first-run \
        --no-default-browser-check \
        --window-size=1280,900 \
        "${CHROME_EXTRA_FLAGS[@]}" \
        about:blank >"$CHROME_LOG" 2>&1 &
      CHROME_PID=$!
      sleep 1
      if kill -0 "$CHROME_PID" 2>/dev/null; then
        info "Chrome started (pid $CHROME_PID)  log: $CHROME_LOG"
        export OPENCLI_CDP_ENDPOINT="http://127.0.0.1:$CDP_PORT"
      else
        warn "Chrome failed to start — see $CHROME_LOG"
      fi
    else
      warn "Chrome/Chromium not found — CDP mode may fail"
      warn "  macOS: install Google Chrome or Chromium"
      warn "  Linux: apt install chromium-browser"
    fi
    export OPENCLI_CDP_ENDPOINT="${OPENCLI_CDP_ENDPOINT:-http://127.0.0.1:$CDP_PORT}"
  fi

  # ── Launch agent server ───────────────────────────────────────────────────
  AGENT_CMD="$UVICORN_BIN backend.agent_server:app --host 0.0.0.0 --port ${AGENT_PORT}"
  SYSTEMD_UNIT="/etc/systemd/system/opencli-agent.service"

  if command -v systemctl >/dev/null 2>&1 && [[ -w /etc/systemd/system ]]; then
    info "Installing systemd service..."
    cat > "$SYSTEMD_UNIT" <<EOF
[Unit]
Description=OpenCLI Agent Server
After=network.target

[Service]
Type=simple
WorkingDirectory=${AGENT_DIR}
Restart=on-failure
RestartSec=5
Environment=CENTRAL_API_URL=${CENTRAL_API_URL}
Environment=AGENT_REGISTER=${AGENT_REGISTER}
Environment=AGENT_PORT=${AGENT_PORT}
Environment=AGENT_LABEL=${AGENT_LABEL}
Environment=AGENT_MODE=${AGENT_MODE}
Environment=AGENT_DEPLOY_TYPE=shell
$([ -n "${OPENCLI_CDP_ENDPOINT:-}" ] && echo "Environment=OPENCLI_CDP_ENDPOINT=${OPENCLI_CDP_ENDPOINT}")
$([ -n "${HTTP_PROXY:-}" ]  && echo "Environment=HTTP_PROXY=${HTTP_PROXY}")
$([ -n "${HTTPS_PROXY:-}" ] && echo "Environment=HTTPS_PROXY=${HTTPS_PROXY}")
ExecStart=${AGENT_CMD}

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now opencli-agent
    info "Service enabled and started (systemctl status opencli-agent)"
  else
    info "Starting agent in background (no systemd)..."
    (
      cd "$AGENT_DIR"
      export CENTRAL_API_URL AGENT_REGISTER AGENT_PORT AGENT_LABEL AGENT_MODE
      export AGENT_DEPLOY_TYPE=shell
      [[ -n "${OPENCLI_CDP_ENDPOINT:-}" ]] && export OPENCLI_CDP_ENDPOINT
      [[ -n "${HTTP_PROXY:-}" ]]  && export HTTP_PROXY
      [[ -n "${HTTPS_PROXY:-}" ]] && export HTTPS_PROXY
      # shellcheck disable=SC2086
      nohup $AGENT_CMD > /tmp/opencli-agent.log 2>&1 &
      echo $! > /tmp/opencli-agent.pid
    )
    info "Agent started (PID=$(cat /tmp/opencli-agent.pid 2>/dev/null || echo '?')). Logs: /tmp/opencli-agent.log"
  fi
}

# ── Dispatch ───────────────────────────────────────────────────────────────────
case "$INSTALL_MODE" in
  docker) install_docker ;;
  python) install_python ;;
  *)      die "Unknown install mode '$INSTALL_MODE'. Usage: $0 [docker|python]" ;;
esac

echo
info "Done! The agent will register itself at: $CENTRAL_API_URL"
info "View registered nodes at: $CENTRAL_API_URL → 节点管理"

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
#   INSTALL_CHROME     Embed Chromium in container: true | false (default: false)
#                      true  → uses image tag suffix "-chrome" (~1.2 GB, self-contained)
#                      false → uses base image (~200 MB), connect to host Chrome via CDP
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
info "  Center:        $CENTRAL_API_URL"
info "  Register:      $AGENT_REGISTER"
info "  Port:          $AGENT_PORT"
info "  Label:         $AGENT_LABEL"
info "  Mode:          $INSTALL_MODE"
info "  Install Chrome: $INSTALL_CHROME"
info "  Image:         $AGENT_IMAGE"
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
    -e AGENT_MODE="cdp" \
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

  info "Installing Python dependencies..."
  # Try pip with --user first; fall back to creating a venv if pip is unavailable or restricted
  VENV_DIR="$HOME/.opencli-agent-venv"
  if python3 -m pip install --user --quiet fastapi uvicorn httpx pyyaml websockets 2>/dev/null; then
    PYTHON_BIN="python3"
  elif python3 -m venv "$VENV_DIR" 2>/dev/null && "$VENV_DIR/bin/pip" install --quiet fastapi uvicorn httpx pyyaml websockets; then
    PYTHON_BIN="$VENV_DIR/bin/python3"
    info "Installed into virtualenv: $VENV_DIR"
  else
    die "Could not install Python dependencies. Try: python3 -m venv ~/.opencli-agent-venv && source ~/.opencli-agent-venv/bin/activate && pip install fastapi uvicorn httpx pyyaml websockets"
  fi

  SYSTEMD_UNIT="/etc/systemd/system/opencli-agent.service"
  AGENT_CMD="$PYTHON_BIN -m backend.agent_server"

  if command -v systemctl >/dev/null 2>&1 && [[ -w /etc/systemd/system ]]; then
    info "Installing systemd service..."
    cat > "$SYSTEMD_UNIT" <<EOF
[Unit]
Description=OpenCLI Agent Server
After=network.target

[Service]
Type=simple
Restart=on-failure
RestartSec=5
Environment=CENTRAL_API_URL=${CENTRAL_API_URL}
Environment=AGENT_REGISTER=${AGENT_REGISTER}
Environment=AGENT_PORT=${AGENT_PORT}
Environment=AGENT_LABEL=${AGENT_LABEL}
Environment=AGENT_MODE=cdp
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
    CENTRAL_API_URL="$CENTRAL_API_URL" \
    AGENT_REGISTER="$AGENT_REGISTER" \
    AGENT_PORT="$AGENT_PORT" \
    AGENT_LABEL="$AGENT_LABEL" \
    AGENT_MODE="cdp" \
    nohup $AGENT_CMD > /tmp/opencli-agent.log 2>&1 &
    info "Agent started (PID=$!). Logs: /tmp/opencli-agent.log"
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

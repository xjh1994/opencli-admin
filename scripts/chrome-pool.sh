#!/usr/bin/env bash
# chrome-pool.sh — Dynamically manage Chrome browser pool instances.
#
# Usage:
#   ./scripts/chrome-pool.sh start [N]   Start N Chrome instances (default: 3)
#   ./scripts/chrome-pool.sh stop        Stop all extra instances (keeps instance 1)
#   ./scripts/chrome-pool.sh status      Show running instances + endpoints
#   ./scripts/chrome-pool.sh endpoints   Print CHROME_POOL_ENDPOINTS value only
#
# After running "start N", copy the printed CHROME_POOL_ENDPOINTS line into .env
# so the API picks up all instances on next restart.
#
# Each extra instance (2..N) gets:
#   - Container name:  chrome-{N}           (Docker DNS name within network)
#   - noVNC port:      NOVNC_BASE + (N-1)   (default: 3011, 3012, ...)
#   - Profile volume:  {project}_chrome_profile_{N}
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Project / image / network detection ──────────────────────────────────────

get_project_name() {
  cd "$PROJECT_DIR"
  # docker compose config prints "name: <project>" on the first line
  docker compose config 2>/dev/null \
    | awk '/^name:/ { print $2; exit }' \
    || basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | tr ' _.' '-'
}

PROJECT_NAME="${COMPOSE_PROJECT_NAME:-$(get_project_name)}"
CHROME_IMAGE="${PROJECT_NAME}-chrome"
NETWORK="${PROJECT_NAME}_default"
NOVNC_BASE="${NOVNC_PORT:-3010}"
LABEL_KEY="chrome.pool.extra"

# ── Helpers ───────────────────────────────────────────────────────────────────

die()  { echo "ERROR: $*" >&2; exit 1; }

usage() {
  grep '^#' "$0" | grep -v '^#!/' | sed 's/^# \{0,1\}//'
  exit 1
}

# Print names of all extra chrome containers (chrome-2, chrome-3, …) sorted
extra_containers() {
  docker ps -a \
    --filter "label=${LABEL_KEY}=true" \
    --filter "network=${NETWORK}" \
    --format "{{.Names}}" 2>/dev/null \
    | sort -t- -k2 -n
}

# True if the compose-managed chrome service is running
chrome1_running() {
  cd "$PROJECT_DIR"
  docker compose ps chrome --format json 2>/dev/null \
    | grep -q '"State":"running"' 2>/dev/null || false
}

# Ensure the chrome image is built (docker compose build chrome)
ensure_image() {
  if ! docker image inspect "$CHROME_IMAGE" &>/dev/null; then
    echo "  Building chrome image (first run)..."
    cd "$PROJECT_DIR" && docker compose build chrome
  fi
}

# Start chrome instance N (N >= 2)
start_instance() {
  local n=$1
  local name="chrome-${n}"
  local novnc_port=$(( NOVNC_BASE + n - 1 ))
  local volume="${PROJECT_NAME}_chrome_profile_${n}"

  if docker ps --filter "name=^${name}$" --format "{{.Names}}" | grep -q "^${name}$"; then
    echo "  ✓ ${name} already running (noVNC :${novnc_port})"
    return
  fi

  if docker ps -a --filter "name=^${name}$" --format "{{.Names}}" | grep -q "^${name}$"; then
    echo "  ▶ Restarting stopped container ${name}..."
    docker start "${name}" >/dev/null
    echo "    noVNC → http://localhost:${novnc_port}"
    return
  fi

  echo "  ▶ Starting ${name}  (noVNC → http://localhost:${novnc_port})"
  docker run -d \
    --name "${name}" \
    --network "${NETWORK}" \
    --label "${LABEL_KEY}=true" \
    --label "chrome.pool.index=${n}" \
    -p "${novnc_port}:6080" \
    -v "${volume}:/home/chrome/.config/chromium" \
    --restart unless-stopped \
    "${CHROME_IMAGE}" >/dev/null
}

# Stop and remove instance N (N >= 2)
stop_instance() {
  local name="chrome-${1}"
  if docker ps -a --filter "name=^${name}$" --format "{{.Names}}" | grep -q "^${name}$"; then
    echo "  ✗ Removing ${name}..."
    docker rm -f "${name}" >/dev/null
  fi
}

# Build endpoint list from running instances
build_endpoints() {
  local eps=()
  chrome1_running && eps+=("http://chrome:19222")
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    eps+=("http://${name}:19222")
  done < <(extra_containers | grep -v '^$')
  local IFS=','
  echo "${eps[*]}"
}

# ── Commands ──────────────────────────────────────────────────────────────────

cmd_start() {
  local N="${1:-3}"
  [[ "$N" =~ ^[0-9]+$ && "$N" -ge 1 ]] \
    || die "N must be a positive integer (got: $N)"

  echo "Starting Chrome pool: ${N} instance(s)"
  echo "  Instance 1 is managed by docker-compose (already running or start with: docker compose up -d chrome)"
  echo ""

  ensure_image

  # Start instances 2..N
  for (( i=2; i<=N; i++ )); do
    start_instance "$i"
  done

  # Stop instances that exceed N
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    idx="${name##*-}"
    if [[ "$idx" -gt "$N" ]]; then
      stop_instance "$idx"
    fi
  done < <(extra_containers)

  echo ""
  echo "Done. Add to .env and restart the API:"
  echo ""
  echo "  CHROME_POOL_ENDPOINTS=$(build_endpoints)"
  echo ""
  echo "Login each new instance via noVNC to authenticate site sessions:"
  for (( i=2; i<=N; i++ )); do
    echo "  chrome-${i} → http://localhost:$(( NOVNC_BASE + i - 1 ))"
  done
}

cmd_stop() {
  echo "Stopping all extra Chrome instances..."
  local stopped=0
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    idx="${name##*-}"
    stop_instance "$idx"
    (( stopped++ )) || true
  done < <(extra_containers)
  [[ "$stopped" -eq 0 ]] && echo "  No extra instances running."
  echo "Instance 1 (chrome) is still managed by docker-compose."
}

cmd_status() {
  echo "Chrome pool status  (project: ${PROJECT_NAME})"
  echo "─────────────────────────────────────────────"

  local i=1
  if chrome1_running; then
    echo "  [1] chrome          noVNC → http://localhost:${NOVNC_BASE}   CDP → http://chrome:19222  (compose)"
  else
    echo "  [1] chrome          ✗ not running  (start: docker compose up -d chrome)"
  fi

  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    (( i++ ))
    local port=$(( NOVNC_BASE + i - 1 ))
    local running
    running=$(docker inspect --format "{{.State.Status}}" "$name" 2>/dev/null || echo "unknown")
    echo "  [${i}] ${name}  noVNC → http://localhost:${port}   CDP → http://${name}:19222  (${running})"
  done < <(extra_containers)

  echo ""
  local eps
  eps=$(build_endpoints)
  if [[ -n "$eps" ]]; then
    echo "CHROME_POOL_ENDPOINTS=${eps}"
  else
    echo "No running instances detected."
  fi
}

cmd_endpoints() {
  build_endpoints
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

[[ $# -ge 1 ]] || usage

case "${1}" in
  start)     cmd_start "${2:-3}" ;;
  stop)      cmd_stop ;;
  status)    cmd_status ;;
  endpoints) cmd_endpoints ;;
  *)         usage ;;
esac

#!/bin/bash
set -e

# Detect whether Chrome is embedded in this image.
# If not, agent_server connects to the host-provided Chrome via env vars.
HAVE_CHROME=false
if command -v chromium > /dev/null 2>&1; then
    HAVE_CHROME=true
fi

if [ "$HAVE_CHROME" = "true" ]; then
    echo "[agent] Chrome detected — starting embedded browser stack"

    # ── 1. Virtual display ────────────────────────────────────────────────────
    rm -f /tmp/.X99-lock
    Xvfb :99 -screen 0 1280x900x24 -nolisten tcp &
    export DISPLAY=:99
    sleep 1

    # ── 2. Clean stale Chrome locks ───────────────────────────────────────────
    find /home/agent/.config/chromium \
        -name 'SingletonLock' -o -name 'SingletonCookie' -o -name 'SingletonSocket' \
        2>/dev/null | xargs rm -f 2>/dev/null || true

    # ── 3. Browser Bridge daemon (for bridge mode) ────────────────────────────
    DAEMON_JS="$(npm root -g)/@jackwener/opencli/dist/daemon.js"
    if [ -f "$DAEMON_JS" ]; then
        (while true; do
            OPENCLI_DAEMON_LISTEN=127.0.0.1 node "$DAEMON_JS"
            echo "[agent] Bridge daemon exited, restarting in 1s..."
            sleep 1
        done) &
        echo "[agent] Bridge daemon started on 127.0.0.1:${OPENCLI_DAEMON_PORT:-19825}"
    else
        echo "[agent] WARNING: Bridge daemon not found at $DAEMON_JS"
    fi

    # ── 4. Chrome ─────────────────────────────────────────────────────────────
    start_chrome() {
        find /home/agent/.config/chromium \
            -name 'SingletonLock' -o -name 'SingletonCookie' -o -name 'SingletonSocket' \
            2>/dev/null | xargs rm -f 2>/dev/null || true
        chromium \
            --remote-debugging-port=9222 \
            --remote-debugging-address=127.0.0.1 \
            --remote-allow-origins='*' \
            --no-sandbox \
            --disable-dev-shm-usage \
            --user-data-dir=/home/agent/.config/chromium \
            --load-extension=/home/agent/extension \
            --window-size=1280,900 \
            "$@"
    }

    (while true; do
        start_chrome || true
        echo "[agent] Chrome exited, restarting in 2s..."
        sleep 2
    done) &

    # ── 5. Wait for Chrome CDP ────────────────────────────────────────────────
    echo "[agent] Waiting for Chrome CDP..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:9222/json/version > /dev/null 2>&1; then
            echo "[agent] Chrome ready"
            break
        fi
        sleep 1
    done

else
    echo "[agent] No embedded Chrome — connecting to host Chrome via OPENCLI_CDP_ENDPOINT / OPENCLI_DAEMON_HOST"
    echo "[agent]   CDP endpoint : ${OPENCLI_CDP_ENDPOINT:-<not set>}"
    echo "[agent]   Bridge daemon: ${OPENCLI_DAEMON_HOST:-<not set>}:${OPENCLI_DAEMON_PORT:-19825}"
fi

# ── Agent server ───────────────────────────────────────────────────────────────
exec uvicorn backend.agent_server:app \
    --host 0.0.0.0 \
    --port "${AGENT_PORT:-19823}" \
    --log-level info

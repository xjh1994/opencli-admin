#!/bin/bash
set -e

# Start virtual display
Xvfb :99 -screen 0 1280x900x24 -nolisten tcp &
export DISPLAY=:99

sleep 1

# Remove stale profile locks (left by crashed/restarted containers)
find /home/chrome/.config/chromium -name 'SingletonLock' -o -name 'SingletonCookie' -o -name 'SingletonSocket' 2>/dev/null | xargs rm -f 2>/dev/null || true

# Generate nginx config with this container's hostname so CDP WebSocket URLs
# are rewritten to the correct container name (supports multi-instance pools).
export CHROME_HOSTNAME="${CHROME_HOSTNAME:-${HOSTNAME:-chrome}}"
envsubst '${CHROME_HOSTNAME}' \
  < /etc/nginx/conf.d/cdp.conf.template \
  > /etc/nginx/conf.d/cdp.conf

# nginx proxy: rewrites Host header to localhost so Chrome accepts CDP requests
nginx -g 'daemon off;' &

# Start noVNC web UI on port 6080
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb -forever -shared &
websockify --web /usr/share/novnc 6080 localhost:5900 &

# Keep Chromium running; restart on crash
start_chrome() {
  find /home/chrome/.config/chromium -name 'SingletonLock' -o -name 'SingletonCookie' -o -name 'SingletonSocket' 2>/dev/null | xargs rm -f 2>/dev/null || true
  chromium \
    --remote-debugging-port=9222 \
    --remote-debugging-address=0.0.0.0 \
    --remote-allow-origins='*' \
    --no-sandbox \
    --disable-dev-shm-usage \
    --user-data-dir=/home/chrome/.config/chromium \
    --window-size=1280,900 \
    "$@"
}

while true; do
  start_chrome || true
  echo "[entrypoint] Chromium exited, restarting in 2s..."
  sleep 2
done

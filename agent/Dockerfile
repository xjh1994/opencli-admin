ARG REGISTRY=
FROM ${REGISTRY}python:3.13-slim

# Switch to Aliyun apt mirror for faster downloads in China
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# System deps: headless Chrome + virtual display + opencli runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium xvfb \
    fonts-noto-cjk \
    curl ca-certificates procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install both opencli versions (same as main API image)
#   /opt/opencli-bridge  →  1.0.0  (Browser Bridge / daemon mode)
#   /opt/opencli-cdp     →  0.9.6  (Playwright direct CDP)
ARG OPENCLI_BRIDGE_VERSION=1.0.0
ARG OPENCLI_CDP_VERSION=0.9.6
COPY scripts/patch-opencli.js /tmp/patch-opencli.js
RUN npm install -g --prefix /opt/opencli-bridge @jackwener/opencli@${OPENCLI_BRIDGE_VERSION} \
    && node /tmp/patch-opencli.js /opt/opencli-bridge \
    && npm install -g --prefix /opt/opencli-cdp @jackwener/opencli@${OPENCLI_CDP_VERSION} \
    && rm /tmp/patch-opencli.js \
    && rm -rf /root/.npm

# Python deps for agent_server only — intentionally minimal
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    pyyaml \
    websockets

# Browser Bridge extension (same as chrome image)
COPY chrome/extension-src/manifest.json /home/agent/extension/manifest.json
COPY chrome/extension-src/icons/         /home/agent/extension/icons/
COPY chrome/extension-src/dist/background.js /home/agent/extension/dist/background.js

# Agent server source — only agent_server.py is needed at runtime
WORKDIR /app
COPY backend/agent_server.py ./backend/agent_server.py
RUN touch ./backend/__init__.py

COPY agent/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -m -u 1000 agent \
    && mkdir -p /home/agent/.config/chromium \
    && chown -R agent:agent /home/agent /app

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Chrome runs inside this container — always localhost
    OPENCLI_CDP_ENDPOINT=http://localhost:9222 \
    OPENCLI_BRIDGE_BIN=/opt/opencli-bridge/bin/opencli \
    OPENCLI_CDP_BIN=/opt/opencli-cdp/bin/opencli \
    # Bridge daemon is local too
    OPENCLI_DAEMON_HOST=127.0.0.1 \
    OPENCLI_DAEMON_PORT=19825

USER agent

# agent_server HTTP port
EXPOSE 19823

ENTRYPOINT ["/entrypoint.sh"]

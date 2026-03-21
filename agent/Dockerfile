ARG REGISTRY=
FROM ${REGISTRY}python:3.13-slim

# Switch to Aliyun apt mirror for faster downloads in China
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# Base system deps (always installed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates procps \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Optional: headless Chrome + virtual display ───────────────────────────────
# Set INSTALL_CHROME=true at build time to embed Chrome in the image.
# Default: false — connect to Chrome running on the host machine instead.
# With Chrome:    ~1.2 GB image, self-contained (no host Chrome required)
# Without Chrome: ~200 MB image, host provides Chrome via OPENCLI_CDP_ENDPOINT
ARG INSTALL_CHROME=false
RUN if [ "$INSTALL_CHROME" = "true" ]; then \
    apt-get update && apt-get install -y --no-install-recommends \
        chromium xvfb fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*; \
fi

# Install opencli globally — available as 'opencli' on PATH
ARG OPENCLI_VERSION=1.1.0
RUN npm install -g @jackwener/opencli@${OPENCLI_VERSION} \
    && rm -rf /root/.npm

# Python deps for agent_server only — intentionally minimal
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    pyyaml \
    websockets

# Browser Bridge extension — only useful when Chrome runs inside the container
# Copied unconditionally so the image can be promoted to INSTALL_CHROME=true
# via a simple rebuild without changing the layer structure.
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
    # Bridge daemon port (used when Chrome is embedded OR daemon runs on host)
    OPENCLI_DAEMON_PORT=19825

USER agent

# agent_server HTTP port
EXPOSE 19823

ENTRYPOINT ["/entrypoint.sh"]

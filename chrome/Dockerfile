ARG REGISTRY=
FROM ${REGISTRY}debian:bookworm-slim

# Switch to Aliyun apt mirror for faster downloads in China
RUN sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|http://deb.debian.org|http://mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# OPENCLI_VERSION: pin the opencli release; patch-opencli.js adds DAEMON_HOST/LISTEN env hooks
ARG OPENCLI_VERSION=1.0.0
COPY scripts/patch-opencli.js /tmp/patch-opencli.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium x11vnc xvfb novnc websockify procps nginx \
    fonts-noto-cjk gettext-base \
    curl ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @jackwener/opencli@${OPENCLI_VERSION} \
    && node /tmp/patch-opencli.js \
    && rm /tmp/patch-opencli.js \
    && rm -rf /root/.npm /var/lib/apt/lists/*

COPY chrome/nginx-cdp.conf.template /etc/nginx/conf.d/cdp.conf.template

RUN useradd -m -u 1000 chrome \
    && rm /etc/nginx/sites-enabled/default 2>/dev/null || true \
    && chown -R chrome:chrome /var/lib/nginx /var/log/nginx /run /etc/nginx/conf.d \
    && sed -i 's/user www-data;//' /etc/nginx/nginx.conf \
    && sed -i 's|pid /run/nginx.pid|pid /tmp/nginx.pid|' /etc/nginx/nginx.conf \
    && mkdir -p /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix \
    && ln -sf /usr/share/novnc/vnc_lite.html /usr/share/novnc/index.html

COPY chrome/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Install Browser Bridge extension (pre-built dist/background.js is committed).
# To update: sync chrome/extension-src/ from the opencli repo and rebuild.
COPY chrome/extension-src/manifest.json /home/chrome/extension/manifest.json
COPY chrome/extension-src/icons/ /home/chrome/extension/icons/
COPY chrome/extension-src/dist/background.js /home/chrome/extension/dist/background.js

EXPOSE 9222 6080

USER chrome
# Pre-create profile directory as chrome user so Docker initialises new
# named volumes with the correct ownership (avoids "Permission denied" on
# first run when a fresh volume is mounted over a root-owned path).
RUN mkdir -p /home/chrome/.config/chromium

ENTRYPOINT ["/entrypoint.sh"]

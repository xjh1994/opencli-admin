ARG REGISTRY=
FROM ${REGISTRY}debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium x11vnc xvfb novnc websockify procps nginx \
    fonts-noto-cjk gettext-base \
    nodejs npm \
    && npm install -g @jackwener/opencli \
    && rm -rf /root/.npm /var/lib/apt/lists/*

COPY nginx-cdp.conf.template /etc/nginx/conf.d/cdp.conf.template

RUN useradd -m -u 1000 chrome \
    && rm /etc/nginx/sites-enabled/default 2>/dev/null || true \
    && chown -R chrome:chrome /var/lib/nginx /var/log/nginx /run /etc/nginx/conf.d \
    && sed -i 's/user www-data;//' /etc/nginx/nginx.conf \
    && sed -i 's|pid /run/nginx.pid|pid /tmp/nginx.pid|' /etc/nginx/nginx.conf \
    && mkdir -p /tmp/.X11-unix \
    && chmod 1777 /tmp/.X11-unix \
    && ln -sf /usr/share/novnc/vnc_lite.html /usr/share/novnc/index.html

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 9222 6080

USER chrome
# Pre-create profile directory as chrome user so Docker initialises new
# named volumes with the correct ownership (avoids "Permission denied" on
# first run when a fresh volume is mounted over a root-owned path).
RUN mkdir -p /home/chrome/.config/chromium

ENTRYPOINT ["/entrypoint.sh"]

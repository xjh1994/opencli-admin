# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a prefix so we can copy them cleanly
COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install --prefix=/install .

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

WORKDIR /app

# Runtime system deps (psycopg2 needs libpq, opencli needs Node.js)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Install opencli and playwright/mcp (separate layer — changes here don't re-run apt)
RUN npm install -g @jackwener/opencli @playwright/mcp \
    && rm -rf /root/.npm

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY backend/ ./backend/
COPY alembic.ini .

# Entrypoint handles migrations
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Non-root user for security; pre-create /data so the SQLite volume is writable
RUN useradd -m -u 1000 appuser && \
    mkdir -p /data && \
    chown -R appuser:appuser /app /data
USER appuser

ENV PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

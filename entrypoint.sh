#!/bin/sh
set -e

# Run DB migrations before starting any service.
# Uses a Python helper so we can auto-stamp existing databases that were
# created before Alembic was introduced (create_all path), preventing
# Alembic from trying to recreate already-existing tables.
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Running database migrations..."
  python3 - <<'EOF'
import asyncio
from backend.database import run_migrations
asyncio.run(run_migrations())
EOF
  echo "Migrations complete."
fi

exec "$@"

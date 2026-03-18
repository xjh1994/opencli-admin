#!/bin/sh
set -e

# Run DB migrations before starting any service
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Running Alembic migrations..."
  alembic upgrade head
  echo "Migrations complete."
fi

exec "$@"

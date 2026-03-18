#!/usr/bin/env bash
# Startup script for RepoForge server container.
# Runs Alembic migrations then starts uvicorn.
set -euo pipefail

echo "==> Running database migrations..."
python -m alembic upgrade head

echo "==> Starting uvicorn server..."
exec uvicorn app.main:app \
    --host "${SERVER_HOST:-0.0.0.0}" \
    --port "${SERVER_PORT:-8000}" \
    --workers 1 \
    --log-level "${LOG_LEVEL:-info}"

#!/usr/bin/env bash
set -euo pipefail

echo "[startup] Running database migrations (alembic upgrade heads)..."
alembic upgrade heads

echo "[startup] Starting web server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"

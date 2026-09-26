#!/usr/bin/env bash
# Start the StudyHub API (Termux/Linux). Run from anywhere:
#   bash backend/start.sh
# Overrides: HOST=... PORT=... PYTHON=... bash backend/start.sh
set -euo pipefail
cd "$(dirname "$0")"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PY="${PYTHON:-.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="python3"
fi

exec "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT"

#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PLANTERM_PYTHON_BIN:-$SCRIPT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[Error] Python dependencies are missing. Run ./scripts/rebuild_workspace.sh first." >&2
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/web/dist/index.html" ]; then
  echo "[Setup] Frontend build not found. Run ./scripts/rebuild_workspace.sh first." >&2
  exit 1
fi

HOST="${PLANTERM_HOST:-127.0.0.1}"
echo "[Run] PlanTerm UI: http://${HOST}:${PLANTERM_PORT:-8000}/"
echo "[Run] Health: http://${HOST}:${PLANTERM_PORT:-8000}/health"
exec "$PYTHON_BIN" -m uvicorn src.api:app --host "$HOST" --port "${PLANTERM_PORT:-8000}"

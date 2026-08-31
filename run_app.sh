#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PLANTERM_PYTHON_BIN:-$SCRIPT_DIR/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

if ! "$PYTHON_BIN" -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  echo "[Setup] Installing Python dependencies..."
  "$PYTHON_BIN" -m pip install -r requirements.txt
fi

if [ ! -f "$SCRIPT_DIR/web/dist/index.html" ]; then
  echo "[Setup] Frontend build not found. Run ./scripts/rebuild_workspace.sh first." >&2
  exit 1
fi

echo "[Run] PlanTerm UI: http://127.0.0.1:8000/"
echo "[Run] Health: http://127.0.0.1:8000/health"
exec "$PYTHON_BIN" -m uvicorn src.api:app --host 127.0.0.1 --port "${PLANTERM_PORT:-8000}" --reload


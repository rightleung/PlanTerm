#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
WEB_DIR="$ROOT_DIR/web"

if [ ! -d "$VENV_DIR" ]; then
  echo "[Rebuild] Creating Python virtual environment"
  python3 -m venv "$VENV_DIR"
fi

echo "[Rebuild] Installing Python and development dependencies"
"$VENV_DIR/bin/python" -m pip install -e ".[dev]"

echo "[Rebuild] Generating deterministic MINISO case"
"$VENV_DIR/bin/python" scripts/build_miniso_case.py

echo "[Rebuild] Installing frontend dependencies and building"
(
  cd "$WEB_DIR"
  npm ci --registry=https://registry.npmjs.org
  npm run build
)

test -s "$WEB_DIR/dist/index.html"
echo "[Rebuild] Done"

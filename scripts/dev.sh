#!/usr/bin/env bash
set -euo pipefail

echo "== Dev runner =="

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found"
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set"
  echo "Run: export OPENAI_API_KEY='sk-...'"
  exit 1
fi

echo "Python: $(python3 --version)"
echo "Using:  $(which python3)"

python3 - <<'PY'
import flask, reportlab
from openai import OpenAI
print("Imports OK: flask, reportlab, openai")
PY

echo "Starting Flask on http://127.0.0.1:8000"
export APP_HOST=127.0.0.1
export APP_PORT=8000

python3 app.py

#!/usr/bin/env bash
# Builds the frontend once and runs ONLY the backend -- FastAPI serves the
# built frontend itself (see backend/app/main.py's FRONTEND_DIST handling),
# so this is one process, one port, nothing else to start. This is the mode
# a self-hosted buyer actually runs, vs. run.sh's two-server dev setup.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_PY="$SCRIPT_DIR/.venv/bin/python3"

echo "== AI Lead Generation & Scoring Agent (production/merged mode) =="

if [ ! -x "$VENV_PY" ]; then
  echo "-> Creating Python virtual environment (.venv)..."
  python3 -m venv .venv
fi

echo "-> Installing backend dependencies..."
"$VENV_PY" -m pip install -q -r requirements.txt

echo "-> Building frontend..."
(cd frontend && npm install --silent && npm run build)

echo "-> Starting on http://localhost:8081 (Ctrl+C to stop)"
cd backend
# Only trust X-Forwarded-*  headers (needed for rate limiting to see the
# real client IP, not a reverse proxy's) if you're actually running this
# behind one -- see TRUST_PROXY_HEADERS in .env.example.
if [ "${TRUST_PROXY_HEADERS:-false}" = "true" ]; then
  exec "$VENV_PY" -m uvicorn app.main:app --port 8081 --proxy-headers --forwarded-allow-ips='*'
else
  exec "$VENV_PY" -m uvicorn app.main:app --port 8081
fi

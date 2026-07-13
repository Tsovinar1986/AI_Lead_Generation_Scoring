#!/usr/bin/env bash
# Starts both the backend (FastAPI) and frontend (React/Vite) for local use.
# macOS / Linux. First run installs dependencies automatically.
set -euo pipefail
set -m  # job control: puts each background job in its own process group,
        # so cleanup() can kill a whole group (reloader/esbuild subprocesses
        # included), not just the one PID bash happens to hand back.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
VENV_PY="$SCRIPT_DIR/.venv/bin/python3"

echo "== AI Lead Generation & Scoring Agent =="

if [ ! -x "$VENV_PY" ]; then
  echo "-> Creating Python virtual environment (.venv)..."
  python3 -m venv .venv
fi

# Deliberately not using `source .venv/bin/activate`: it hardcodes this
# project's absolute path at creation time, so if this folder is ever moved
# or renamed later, activation silently prepends a now-nonexistent directory
# to PATH and falls back to whatever "pip"/"uvicorn" happen to be on the
# system (wrong Python, or a from-source rebuild of everything). Invoking
# the venv's own python3 by path sidesteps that entirely and always works.
echo "-> Installing backend dependencies..."
"$VENV_PY" -m pip install -q -r requirements.txt

if [ ! -d "frontend/node_modules" ]; then
  echo "-> Installing frontend dependencies (npm install)..."
  (cd frontend && npm install)
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "-> Stopping backend and frontend..."
  [ -n "$BACKEND_PID" ] && kill -TERM "-$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill -TERM "-$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  # Belt-and-suspenders: reloader/esbuild helper processes sometimes survive
  # the group signal, so make sure the dev ports are actually free on exit.
  for port in 8000 5173; do
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    [ -n "$pids" ] && echo "$pids" | xargs kill -9 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "-> Starting backend  on http://localhost:8000"
(cd backend && exec "$VENV_PY" -m uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

echo "-> Starting frontend on http://localhost:5173"
(cd frontend && exec npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000/api/health"
echo "Frontend: http://localhost:5173"
echo "Press Ctrl+C to stop both."

wait

@echo off
REM Builds the frontend once and runs ONLY the backend -- FastAPI serves the
REM built frontend itself, so this is one process, one port. This is the
REM mode a self-hosted buyer actually runs, vs. run.bat's two-window dev setup.
setlocal

cd /d "%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo == AI Lead Generation ^& Scoring Agent (production/merged mode) ==

if not exist "%VENV_PY%" (
  echo -^> Creating Python virtual environment .venv...
  python -m venv .venv
)

echo -^> Installing backend dependencies...
"%VENV_PY%" -m pip install -q -r requirements.txt

echo -^> Building frontend...
pushd frontend
call npm install --silent
call npm run build
popd

echo -^> Starting on http://localhost:8081 (Ctrl+C to stop)
cd backend
"%VENV_PY%" -m uvicorn app.main:app --port 8081

endlocal

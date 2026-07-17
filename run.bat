@echo off
REM Starts both the backend (FastAPI) and frontend (React/Vite) for local use.
REM Windows. First run installs dependencies automatically. Opens two windows.
setlocal

cd /d "%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

echo == AI Lead Generation ^& Scoring Agent ==

if not exist "%VENV_PY%" (
  echo -^> Creating Python virtual environment .venv...
  python -m venv .venv
)

REM Deliberately not using ".venv\Scripts\activate.bat": if this folder is
REM ever moved or renamed, activation can point at a stale path and silently
REM fall back to whatever python/pip is on PATH instead. Calling the venv's
REM own python.exe by full path avoids that.

echo -^> Installing backend dependencies...
"%VENV_PY%" -m pip install -q -r requirements.txt

if not exist "frontend\node_modules" (
  echo -^> Installing frontend dependencies ^(npm install^)...
  pushd frontend
  call npm install
  popd
)

echo -^> Starting backend in a new window on http://localhost:8081
start "Lead Agent - Backend" cmd /k "cd /d "%~dp0backend" && "%VENV_PY%" -m uvicorn app.main:app --reload --port 8081"

echo -^> Starting frontend in a new window on http://localhost:5173
start "Lead Agent - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Backend:  http://localhost:8081/api/health
echo Frontend: http://localhost:5173
echo Two new windows were opened for backend and frontend - close them to stop.

endlocal

@echo off
REM Start backend and frontend in separate windows and open browser
SETLOCAL
SET ROOT=%~dp0

REM Start backend in a new cmd window
IF EXIST "%ROOT%backend\.venv\Scripts\activate.bat" (
  start "Backend" cmd /k "cd /d %ROOT%backend && .venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
) ELSE (
  start "Backend" cmd /k "cd /d %ROOT%backend && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

REM Start frontend in a new cmd window (bind to 0.0.0.0 so tools can reach it)
start "Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev -- --host 0.0.0.0 --port 4173 --strictPort"

REM Open browser to the frontend
start "" "http://localhost:4173/"

ENDLOCAL
exit /b 0

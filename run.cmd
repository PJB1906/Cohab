@echo off
REM Cohab — one-click/one-command dev launcher.
REM Double-click this file in Explorer, or run `run.cmd` / `.\run.cmd` from a
REM terminal. Starts Postgres (Docker), applies migrations, then starts the
REM backend (uvicorn) and frontend (vite) each in their own window.
setlocal
cd /d "%~dp0"

echo ============================================
echo  Cohab dev launcher
echo ============================================

echo.
echo [1/3] Making sure the database is up...
docker compose up -d db >nul 2>&1
if not errorlevel 1 goto :db_ready

echo Docker doesn't seem to be running yet — starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

set /a _tries=0
:wait_docker
set /a _tries+=1
if %_tries% gtr 60 (
    echo.
    echo Docker Desktop did not come up after 3 minutes. Start it manually
    echo and re-run this script.
    goto :error
)
%SystemRoot%\System32\timeout.exe /t 3 /nobreak >nul
docker compose up -d db >nul 2>&1
if errorlevel 1 goto :wait_docker

:db_ready
echo Database is up.

echo.
echo [2/3] Applying database migrations...
pushd backend
call .venv\Scripts\activate.bat
alembic upgrade head
if errorlevel 1 (
    popd
    goto :error
)
popd
echo Migrations up to date.

echo.
echo [3/3] Starting backend and frontend...

REM Stop anything already listening on our ports before starting new servers.
REM
REM Why this exists: uvicorn on Windows does not set SO_EXCLUSIVEADDRUSE, so a
REM second `uvicorn --port 8000` binds successfully instead of failing. Two
REM servers then share the port and requests go to whichever wins the race —
REM which presents as "my backend edit did nothing", because the older process
REM (started before the edit, and holding pre-edit code) is answering. This
REM cost a real debugging session; see docs/DECISIONS.md D-13.14.
REM
REM Guarded on 127.0.0.1:<port> so we only ever kill a local dev listener.
call :free_port 8000 "backend"
call :free_port 5173 "frontend"

start "Cohab Backend"  cmd /k "cd /d "%~dp0backend"  && call .venv\Scripts\activate.bat && uvicorn cohab.main:app --reload"
start "Cohab Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

%SystemRoot%\System32\timeout.exe /t 4 /nobreak >nul
start http://localhost:5173

echo.
echo ============================================
echo  Cohab is running:
echo    Frontend  http://localhost:5173
echo    Backend   http://localhost:8000
echo.
echo  Two new windows opened for backend/frontend logs.
echo  Close them (or Ctrl+C inside them) to stop the app.
echo ============================================
pause
goto :eof


REM --------------------------------------------------------------------------
REM :free_port <port> <label>
REM Terminates any process LISTENING on 127.0.0.1:<port> or [::1]:<port>.
REM Vite binds IPv6 loopback and uvicorn binds IPv4, so both forms are matched.
REM Silent when the port is already free, which is the normal case.
REM --------------------------------------------------------------------------
REM Written without delayed expansion: this script runs under plain `setlocal`,
REM where a variable set inside a `for` body is not readable inside that same
REM body. So the "did we kill anything" test is a separate pass over netstat
REM rather than a flag set in the loop.
:free_port
set "_port=%~1"
set "_label=%~2"

netstat -ano | findstr /r /c:"TCP .*:%_port% .*LISTENING" >nul 2>&1
if errorlevel 1 goto :eof

echo   Port %_port% is already in use — stopping the old %_label%...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /r /c:"TCP .*:%_port% .*LISTENING"') do (
    if not "%%P"=="0" taskkill /PID %%P /F >nul 2>&1
)
REM Give the socket a moment to leave TIME_WAIT before the new server binds.
%SystemRoot%\System32\timeout.exe /t 2 /nobreak >nul
goto :eof

:error
echo.
echo Startup failed — see the messages above.
pause

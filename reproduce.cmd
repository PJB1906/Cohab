@echo off
rem Cohab v2: regenerate every result. Usage:
rem   reproduce.cmd            real study data + all simulations
rem   reproduce.cmd dryrun     the synthetic dry run
rem   reproduce.cmd quick      small in-memory smoke run, no DB writes
rem   reproduce.cmd demo       write dry run, results and a demo calibration
setlocal
cd /d "%~dp0backend"
set PY=.venv\Scripts\python.exe
if "%1"=="" %PY% -m cohab.analysis.reproduce --source real & goto :eof
if "%1"=="dryrun" %PY% -m cohab.analysis.reproduce --source dryrun & goto :eof
if "%1"=="quick" %PY% -m cohab.analysis.reproduce --source dryrun-memory --quick --no-db-write --out ..\docs\results-quick & goto :eof
if "%1"=="demo" (
  %PY% -m cohab.analysis.dryrun_seed
  %PY% -m cohab.analysis.reproduce --source dryrun --activate-dryrun-calibration
  goto :eof
)
echo Unknown option "%1". Use: dryrun ^| quick ^| demo

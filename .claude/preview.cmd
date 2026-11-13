@echo off
rem Preview server for Claude's browser pane: FastAPI serving the built frontend
rem on one origin (CLAUDE.md same-origin rule). Build first: cd frontend && npm run build
cd /d "%~dp0..\backend"
set COHAB_PORT=8011
.venv\Scripts\python.exe -m uvicorn cohab.main:app --host 127.0.0.1 --port 8011

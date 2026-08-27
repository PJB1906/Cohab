# Render deploy image (docs/DECISIONS.md). Multi-stage: build the frontend
# with Node, run the backend with Python — CLAUDE.md's same-origin design
# (FastAPI serves the built bundle) means one image, one container, one
# Render web service.

FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
# FRONTEND_DIST_DIR defaults to ../frontend/dist relative to backend's cwd
# (core/config.py) — this lands the built bundle at exactly that path.
COPY --from=frontend /app/frontend/dist /app/frontend/dist

EXPOSE 8000
# Render sets $PORT at runtime; alembic upgrade head is safe to run on every
# boot (no-ops once already at head), which auto-migrates on every deploy
# and every free-tier spin-down/wake cycle without a separate step.
CMD alembic upgrade head && uvicorn cohab.main:app --host 0.0.0.0 --port ${PORT:-8000}

# Cohab v2 — common tasks. On Windows without make, use reproduce.cmd.
PY ?= backend/.venv/bin/python
ifeq ($(OS),Windows_NT)
PY = backend/.venv/Scripts/python
endif

.PHONY: test test-fast migrate seed dryrun reproduce reproduce-quick reproduce-dryrun demo frontend

test:            ## full backend suite (needs Postgres up, migrated and seeded)
	cd backend && ../$(PY) -m pytest -q

test-fast:       ## DB-free tests only: matcher, vectorised scorer, analysis
	cd backend && ../$(PY) -m pytest -q tests/matching tests/core tests/analysis

migrate:
	cd backend && ../$(PY) -m alembic upgrade head

seed:
	cd backend && ../$(PY) -m cohab.seed && ../$(PY) -m cohab.demo_seed

dryrun:          ## write a SYNTHETIC dry-run study into the study tables
	cd backend && ../$(PY) -m cohab.analysis.dryrun_seed

reproduce:       ## every v2 result from real study data, plus all simulations
	cd backend && ../$(PY) -m cohab.analysis.reproduce --source real

reproduce-dryrun:
	cd backend && ../$(PY) -m cohab.analysis.reproduce --source dryrun

reproduce-quick: ## small settings, in memory, no DB writes (CI smoke test)
	cd backend && ../$(PY) -m cohab.analysis.reproduce --source dryrun-memory --quick --no-db-write --out ../docs/results-quick

demo: dryrun     ## dry run + results + demo calibration, for the viva demo
	cd backend && ../$(PY) -m cohab.analysis.reproduce --source dryrun --activate-dryrun-calibration

frontend:
	cd frontend && npm run build

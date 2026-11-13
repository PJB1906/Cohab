# Cohab

Cohab is a roommate matching platform built on compatibility. Members verify who they are and fill in a short lifestyle questionnaire. Cohab then gives each member a **ranked, explainable** shortlist of possible roommates. Matched members can chat in a moderated in-app chat before either of them shares contact details. Outcome feedback is fed back into the scoring.

This is an academic project for the MSc Data Science programme at Christ University, by Puranjyoti Bera and Alwin N Joseph, guided by Dr Sathya P. It is meant to carry on as a real product after submission. The v1 pilot covers a single campus: Christ University students in Bangalore.

## How matching works

Matching runs in two stages. The stages are kept separate on purpose; they are never merged into one score.

1. **Hard constraints (pass/fail).** These are: same city, budget bands that overlap, move-in dates within `MOVE_IN_TOLERANCE_DAYS` (30 days, a configurable value), gender preference satisfied on both sides, smoking/pet/allergy deal-breakers, and an account that is verified, active and unblocked. A good score elsewhere can never make up for a failure here. Each excluded candidate keeps the reason it was excluded.
2. **Soft scoring (weighted, 0–1).** Each attribute has a type: similarity, tolerance, absolute or continuous. Scoring runs in both directions. `S(a→b)` uses A's importance weights and `S(b→a)` uses B's. The two are combined with the **harmonic mean**, so a match that suits only one person ends up low. Each stored score records the immutable `weight_set` version it was computed under, so old explanations can always be reproduced.

The full questionnaire, the matrices, the default weights and the explanation templates are in [docs/COHAB_MATCHING_SPEC.md](docs/COHAB_MATCHING_SPEC.md).

## v2: evidence, not more screens

v2 replaces the expert-assigned weights with weights learned from people, and
says how sure it is. It adds an anonymous pairwise study (Cohab Lab), a
roommate-pair validation study, a Bradley–Terry fit shrunk toward the expert
prior with grouped cross-validation and bootstrap intervals, calibrated
confidence tiers, a top-3 "effectively tied" hint, a "why am I seeing so few
people?" panel, a policy simulation with Irving's stable roommates as a
reference, a fairness audit, and a moderator evidence page and playground.
Every result regenerates with `make reproduce` (Windows: `reproduce.cmd`) and is
tagged with its data source.

Start at [docs/COHAB_V2.md](docs/COHAB_V2.md); the study protocol is
[docs/COHAB_HUMAN_STUDY.md](docs/COHAB_HUMAN_STUDY.md).

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, scikit-learn (TF-IDF text similarity) |
| Database | PostgreSQL 16, with `JSONB` for the questionnaire |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, React Router, TanStack Query, GSAP |
| Auth | Session JWT in an `httpOnly`, `SameSite=Lax`, `Secure` cookie. Never stored in `localStorage` |
| Chat | REST polling; message content is encrypted at rest and PII-scanned on send |

Development uses one origin: Vite proxies `/api` to `localhost:8000`. In production, FastAPI serves the built frontend bundle itself, so the whole app is one process.

## Repository layout

```
backend/
  cohab/
    api/                FastAPI routers (thin: validate → service → serialise)
    services/           business logic, no FastAPI imports
      matching/         eligibility, scoring, ranker, explanations, tuning, evaluation
    models/             SQLAlchemy models
    core/               config, security (JWT/bcrypt), message encryption
    seed.py             deterministic synthetic profile generator
    demo_seed.py        demo accounts that reach every screen
    promote_moderator.py
  migrations/           Alembic
  tests/                pytest (matching/, api/, core/)
frontend/
  src/
    api/                typed client, one module per resource
    features/           auth, onboarding, matches, chat, profile, safety, moderation, analytics
    components/         shared UI
docs/                   PRD, matching spec, build plan, decisions log, evaluation
SDD/                    System Design Document (LaTeX source + PDF)
run.cmd                 one-step Windows dev launcher
Dockerfile              single-image production build (frontend + backend)
docker-compose.yml      local Postgres
```

## Getting started

**Prerequisites:** Python 3.11, Node 20, and Docker Desktop.

### 1. Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows; use `source .venv/bin/activate` elsewhere
pip install -r requirements.txt
cp .env.example .env
```

Leave `COOKIE_SECURE=False` for local http. OTP codes are printed to the console unless you set Resend or SMTP credentials in `.env`.

### 2. Frontend setup

```bash
cd frontend
npm install
```

### 3. Run it

On Windows, run `run.cmd` from the repo root, either by double-clicking it or with `.\run.cmd`. It starts the database (and Docker Desktop if it isn't running), applies the migrations, starts the backend and frontend in separate windows, and opens http://localhost:5173.

To run each piece by hand:

```bash
docker compose up -d db
```

```bash
cd backend && alembic upgrade head && uvicorn cohab.main:app --reload
```

```bash
cd frontend && npm run dev
```

### First moderator

A new database has no moderators, and there is deliberately no API route for granting the role ([docs/DECISIONS.md](docs/DECISIONS.md) D-7.1). Register the account in the app first, then run this from `backend/`:

```bash
python -m cohab.promote_moderator someone@example.com
```

## Tests

```bash
cd backend && pytest
```

The API tests need the Postgres database running. Everything under `services/matching/` has tests.

## Production

```bash
docker build -t cohab .
```

The image builds the frontend, installs the backend, runs `alembic upgrade head` on boot, and serves everything from uvicorn on `$PORT`. For anything other than localhost, set a real `SECRET_KEY` and keep `COOKIE_SECURE=True` (see [docs/DECISIONS.md](docs/DECISIONS.md) D-13.19).

## Evaluation

`python -m cohab.services.matching.evaluation` needs `requirements-dev.txt`. It reports filter yield, the score distribution, ablations, a precision@k/NDCG@10 recovery experiment and Kaplan–Meier survival. The results are in [docs/COHAB_EVALUATION.md](docs/COHAB_EVALUATION.md). Every figure there comes from **synthetic** data. The figures show that the implementation works as built; they are not evidence that the matching improves real roommate outcomes.

## Documentation

- [docs/COHAB_PRD.md](docs/COHAB_PRD.md): product requirements (authoritative)
- [docs/COHAB_MATCHING_SPEC.md](docs/COHAB_MATCHING_SPEC.md): questionnaire and scoring numbers (authoritative)
- [docs/COHAB_BUILD_PLAN.md](docs/COHAB_BUILD_PLAN.md): build phases
- [docs/DECISIONS.md](docs/DECISIONS.md): log of design decisions and deviations from the original design
- [CLAUDE.md](CLAUDE.md): repo conventions and invariants

### Deliberate deviations from the original SDD

- MongoDB was replaced with Postgres `JSONB`.
- Redis is deferred.
- Text similarity uses TF-IDF. Embeddings are optional and used only for evaluation.
- Not built: Irving's stable-roommates extension, a learned GBT ranker, ε-greedy exploration, WebSocket chat, and a consent/erasure workflow.

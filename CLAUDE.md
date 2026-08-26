# Cohab — Compatibility-Based Roommate Matching Platform

Academic project (MSc Data Science, Christ University), intended to continue as a
real product. Read this file first, every session.

## Source of truth — read before making design decisions

The authoritative design documents live in `docs/`:

- `docs/COHAB_PRD.md` and `docs/COHAB_MATCHING_SPEC.md` are **authoritative**.
- `docs/COHAB_BUILD_PLAN.md` sets the build order and the working method.
- `docs/DECISIONS.md` is the **running decisions log** — non-obvious choices and
  deliberate deviations taken during the build, with the spec section and code
  each relates to. It is not authoritative design (the PRD and matching spec are),
  but read it before re-deciding something already settled, and **append a new
  entry** when you make a design decision the specs do not fix.
- The SDD and SRS are **earlier, superseded documents** and are not kept in this
  repo. The PRD and matching spec override them. Do not go looking for them or
  treat them as the current design.

When you state a number, threshold or weight, name the document and section it
comes from. If it is not in any document, say you are proposing it — do not
present an invented value as specified. If a request contradicts a decision
recorded in these docs, say so before doing it.

## What this system claims to do

Capture a verified user profile and a structured lifestyle questionnaire, then
produce a **ranked, explainable** list of compatible roommate candidates. The
explainability is not decoration: a user must always be able to see which
attributes drove a score.

## Stack

**Backend**

- Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic
- PostgreSQL (single database — see "Deliberate deviations" below)
- pytest for tests

**Frontend**

- React 18 + Vite + TypeScript
- Tailwind CSS, shadcn/ui components
- React Router, TanStack Query for server state
- **Mobile-first.** Most pilot users arrive on a phone browser. Build at the
  small breakpoint and widen — not the reverse.

**Same-origin deployment — important**

- Dev: Vite dev server proxies `/api` → `localhost:8000`. Configure this in
  `vite.config.ts` rather than enabling permissive CORS.
- Prod: `vite build`, and FastAPI serves the static bundle. Same origin means
  no CORS in production and one deployable unit.
- Auth: session token in an `httpOnly`, `SameSite=Lax`, `Secure` cookie.
  **Never `localStorage`** — this app holds identity documents, private messages
  and contact details, and a token readable by injected script is not acceptable.
  Same-origin is what makes cookie auth simple here.

**Chat transport**

- WebSocket for live delivery; REST for history and initial load.
- For the pilot, chat ships as **REST polling first** (build plan Phase 6);
  WebSocket is the target transport, added once polling latency justifies it.
- `ChatService.send_message()` is transport-agnostic — PII detection, moderation
  flagging and persistence all live there, not in the WebSocket handler. The
  socket only broadcasts.
- Single uvicorn worker for the pilot. Connection state is in-process; scaling to
  multiple workers requires a Redis pub/sub backplane. Note it, don't build it.

## Architecture rules

- **The frontend never orchestrates business logic.** All workflow sequencing
  happens server-side behind the API layer. The client issues intent-level
  requests, not step sequences.
- Business logic lives in `cohab/services/`, and must be importable and testable
  without FastAPI. If a service needs a `Request` object, it's in the wrong layer.
- Route handlers stay thin: validate, call a service, serialise.

## Matching design — the part that must be right

Matching is **two-stage**, and the stages must not be collapsed into one score.

**Stage 1 — hard constraints (boolean).** A candidate passes or fails. Never
compensable by scoring well elsewhere. Constraints: same city, budget bands
intersect, move-in dates within tolerance, gender preference mutually satisfied,
smoking/pets deal-breakers respected, neither party blocked or suspended.
Retain the failure reason for each excluded candidate.

**Stage 2 — soft scoring (weighted, 0–1).** Only runs on candidates that passed
Stage 1.

Invariants:

- Scoring is **directional**. Compute `S(a→b)` using A's importance weights and
  `S(b→a)` using B's, then combine with the **harmonic mean** — not the
  arithmetic mean, which would hide a match that suits only one party.
- Every `match_score` row stores the `weight_set_id` it was computed under.
  Weight sets are **immutable once published**; refinement creates a new version.
  Without this, historical explanations are not reproducible.
- Text embeddings are computed **once on profile save** and cached. Never encode
  inside the match request path — it makes the 5-second performance target
  unreachable.

## Database invariants

- `match_score`: `CHECK (user_id_a < user_id_b)` plus `UNIQUE (user_id_a, user_id_b)`.
  A user pair is unordered; without canonical ordering the same pair inserts
  twice and every downstream count doubles.
- `feedback`: `UNIQUE (score_id, submitted_by)` — each participant reports once.
- `preference_profile`: `CHECK (budget_min <= budget_max)`.
- Budget is two integer columns (`budget_min`, `budget_max`), never a string.
  The scoring function computes a numeric difference over it.

## Deliberate deviations from the original design

Record these in the report rather than quietly diverging:

- **MongoDB → Postgres `JSONB`.** The design argument was schema flexibility for
  an evolving questionnaire; `JSONB` provides it without a second database.
- **Redis deferred.** In-process caching until there's a measured need.
- **Text similarity behind an interface.** `TfidfSimilarity` first;
  `EmbeddingSimilarity` (sentence-transformers) swapped in only if time allows.
- **Not implemented:** Irving's stable-roommates extension, the GBT learned
  ranker, ε-greedy exploration, WebSocket chat, consent/erasure workflow. All are
  documented in the SDD as extensions.

## Build order

Follow `docs/COHAB_BUILD_PLAN.md` §4. Summary: Phase 0 foundation → Phase 1 schema
+ crude seed → Phase 2 matcher (headless, tests first) → Phase 3 realistic seed +
tuning + embeddings → Phase 4 auth + API → Phase 5 UI → Phase 6 chat → Phase 7
safety → Phase 8 feedback loop → Phase 9 evaluation.

**One phase per session.** "Build Phase 2" is a good instruction. "Build the app"
is not — it produces a plausible skeleton with subtle inconsistencies. The matcher
(Phase 2) is the critical path: build it headless, tests first, then read the
top-10 output for a few profiles yourself before moving on.

## Layout

```
backend/
  cohab/
    models/       SQLAlchemy models
    services/     business logic — no FastAPI imports
      matching/   eligibility filter, matcher, ranker, explanations
    api/          FastAPI routers
    seed.py       synthetic profile generator (deterministic, fixed seed)
  tests/
frontend/
  src/
    api/          typed client, one module per resource
    components/   shared UI
    features/     questionnaire, matches, chat, listings
    routes/
  vite.config.ts  contains the /api dev proxy
docs/
  COHAB_PRD.md            authoritative
  COHAB_MATCHING_SPEC.md  authoritative
  COHAB_BUILD_PLAN.md     build order
```

## Commands

Keep these accurate as the repo takes shape:

- **Run everything (one step):** `run.cmd` at the repo root — double-click
  in Explorer, or run `.\run.cmd` from a terminal. Starts the DB (starting
  Docker Desktop first if needed), applies migrations, then launches the
  backend and frontend each in their own window and opens the app in a
  browser. Individual commands below are for when you need just one piece.
- Run API: `uvicorn cohab.main:app --reload`
- Run tests: `pytest`
- Migrations: `alembic upgrade head` / `alembic revision --autogenerate -m "..."`
- Frontend dev: `npm run dev` (in `frontend/`)
- Database: `docker compose up -d db`

## Conventions

- British spelling in user-facing strings and docs (`normalised`, `anonymised`)
  to match the submitted documents.
- Type hints on all service functions.
- Tests for anything in `services/matching/`. CRUD tests are optional; matching
  tests are not.
- Money in whole rupees as integers. Dates as `date`, timestamps as
  timezone-aware `datetime`.

## Working notes

- Prefer small, verifiable increments. Do not scaffold multiple layers in one go.
- Write failing tests before implementing matching logic.
- Never log message content, contact details, or ID document references.
- Read the matching code properly before accepting it — the scoring logic has to
  be defensible in the viva.
- When a design question isn't settled here or in the docs, ask rather than
  choosing silently — this is graded work and the author has to defend it.

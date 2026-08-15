# Cohab — Build Plan

**Context:** greenfield, building the full product, working in Claude Code.
**Principle:** everything in the SDD gets built. The order is chosen so the parts
most likely to be *wrong* get built while there's still time to react.

---

## 1. Why order matters even when nothing is cut

Two features can be equally necessary and still belong in different weeks.

The Auth module is well-understood: you know before writing a line what "working"
looks like, and the risk of it surprising you is close to zero. The matching
engine is the opposite — it can be fully implemented, pass every unit test, and
still produce rankings that look arbitrary when a human reads them. That failure
mode is only visible once it's running against realistic data, and fixing it may
mean revisiting the distance functions, the weights, or the questionnaire itself.

So the matcher goes early — not because it matters more, but because it's the
only part where "done" is a judgment call rather than a checklist. Auth built in
week 6 is the same auth as auth built in week 1. A matcher discovered to be
broken in week 6 is a very different problem from one discovered in week 2.

---

## 2. Two implementation substitutions

**Text similarity behind an interface.** sentence-transformers pulls in ~2 GB of
PyTorch, and a bad install can eat a day. Build:

```
TextSimilarity (interface)
├── TfidfSimilarity      ← Phase 2, works in minutes
└── EmbeddingSimilarity  ← Phase 3, once the pipeline is proven end-to-end
```

Both ship in the full product. TF-IDF first means you're never blocked on an
install while trying to get the core algorithm right, and the comparison between
the two becomes a genuine result you can report.

**MongoDB — your call, with a recommendation.** The SDD specifies Postgres +
MongoDB. The honest engineering position is that a Postgres `JSONB` column
delivers the schema flexibility your §2.2 rationale actually asks for, without
the operational cost of a second database. Two options:

- *Recommended:* `JSONB` now, and note it in the report as an MVP implementation
  decision. The design rationale stands; you can add Mongo when questionnaire
  churn justifies it.
- *If fidelity to the submitted SDD matters more:* build Mongo in Phase 1. It's
  perhaps a day of extra work and some ongoing friction, and it isn't wrong —
  just more than the problem currently needs.

Decide this before Phase 1, because the models depend on it.

---

## 3. On seed data — when you actually need it

You asked whether the database really has to be populated up front. Short
answer: **the schema, yes. Realistic volume, no — not yet.** There are three
distinct needs and they arrive at different times.

| Need | When | What's required |
|---|---|---|
| Unit-testing the scoring functions | Phase 2 | 8–12 **hand-written** fixture profiles. Volume adds nothing; you need known inputs and known expected outputs. |
| Judging whether rankings look sensible | End of Phase 2 | ~500 crude random profiles. Enough to produce a top-10 list you can read and react to. |
| Tuning weights, measuring filter yield, evaluation | Phase 3 | 1,000–2,000 profiles with *realistic, correlated* distributions. This is the one that takes a day to write. |

So the correct sequence is: schema → a crude seeder (30 minutes, random values,
no realism) → matcher with hand-written fixtures → upgrade the seeder properly
when you reach tuning. My earlier plan front-loaded the full generator; that was
wrong. Writing a careful generator against a schema you're still changing means
writing it twice.

One thing genuinely does need to happen early, though: **find out your filter
yield.** Stage 1 requires same city, overlapping budget, move-in within
tolerance, mutual gender preference, and deal-breakers respected. Those conjoin
fast. If realistic distributions leave the median user with four eligible
candidates out of two thousand, that's not a bug — it's a finding that changes
the product (widen tolerances, relax a constraint to a soft score, or seed the
pilot within a single campus). You want that discovery in Phase 3, not during
the pilot. A crude seeder in Phase 1 gives you an early smell of it.

---

## 4. Build order

### Phase 0 — Foundation (½ day)
Repo, venv, `requirements.txt`, Postgres via Docker Compose, FastAPI skeleton
with `/health`, Alembic initialised, **`CLAUDE.md` committed first**.

### Phase 1 — Schema + crude seed (1 day)
SQLAlchemy models and migrations for the full ERD. Include the tables you won't
use for weeks (`moderator`, `consent_record`, `contact_share`, `user_block`) —
designing them now is free and retrofitting them later is not.

Then a throwaway seeder: random values, no correlations, ~500 rows. Half an
hour. Its only job is to make the next phase testable.

### Phase 2 — Matcher, headless (2–3 days) ← the critical path
No API, no UI. Pure Python with tests.
1. `EligibilityFilter.filter(user, pool) -> (eligible, excluded_reasons)`
2. Attribute similarity — categorical distance, budget proximity, TF-IDF text
3. `CompatibilityMatcher` — directional scores, harmonic mean, breakdown
4. `MatchRanker` — sort, tie-break, template-based explanations

Unit-test against hand-written fixtures. Then run it over the crude seed data and
**read the top 10 for a few profiles yourself.** This is the checkpoint the whole
ordering exists to reach.

### Phase 3 — Realistic seed, tuning, embeddings (2 days)
Proper generator with correlated distributions (budget by city, move-in clustered
around term start, templated lifestyle notes). Deterministic seed for
reproducibility. Measure filter yield and score distribution. Tune weights. Swap
in `EmbeddingSimilarity` and compare against TF-IDF.

### Phase 4 — Auth, verification, API (2 days)
JWT auth, registration, email-OTP verification, profile CRUD (**compute and cache
the text vector on save**), `GET /matches`, `GET /matches/{id}/explanation`.

### Phase 5 — Core UI (2 days)
Signup, questionnaire, ranked match list, match detail with the attribute
breakdown. Built in React + Vite + TypeScript (Tailwind, shadcn/ui), mobile-first, and served same-origin behind the `/api` proxy. This is the decided product stack (project instructions and the Claude Design mockups), replacing the earlier Jinja + HTMX suggestion — the framework is not graded, but the mockups are drawn in React and the product is meant to be real. Follow the §13 wireframes and the desktop/mobile mockups.

### Phase 6 — Chat and contact sharing (2–3 days)
Start with REST polling; it is a genuinely working chat and takes hours.
WebSockets after it works, if the polling latency actually bothers you. Then the
mutual `contact_share` opt-in — the design's consent mechanism and worth getting
exactly right.

### Phase 7 — Safety and moderation (2 days)
Reports, blocks, the moderator admin view, report state machine per Figure 8.2.
Blocks must feed back into Stage 1 filtering.

### Phase 8 — Feedback loop and analytics (2–3 days)
Outcome logging, `weight_set` versioning with immutable published sets, the
periodic recompute job, institutional analytics dashboard.

### Phase 9 — Evaluation and polish (2 days)
The Chapter 12 metrics: filter yield, score distribution, attribute ablation,
precision@k. Two charts and a table here is the difference between "we built it"
and "we built it and here's how it behaves." Most student projects have nothing
on evaluation and examiners ask.

### Deferred to post-submission
Irving's stable-roommates algorithm, the GBT learned ranker, ε-greedy
exploration, IPS correction, Redis, the DPDP consent/erasure workflow. All are
documented in the SDD as extensions — that's the point of having written them up.

---

## 5. Working effectively in Claude Code

- **Commit `CLAUDE.md` first**, or you re-explain the project every session and
  get inconsistent naming across modules.
- **Put the SDD in `docs/`** as markdown so decisions are grounded in your design
  rather than invented.
- **One phase per session.** "Build Phase 2" works. "Build the app" produces a
  plausible skeleton with subtle inconsistencies that cost more to unpick than to
  have written.
- **Failing tests first for the matcher.** It's the one place where correctness
  is subtle enough that the tests should lead.
- **Read the matching code properly.** Skim the CRUD if you like, but you have to
  defend the scoring logic. Accepting code you can't explain is the main risk of
  building this way.
- **Commit at every green test run.**

---

## 6. Realistic effort

Phases 0–9 are roughly 18–22 focused working days for one developer, less if
Alwin works in parallel on a separate phase — Phases 6 and 7 split cleanly from
the matcher work.

If the trimester deadline arrives mid-sequence, submit at whatever phase boundary
you've reached and report the remainder as in-progress. Phase boundaries are
chosen so that each one is a coherent, demonstrable state rather than a
half-finished layer — that's what makes stopping at one of them defensible.

# Cohab — Session Handoff

**Date:** 13 August 2026
**Owner:** Puranjyoti Bera (2548035), with Alwin N Joseph (2548006)
**Guide:** Dr Sathya P — MSc Data Science, Christ University
**Session covered:** SDD review and correction → PRD → matching specification → build planning

---

## 1. What Cohab is

A compatibility-based roommate matching platform. Verified profiles plus a structured lifestyle questionnaire produce a ranked, **explainable** shortlist of candidates. Moderated in-app chat lets matched users talk before either shares a phone number. Match outcomes feed back to refine the scoring.

Academic project, but intended to continue as a real product beyond submission.

---

## 2. Current state

**No code exists yet.** The project is fully specified and ready to build.

| Artefact | Status |
|---|---|
| Synopsis | Submitted |
| SRS | Submitted — thin, treat as draft, superseded where it conflicts with the PRD |
| SDD | Submitted, then **revised and corrected this session** (34 → 53 pages) |
| PRD | Written this session |
| Matching spec | Written this session |
| Build plan | Written this session |
| `CLAUDE.md` | Drafted, to be committed at repo root before any code |
| Codebase | Not started |

**Timeline:** near the end of the trimester. Full product is the goal; phase boundaries are chosen so submission at any boundary is coherent.

---

## 3. Files produced

All in the working folder:

| File | Contents |
|---|---|
| `Cohab_SDD_revised.zip` | Drop-in replacement SDD package — `.tex`, 18 images, compiled PDF, figure-generation scripts, changelog |
| `Cohab_SDD_revised.pdf` | Compiled, 53 pages |
| `COHAB_PRD.md` | Full product requirements — problem, personas, scope, domain model, architecture, engine evolution, workflows, screens, chat requirements, safety/DPDP, cold start, risks, DS/ML inventory |
| `COHAB_MATCHING_SPEC.md` | The buildable spec — 15 questions with exact options, all distance and tolerance matrices, default weights, scoring pseudocode, explanation templates, tuning checklist |
| `COHAB_BUILD_PLAN.md` | Nine-phase build order with reasoning and migration triggers |
| `CLAUDE.md` | Repo context file for Claude Code — stack, invariants, conventions, deliberate deviations |

Inside the SDD zip, `figure-sources/schedule.py` is the single activity table generating **both** the Gantt and PERT figures — edit a duration there and re-run, and they cannot drift apart.

---

## 4. Decisions made this session

| Decision | Choice | Rationale |
|---|---|---|
| Build scope | Full product, phased | User's call; phases are an order, not a scope cut |
| Gender | **Hard filter** | Near-universal expectation in Indian shared housing |
| Diet | **Scored, never filtered** | Veg/non-veg acts as a caste and religion proxy; kitchen friction captured instead by a tolerance question about non-veg cooking |
| Seeker types | **Both**, with a `listing` entity | `has_place` + `has_place` is a hard incompatibility — neither is moving |
| v1 audience | **Single-campus pilot** (Christ University) | Density beats volume; the eligibility filter is unforgiving on a thin pool |
| MongoDB | **Replaced with Postgres `JSONB`** | Same schema flexibility, one less database to operate. Record as an MVP decision |
| Redis | Deferred | No measured need yet |
| Text similarity | **TF-IDF first**, embeddings after | Avoids being blocked on a 2 GB PyTorch install while getting the core algorithm right |
| Chat transport | **REST polling**, not WebSockets | ~100 lines vs 10× the work for imperceptible latency gain |
| Questionnaire | **Short required core + optional depth** | Preserves the 5-interaction usability target |
| Questionnaire basis | **Grounded in roommate-conflict research** | Citations in PRD §16 |
| Weight learning | **Three tiers**, not two | Fitted-weights step inserted between expert weights and GBT |
| Labelling study | Deferred until after chat is built | User's call; note the elapsed-vs-work-time caveat below |

---

## 5. Six errors found and fixed in the SDD

1. **Gale-Shapley → Irving's algorithm.** Roommate matching is non-bipartite; Gale-Shapley solves the bipartite stable *marriage* problem. Also documented: a stable roommates matching need not exist, with a defined fallback. **The most important viva point in the document.**
2. **Gantt said 16 weeks, PERT said 20.** Both now generated from one activity table and close at exactly 16.
3. **`budget_range VARCHAR(30)`** → `budget_min` / `budget_max INT`. A numeric difference is undefined on a string.
4. **MongoDB vs relational `PREFERENCE_PROFILE` contradiction** — resolved as filterable projection plus document body via `profile_doc_id`.
5. **"Frontend acts as central orchestration layer"** → server-side API gateway.
6. **"Encrypted chat" vs "moderated chat"** — a genuine contradiction, now stated and resolved (encryption at rest, not E2E, with the reasoning).

Also: `Odd Semester` / `Even Trimester` label mismatch, now **Even Trimester 2026–2027** in both places.

---

## 6. Design insights that must not be lost

These are the substance of the work. Losing them would cost days to re-derive.

**Four attribute types, not one.** The original design treated every attribute as a similarity comparison, which is wrong for three of four:
- *Hard* — pass/fail, non-compensable (city, budget, dates, gender, allergies, seeker type)
- *Similarity* — closer is better (sleep, cleanliness, chores, communication, interests)
- *Tolerance* — **asymmetric**: does A tolerate B's behaviour? (guests, smoking, alcohol, noise, non-veg cooking). A `prefer_none` person against a `rarely-has-guests` person scores 1.00 — a similarity model would call that a mismatch, which is absurd
- *Absolute* — higher is better regardless of self (payment reliability). Nobody wants a match on shared unreliability

**Directional scoring + harmonic mean.** Compute `S(a→b)` with A's weights and `S(b→a)` with B's, combine harmonically. 0.9 and 0.3 → 0.45, not 0.60. A match that suits one side only should rank low.

**Two `let_go` communicators score 0.55, not 1.00.** The one case where similarity is actively harmful — neither raises anything, resentment builds silently.

**Weight sets are immutable and versioned.** Every `match_score` stores its `weight_set_id`. Without this, an explanation shown in March cannot be reproduced in June and the explainability guarantee is hollow.

**PII detection in chat is the highest-value item in that feature.** Users will type their phone number into the first message. Without detection, they bypass the `contact_share` consent gate in thirty seconds and the platform's one substantive safety mechanism becomes decorative.

**Synthetic data validates the machine, not the theory.** It cannot generate informative labels — deciding what makes a match succeed is the thing being learned, so any model trained on synthetic outcomes recovers its own generator's assumption. Never report precision@k on synthetic data as evidence the matching works.

**The learned-ranker trap.** The abundant label (*pursued*) records a click; the label that matters (90-day survival) is rarest. Training on the abundant one produces a model optimising for appealing-looking profiles — quietly turning Cohab into a ranked attractiveness list.

**Kaplan–Meier for the primary metric.** 90-day cohabitation survival is right-censored. Survival analysis permits a meaningful estimate from partial follow-up, which is what makes the primary metric partially reportable inside the project timeline.

**Cold start is the biggest risk to the pilot.** Minimum viable density is ~150–200 verified profiles in overlapping localities and budget bands. Below that the eligibility filter leaves most users with too few candidates to judge the product fairly. Mitigation plan in PRD §11.

---

## 7. Immediate next steps

1. **Phase 0** — repo, venv, Docker Postgres, FastAPI skeleton, **commit `CLAUDE.md` first**, put the SDD in `docs/` as markdown
2. **Phase 1** — SQLAlchemy models and migrations for the full ERD (including `listing`), then a *crude* seeder (~500 random rows, 30 minutes)
3. **Phase 2** — the matcher, headless, unit tested against 8–12 hand-written fixtures. **Then read the top-10 output yourself** — this is the checkpoint the whole build order exists to reach
4. **Phase 3** — realistic seed generator, weight tuning, filter-yield measurement, swap in embeddings

Do **not** start with auth. It carries a week of slack on the PERT chart and is the most solved problem in the system.

**Seed data timing, corrected:** 8–12 hand-written fixtures for unit tests (Phase 2) → ~500 crude rows to eyeball rankings (Phase 1, half an hour) → 1,000–2,000 realistic correlated profiles only at Phase 3. Writing a careful generator against a schema still in flux means writing it twice.

---

## 8. Open questions

1. Move-in tolerance window — currently 30 days. **The single biggest lever on filter yield.** Settle early.
2. Do we surface *why* a candidate was excluded? Useful, but reveals information about an unseen pool.
3. Should `has_place` members see fewer, higher-quality matches given one room and a deadline?
4. Importance weighting (screen 6) — required or optional?
5. Profile browsing at all, or only system-generated matches?
6. Is Alwin building in parallel? Phases 6 and 7 split cleanly from the matcher work.

---

## 9. Deferred work

**Semi-synthetic labelling study** — deferred until after chat is built, per the user's decision. Design: a respondent fills the real questionnaire, then rates ~20 generated candidate profiles on a 1–5 scale and ticks what drove each decision. 30 respondents × 20 = 600 labelled rows, enough to fit 20 weights. Half a day to build, a week of elapsed collection, a day to analyse.

*Caveat noted at the time:* its cost is elapsed time rather than work time, so launching the form early and analysing late loses nothing, whereas deferring the launch pushes the collection week later into an already tight calendar. Weights are configuration, so learning late is cheap to act on — the downside is real but small.

Also deferred: Irving's algorithm, GBT reranker, ε-greedy exploration, inverse propensity scoring, Redis, DPDP consent/erasure workflow, group matching, institutional analytics, multi-city. All documented in the SDD as extensions.

---

## 10. Research grounding

Conflict dimensions are traceable to sources; nothing in the questionnaire is invented.

- Cleanliness ~42%, noise/sleep ~38%, guests ~31%, sharing ~27% of reported conflicts; 60–70% of students living with roommates report conflict
- Noise generates more residence-hall mediation than any other single issue
- Over 20% name non-payment as immediately terminable; 22% report financial arguments
- **Perceived** similarity predicts satisfaction more strongly than actual similarity — which is why the explanation screen is load-bearing, not decoration
- Attitude and communication similarity predict roommate *dissolution*, more strongly than lifestyle logistics
- Carli et al. (1991) found attractiveness similarity affects satisfaction — **considered and explicitly rejected** as a product decision

Key sources: Carli et al. (1991), *Personality and Social Psychology Bulletin*; Bahns et al. (2013), *Deciding to Dissolve*, Basic and Applied Social Psychology 35(2); University of Cape Coast roommate conflict study; Apartment List renter surveys; SpareRoom dispute guidance. Full list in PRD §16.

Reddit was requested as a source but is blocked to the web tools. Proxies used instead: crowd-sourced "questions to ask a roommate" lists, roommate agreement templates (what people formalise is what they have learned to fight about), and rental-platform survey data. **If Reddit threads are wanted, paste them in directly — analysing supplied text is fine.**

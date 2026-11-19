# Cohab v2 — what was built, and how to run it

v1 showed a two-stage, explainable roommate matcher could be built end to end,
measured only against data it generated. v2 asks whether it matches people
better than an expert-designed weight vector, and builds everything needed to
answer that honestly, including what to report if real data does not arrive.

## Workstreams

| | What | Where |
| --- | --- | --- |
| W1 | Exposure log, append-only state events, one writer for state, bulk read path, 8 indexes, explicit read receipts, funnel endpoint, CI, requirements split, `/health` DB check, `/metrics`, JSON logs | `services/match_events.py`, `services/funnel.py`, `core/observability.py`, migration `a1c0e5d2f7b9`, `.github/workflows/ci.yml` |
| — | Vectorised Stage 1 + Stage 2 for whole populations, verified equal to the reference matcher | `services/matching/vectorised.py` |
| W2 | Cohab Lab: anonymous pairwise study with conjoint design, repeats, attention checks, rank task | `services/study/`, `api/study.py`, `frontend/src/features/study/` |
| W3 | Roommate-pair validation: both people answer alone; outcomes and self-report inflation | same |
| W4 | Bradley–Terry fit shrunk toward the expert prior, grouped CV, baselines, noise ceiling, bootstrap, tier-B cluster fit, isotonic calibration, rank stability | `analysis/fitting.py`, `calibration.py`, `stability.py`, `reliability.py` |
| W5 | Policy simulation (random, expert, learned, oracle, Irving), misreporting stress test, power study, fairness audit, public-data transfer test | `analysis/simulation.py`, `irving.py`, `power.py`, `fairness.py`, `transfer.py` |
| W7 | Taste learning: per-member Bayesian logistic regression that reorders your list from your yes/no decisions, with an off switch; simulation in `reproduce` | `services/taste.py`, `api/taste.py`, `analysis/taste_sim.py`, migration `c4e2a8b1d9f3`, `frontend/src/features/matches/TastePanel.tsx` |
| W8 | "Loud poster" redesign, then the "Daylight" colour system (cobalt, navy, sun), photo banners, landing page, chemistry chart, credited stock photos | `frontend/src/index.css`, `components/Chemistry.tsx`, `features/landing/`, `public/photos/` |
| W6 | "Why so few people", top-3 tie hint, calibrated confidence tiers, evidence page, policy playground, `make reproduce`, protocol, datasheet, model card | `services/insights.py`, `api/evidence.py`, `frontend/src/features/evidence/`, `analysis/reproduce.py` |

Design decisions and every proposed value: `docs/DECISIONS.md` D-14.1 to D-14.26.

## Running it

```bash
docker compose up -d db
cd backend && python -m alembic upgrade head
python -m cohab.seed && python -m cohab.demo_seed
```

Results:

```bash
make reproduce            # real study data + all simulations (about 25 minutes)
make reproduce-quick      # in-memory smoke run, under a minute
make demo                 # synthetic dry run + results + a demo calibration
```

On Windows without make: `reproduce.cmd`, `reproduce.cmd quick`, `reproduce.cmd demo`.

Outputs go to `docs/results/*.json` (+ `figures/`) and to the `analysis_run`
table, which the evidence page reads. Every result is tagged `real`, `dryrun`,
`simulation` or `public`.

Publishing learned weights is separate and guarded:

```bash
python -m cohab.analysis.reproduce --source real --publish   # refuses unless tier A or B on real data
```

The public-data transfer test needs the Columbia speed-dating CSV saved as
`data/public/speed_dating.csv`; without it the evidence page says so.

## Pages

| Path | Who | What |
| --- | --- | --- |
| `/` | Logged out | Landing page (members are sent to `/matches`) |
| `/credits` | Anyone | Photo credits |
| `/study`, `/study/lab`, `/study/pair` | Anyone, no account | The two studies |
| `/matches` | Members | Tie hint, "why so few people", confidence tiers when calibrated, taste panel and "up N for you" |
| `/evidence` | Moderators | Every stored result, with its data-source tag |
| `/evidence/playground` | Moderators | Re-rank a synthetic person's shortlist live; verify against the server |

## Without real data

If recruitment fails, the report still has four results that need no rater
(tier D): the power study (how many raters the study needs before learning beats
the prior), weight-sensitivity and rank stability, the misreporting stress test
and policy comparison in simulation, and the transfer test on public
speed-dating data. The dry run demonstrates the full pipeline on synthetic
raters with a planted answer, and is labelled as such everywhere it appears.

## What v2 does not claim

That 90-day cohabitation improved. The event log and outcome instrumentation
exist; the outcome cannot be observed within one trimester.

## Tests

| Suite | What it checks |
| --- | --- |
| `tests/analysis/test_taste.py`, `tests/api/test_taste.py` | Taste fit follows the prior with no data and moves with consistent decisions; activation thresholds; re-ranking without changing shown scores; policy tag; off switch; post-chat rejections ignored |
| `tests/api/test_instrumentation.py` | Exposure rows and ranks, gap-free ordered event chain for a full journey, no score writes on repeat reads, reasons, funnel, health, metrics |
| `tests/matching/test_vectorised.py` | Vectorised scores, exclusion reasons and ranking equal the reference matcher |
| `tests/matching/test_study_design.py`, `tests/api/test_study.py` | Conjoint properties; consent, ordering, resume, withdrawal, flag, pairs, admin export |
| `tests/analysis/test_learning.py` | Recovery of planted weights, shrinkage, baselines, kappa and noise ceiling, exclusions, calibration, stability, tier-B fit, pair analyses |
| `tests/analysis/test_simulation.py` | Irving vs brute force, policy ordering, determinism, power, fairness, transfer on the dataset's format |
| `tests/api/test_showcase.py` | Insights write nothing and suggestions are exact; tiers only with calibration; evidence; playground arithmetic equals server |
| `tests/analysis/test_reproduce.py` | Every analysis runs, is tagged, and two runs give identical numbers |

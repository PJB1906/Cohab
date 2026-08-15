# Cohab SDD — revised package

Drop-in replacement for the original `System_Design_Document__SDD__.zip`.
Compiles with `pdflatex Cohab_SDD_v2.tex` (run 3× for the TOC, list of figures
and cross-references). 53 pages, no errors, no overfull boxes above 20pt.

## Corrections made

| # | Issue | Where |
|---|-------|-------|
| 1 | Gale-Shapley replaced with **Irving's algorithm** for the stable *roommates* (non-bipartite) problem, including the fact that a stable matching need not exist and the resulting fallback | §10.6 |
| 2 | Gantt (16 wks) and PERT (20 wks) reconciled — both now generated from one activity table and close at exactly 16 weeks | §12.1, §12.2, Figs 12.1–12.2 |
| 3 | `budget_range VARCHAR(30)` → `budget_min` / `budget_max INT`, so the normalised-difference computation is actually defined | §6.2, §10.3 |
| 4 | MongoDB vs relational `PREFERENCE_PROFILE` contradiction resolved (relational filterable projection + document body via `profile_doc_id`) | §2.2 |
| 5 | "Frontend acts as the central orchestration layer" replaced with a server-side API gateway | §2.1, §3.1, Figs 2.1, 3.1 |
| 6 | "Encrypted chat" vs "moderated chat" contradiction stated and resolved explicitly (encryption at rest, not E2E, with reasoning) | §11.3 |
| 7 | Axis label read "Odd Semester" while the text read "Even Trimester" — both now read **"Even Trimester 2026–2027"** | §12.1, Fig 12.1 |
| 8 | "trimster" typo | §12.1 |

## Added

- **§10.1–10.2** Two-stage matching: hard eligibility constraints before soft scoring (new Fig 10.1)
- **§10.3** Directional scoring with per-user importance weights, combined by harmonic mean
- **§10.4** Weight-set versioning for reproducible explanations
- **§10.5** Selection/position bias in the feedback loop, ε-greedy exploration and IPS correction
- **§8.2** Match and report state models (new Fig 8.2)
- **Chapter 11** Security, privacy and DPDP Act 2023 compliance design
- **Chapter 12** Evaluation design, including the 90-day cohabitation-survival ground-truth problem
- **§6.1** Integrity constraints (unordered-pair uniqueness on `MATCH_SCORE`, etc.) and six new entities: `MODERATOR`, `WEIGHT_SET`, `USER_ATTRIBUTE_WEIGHT`, `CONTACT_SHARE`, `USER_BLOCK`, `CONSENT_RECORD`

## Figures

Regenerated: `image2` (architecture), `image3` (component), `image7` (ERD, in
the root directory as before), `image8` (class), `image15` (Gantt), `image16`
(PERT/CPM).
New: `image17` (matching pipeline), `image18` (state models).
Unchanged: `image1`, `image4`–`image6`, `image9`–`image11`, `image12`–`image14`.

`figure-sources/` contains the scripts that generate them. `schedule.py` is the
single activity table behind both Figure 12.1 and Figure 12.2 — edit a duration
there and re-run `make_gantt.py` and `make_pert.py`, and the two figures cannot
drift apart again. Requires `matplotlib` and Graphviz (`dot`).

## Preamble change

Added `\usepackage[htt]{hyphenat}` and `\emergencystretch=3em` so that long
`\texttt{}` identifiers wrap instead of overflowing the margin.

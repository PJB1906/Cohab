# Datasheet — Cohab v2 study data

Following Gebru et al., "Datasheets for Datasets" (2021), abridged.

## Motivation

Collected to estimate how much each lifestyle attribute matters when people
choose a roommate (Cohab Lab), and to check whether Cohab's compatibility score
tracks real cohabitation (roommate pairs). Created by the Cohab project team
(M.Sc. Data Science, CHRIST University) as part of a trimester project.

## Composition

| Table | One row per | Contains |
| --- | --- | --- |
| `study_rater` | Lab participant | 21 lifestyle answers, up to 3 important attributes, optional coarse demographics, cohort label, consent version and time |
| `study_trial` | Trial shown | Card profiles exactly as displayed (generated, not real people), varied fields, repeat/attention metadata |
| `study_response` | Answer | Choice or ranking, confidence, would-message, optional 140-char reason, response time |
| `study_pair` / `study_pair_member` | Roommate pair / person | Lifestyle answers, roommate's-view ratings, 8 outcome items, months together, still together |

No names, emails, phone numbers, account IDs or IP addresses. Rows created by
the pipeline's dry run are marked `is_synthetic = true` and excluded from every
analysis of real data.

## Collection

Self-selected volunteers recruited through class groups, hostels and in-class
sessions at one campus. Web form, anonymous token. The Lab design is generated
per rater from a stored seed (`services/study/design.py`).

## Known biases

- One campus, mostly postgraduate students in Bengaluru: not representative of
  renters generally.
- Volunteers may be more agreeable or more interested in housing than average.
- Lab choices are stated preferences over vignettes, not lived compatibility.
- Roommate pairs are survivors: pairs who split quickly are under-represented.

## Preprocessing

Pre-registered exclusions (`docs/COHAB_HUMAN_STUDY.md` §5) applied before
analysis; counts reported. No imputation.

## Uses

Fitting and evaluating Cohab's attribute weights and calibration. Not suitable
for inferring anything about an individual, for any decision about a real
person outside Cohab's own ranked shortlist, or for population-level claims
about students' preferences.

## Distribution and maintenance

Not distributed. Aggregate results appear in the project report. Data can be
deleted with `python -m cohab.services.study.delete_data --all --yes`; a
participant's withdrawal deletes their rows immediately.

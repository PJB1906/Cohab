# Model card — Cohab matcher, v2

Following Mitchell et al., "Model Cards for Model Reporting" (2019), abridged.

## Model

A two-stage roommate matcher.

1. **Stage 1, hard constraints** (pass/fail): city, budget overlap, move-in
   within 30 days, mutual gender preference, seeker type, allergies, pets,
   indoor-smoking deal-breaker, blocks, settled pairs.
2. **Stage 2, directional scoring**: 20 attributes typed as similarity,
   tolerance, absolute, continuous or semantic; S(A→B) under A's weights and
   S(B→A) under B's, combined by harmonic mean. Each person's three "most
   important" attributes are boosted 1.5×.

Weight sets are immutable and versioned. v2 adds a *fitted* weight set
(Bradley–Terry on Cohab Lab choices, shrunk toward the expert prior) and an
optional isotonic calibration map to P(would message).

## Intended use

Producing a ranked, explained shortlist of possible roommates for a verified
student. The system ranks and explains; it never assigns, and it never releases
contact details without two separate consents.

## Out of scope

Assigning people to rooms; any decision about a person outside their own
shortlist; predicting whether a cohabitation will last (no outcome data exists
to support it).

## Factors

Gender, diet, budget band and seeker type are audited for Stage 1 pass rate and
exposure (`analysis/fairness.py`). Parity ratios outside 0.8–1.25 are flagged
for review, not asserted as discrimination: gaps can arise from what people ask
for (a gender preference, a budget) as much as from the system.

## Metrics

| What | Metric | Where |
| --- | --- | --- |
| Learned vs expert | Held-out pairwise log loss and accuracy, rater-bootstrap 95% CI | `docs/results/lab.json` |
| Ranking | Kendall τ on the six-card task | same |
| Calibration | ECE, Brier, reliability bins (out-of-fold) | same |
| Real pairs | Known-groups difference, Spearman ρ, permutation p | `docs/results/pairs.json` |
| Stability | Top-5 Jaccard, P(#1 changes) | `docs/results/rank_stability.json` |
| Policies | Welfare, match rate, overlap with oracle (simulation) | `docs/results/policy_comparison.json` |

Every stored result carries `data_source`: `real`, `dryrun` (synthetic, not
evidence), `simulation`, or `public`.

## Training data

Cohab Lab responses (see `DATASHEET_STUDY.md`). Expert prior: conflict
frequencies from the roommate-conflict literature (COHAB_MATCHING_SPEC.md §8).

## Caveats

- Self-reported answers are gameable; the roommate-pair study measures by how
  much, but the matcher cannot correct for it.
- Vignette choices are stated preference, not lived compatibility.
- Scores bunch (v1: 53% of eligible pairs in 0.70–0.80); adjacent ranks mean
  little, which is why the match screen says when the top three are tied.
- No claim is made that 90-day cohabitation improved. The instrumentation to
  measure it exists; the outcome cannot be observed within the project.

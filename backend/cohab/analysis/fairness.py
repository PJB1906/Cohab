"""Fairness audit: who gets seen, and which constraints cause it
(Cohab v2 plan W5, deck slide 27).

Descriptive only. A parity ratio outside [0.8, 1.25] is flagged for a human
to look at; it is never asserted to be discrimination, because group gaps
here can come from what people ask for (a gender preference, a budget) as
much as from the system.

Measures, per group (gender, diet, budget band, seeker type):
- Stage 1 pass rate: of all other people, the share for whom a member is
  eligible.
- Exposure: how many top-10 lists a member appears in under the expert
  policy, relative to the overall mean.
- Each hard constraint's marginal effect: how much the group's eligible
  pool grows when that one constraint is switched off.
- Counterfactual: drop the mutual gender-preference constraint and see who
  gains or loses pool size and exposure.
"""

from __future__ import annotations

import dataclasses
from typing import Callable

import numpy as np

from cohab.analysis.weights import EXPERT
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.vectorised import (
    ELIGIBLE,
    REASON_ORDER,
    Population,
    eligibility_reasons,
    score_population,
    top_k_fast,
)

PARITY_BAND = (0.8, 1.25)
LIST_K = 10


def budget_band(c: Candidate) -> str:
    mid = (c.budget_min + c.budget_max) / 2
    if mid < 10000:
        return "<10k"
    if mid < 15000:
        return "10-15k"
    if mid < 20000:
        return "15-20k"
    return "20k+"


GROUPINGS: dict[str, Callable[[Candidate], str]] = {
    "gender": lambda c: c.gender,
    "diet": lambda c: c.questionnaire.get("diet") or "unanswered",
    "budget_band": budget_band,
    "seeker_type": lambda c: c.seeker_type,
}


def _exposure(pop: Population, elig: np.ndarray) -> np.ndarray:
    sm = score_population(pop, EXPERT)
    exp = np.zeros(pop.n)
    for i in range(pop.n):
        for j in top_k_fast(i, sm.combined, elig, LIST_K):
            exp[j] += 1
    return exp


def _group_table(groups: np.ndarray, pass_rate: np.ndarray, exposure: np.ndarray) -> list[dict]:
    rows = []
    overall_pass = pass_rate.mean()
    overall_exp = exposure.mean()
    for g in sorted(set(groups.tolist())):
        m = groups == g
        pr = pass_rate[m].mean() / overall_pass if overall_pass else None
        er = exposure[m].mean() / overall_exp if overall_exp else None
        rows.append(
            {
                "group": g,
                "n": int(m.sum()),
                "stage1_pass_rate": float(pass_rate[m].mean()),
                "pass_rate_ratio": float(pr) if pr is not None else None,
                "mean_exposure": float(exposure[m].mean()),
                "exposure_ratio": float(er) if er is not None else None,
                "flag": bool(
                    (pr is not None and not PARITY_BAND[0] <= pr <= PARITY_BAND[1])
                    or (er is not None and not PARITY_BAND[0] <= er <= PARITY_BAND[1])
                ),
            }
        )
    return rows


def audit(cands: list[Candidate]) -> dict:
    pop = Population.from_candidates(cands)
    reasons = eligibility_reasons(pop)
    elig = reasons == ELIGIBLE
    # "Pass rate" for j: share of others for whom j is eligible (column).
    pass_rate = elig.sum(axis=0) / max(pop.n - 1, 1)
    exposure = _exposure(pop, elig)

    out: dict = {"n": pop.n, "parity_band": list(PARITY_BAND), "groupings": {}}
    for name, fn in GROUPINGS.items():
        groups = np.array([fn(c) for c in cands], dtype=object)
        table = _group_table(groups, pass_rate, exposure)
        # Marginal effect of each hard constraint: pool growth if it alone were lifted.
        marginal = {}
        for code, reason in enumerate(REASON_ORDER[:9]):
            freed = (reasons == code).sum(axis=1)  # subject-side pool gain
            marginal[reason] = {
                g: float(freed[groups == g].mean()) for g in sorted(set(groups.tolist()))
            }
        out["groupings"][name] = {"table": table, "constraint_marginal_pool_gain": marginal}

    # Counterfactual: drop mutual gender preference.
    cf_cands = [dataclasses.replace(c, gender_preference="any") for c in cands]
    cf_pop = Population.from_candidates(cf_cands)
    cf_elig = eligibility_reasons(cf_pop) == ELIGIBLE
    cf_exposure = _exposure(cf_pop, cf_elig)
    genders = np.array([c.gender for c in cands], dtype=object)
    pool = elig.sum(axis=1)
    cf_pool = cf_elig.sum(axis=1)
    out["counterfactual_no_gender_preference"] = [
        {
            "gender": g,
            "n": int((genders == g).sum()),
            "median_pool_before": float(np.median(pool[genders == g])),
            "median_pool_after": float(np.median(cf_pool[genders == g])),
            "mean_exposure_before": float(exposure[genders == g].mean()),
            "mean_exposure_after": float(cf_exposure[genders == g].mean()),
        }
        for g in sorted(set(genders.tolist()))
    ]
    out["share_with_gender_preference"] = float(np.mean([c.gender_preference != "any" for c in cands]))
    return out

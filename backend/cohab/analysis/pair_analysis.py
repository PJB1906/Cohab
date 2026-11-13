"""Roommate-pair validation (Cohab v2 plan W3).

Does the Cohab score track how real cohabitation went? Three analyses, all
with bootstrap intervals over pairs:

1. Known groups: mean score of satisfied pairs minus dissatisfied pairs, and
   the Spearman correlation between score and mean satisfaction.
2. Permutation null: real pairs against the same people randomly re-paired.
3. Self-report inflation: each person's own answer on the gameable items
   against how their roommate describes them.

Scores are computed with the full matcher (both directions, harmonic mean)
on the lifestyle attributes only: budget is held equal and interests/notes
are neutral, because the pair form does not ask them.

Stated limits (also written into every result): pairs who split up early are
under-sampled; answers are coloured by having lived together; n is small.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Mapping

import numpy as np
from scipy.stats import spearmanr

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.scoring import CompatibilityMatcher
from cohab.services.study.export import PairRecord
from cohab.services.study.instrument import (
    GAMEABLE_FIELDS,
    OUTCOME_ATTRIBUTE_MAP,
    SATISFIED_THRESHOLD,
)

LIMITATIONS = [
    "Survivorship: pairs who separated quickly are less likely to take part.",
    "Answers are given after living together and may be coloured by it.",
    "Small sample; intervals are wide and no correction for multiple comparisons is applied.",
]

# Most flattering option first (for directional inflation).
FLATTERING_ORDER: dict[str, list[str]] = {
    "cleanliness_level": ["very_tidy", "moderate", "relaxed"],
    "payment_reliability": ["early", "on_time", "needs_grace", "needs_reminding"],
    "noise_behaviour": ["quiet", "moderate", "loud"],
    "guest_frequency": ["rarely", "occasionally", "often", "partner_regular"],
}


def candidate_from_answers(answers: Mapping[str, str], important: list[str], uid: uuid.UUID) -> Candidate:
    return Candidate(
        user_id=uid,
        name="",
        gender="other",
        seeker_type="needs_place",
        verification_status="verified",
        account_status="active",
        city="-",
        budget_min=10000,
        budget_max=10000,
        move_in_date=date(2026, 1, 1),
        gender_preference="any",
        questionnaire=dict(answers),
        important_attributes=frozenset(important),
    )


def _boot_ci(values: np.ndarray, fn, n_boot: int, rng: np.random.Generator) -> list[float]:
    stats = []
    n = len(values)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        v = fn(idx)
        if v is not None and not np.isnan(v):
            stats.append(v)
    if not stats:
        return [float("nan"), float("nan")]
    return [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))]


def analyse_pairs(
    pairs: list[PairRecord], weights: Mapping[str, float], n_boot: int = 2000, n_perm: int = 5000, seed: int = 0
) -> dict:
    rng = np.random.default_rng(seed)
    n = len(pairs)
    if n < 4:
        return {"n_pairs": n, "status": "too_few_pairs", "limitations": LIMITATIONS}

    matcher = CompatibilityMatcher(dict(weights), uuid.uuid4())
    cand_a = [candidate_from_answers(p.a.answers, p.a.important, uuid.UUID(int=2 * i + 1)) for i, p in enumerate(pairs)]
    cand_b = [candidate_from_answers(p.b.answers, p.b.important, uuid.UUID(int=2 * i + 2)) for i, p in enumerate(pairs)]
    results = [matcher.score(a, b) for a, b in zip(cand_a, cand_b)]
    score = np.array([r.combined_score for r in results])
    satisfaction = np.array([(p.a.outcomes["overall_satisfaction"] + p.b.outcomes["overall_satisfaction"]) / 2 for p in pairs])
    satisfied = satisfaction >= SATISFIED_THRESHOLD

    # 1. Known groups.
    def diff(idx):
        s, g = score[idx], satisfied[idx]
        if g.all() or (~g).all():
            return None
        return float(s[g].mean() - s[~g].mean())

    def rho(idx):
        if np.ptp(satisfaction[idx]) == 0 or np.ptp(score[idx]) == 0:
            return None
        return float(spearmanr(score[idx], satisfaction[idx]).statistic)

    all_idx = np.arange(n)
    known_groups = {
        "n_satisfied": int(satisfied.sum()),
        "n_dissatisfied": int((~satisfied).sum()),
        "mean_score_satisfied": float(score[satisfied].mean()) if satisfied.any() else None,
        "mean_score_dissatisfied": float(score[~satisfied].mean()) if (~satisfied).any() else None,
        "difference": diff(all_idx),
        "difference_ci": _boot_ci(score, diff, n_boot, rng),
        "spearman_rho": rho(all_idx),
        "spearman_ci": _boot_ci(score, rho, n_boot, rng),
    }

    # 2. Permutation null: re-pair the a-people with shuffled b-people.
    sims = np.array([[matcher.score(a, b).combined_score for b in cand_b] for a in cand_a])
    real_mean = float(np.mean(np.diag(sims)))
    real_sat_mean = float(np.mean(np.diag(sims)[satisfied])) if satisfied.any() else None
    perm_means, perm_sat_means = [], []
    for _ in range(n_perm):
        perm = rng.permutation(n)
        vals = sims[np.arange(n), perm]
        perm_means.append(vals.mean())
        if satisfied.any():
            perm_sat_means.append(vals[satisfied].mean())
    perm_means = np.array(perm_means)
    permutation = {
        "real_mean": real_mean,
        "random_mean": float(perm_means.mean()),
        "random_95": [float(np.percentile(perm_means, 2.5)), float(np.percentile(perm_means, 97.5))],
        "p_value_one_sided": float((np.sum(perm_means >= real_mean) + 1) / (n_perm + 1)),
        "satisfied_real_mean": real_sat_mean,
        "satisfied_p_value_one_sided": (
            float((np.sum(np.array(perm_sat_means) >= real_sat_mean) + 1) / (n_perm + 1)) if real_sat_mean is not None else None
        ),
        "histogram": np.histogram(perm_means, bins=20)[0].tolist(),
        "histogram_edges": [float(e) for e in np.histogram(perm_means, bins=20)[1]],
    }

    # Attribute-level: each conflict item against its attribute cluster's score.
    attribute_level = {}
    for item, attrs in OUTCOME_ATTRIBUTE_MAP.items():
        cluster = []
        for r in results:
            vals = [(r.breakdown[a]["sim_a"] + r.breakdown[a]["sim_b"]) / 2 for a in attrs if a in r.breakdown]
            cluster.append(np.mean(vals) if vals else np.nan)
        cluster = np.array(cluster)
        outcome = np.array([(p.a.outcomes[item] + p.b.outcomes[item]) / 2 for p in pairs])
        ok = ~np.isnan(cluster)
        if ok.sum() >= 4 and np.ptp(cluster[ok]) > 0 and np.ptp(outcome[ok]) > 0:
            attribute_level[item] = {"attributes": list(attrs), "spearman_rho": float(spearmanr(cluster[ok], outcome[ok]).statistic), "n": int(ok.sum())}

    # 3. Self-report inflation.
    inflation = {}
    for f in GAMEABLE_FIELDS:
        selves, views = [], []
        for p in pairs:
            for me, other in ((p.a, p.b), (p.b, p.a)):
                selves.append(me.answers[f])
                views.append(other.roommate_ratings[f])
        agree = float(np.mean([s == v for s, v in zip(selves, views)]))
        entry = {"agreement": agree, "n": len(selves)}
        if f in FLATTERING_ORDER:
            order = FLATTERING_ORDER[f]
            d = np.array([order.index(v) - order.index(s) for s, v in zip(selves, views)], dtype=float)
            entry["mean_inflation_steps"] = float(d.mean())
            entry["inflation_ci"] = _boot_ci(d, lambda idx: float(d[idx].mean()), n_boot, rng)
            entry["share_self_more_flattering"] = float(np.mean(d > 0))
        inflation[f] = entry

    return {
        "n_pairs": n,
        "status": "ok",
        "known_groups": known_groups,
        "permutation": permutation,
        "attribute_level": attribute_level,
        "self_report_inflation": inflation,
        "months_together_median": float(np.median([p.a.months_together for p in pairs])),
        "share_still_together": float(np.mean([p.a.still_together and p.b.still_together for p in pairs])),
        "scores": [float(s) for s in score],
        "satisfaction": [float(s) for s in satisfaction],
        "limitations": LIMITATIONS,
    }

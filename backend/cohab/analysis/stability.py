"""Rank stability under weight uncertainty (Cohab v2 plan W4 / deck A3).

Given a population and a set of plausible weight vectors (bootstrap refits,
or a stated prior perturbation), how much does each person's top of the list
move? Reported as top-5 Jaccard overlap with the point-estimate ranking and
the probability that the #1 candidate changes.

`top3_tie_hint` is the per-user rule the match screen uses (D-14.9): the top
three are "effectively tied" when the same three people stay on top under
most plausible weights but their order among themselves does not.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from cohab.services.matching.vectorised import (
    AttributeMatrices,
    Population,
    attribute_matrices,
    blended_weights,
    directional_scores,
    eligible_mask,
    harmonic,
    top_k_fast,
)

TIE_SET_OVERLAP = 0.8  # top-3 set must stay this stable (Jaccard) ...
TIE_ORDER_CHANGE = 0.5  # ... while the order changes at least this often.


def dirichlet_prior_samples(weights: Mapping[str, float], n: int, concentration: float, seed: int = 0) -> list[dict]:
    """Perturbations of an expert weight set: Dirichlet(concentration * w).
    Larger concentration = more confidence in the expert values. A stated
    assumption, never presented as estimated from data."""
    names = list(weights)
    w = np.array([weights[k] for k in names])
    rng = np.random.default_rng(seed)
    return [dict(zip(names, map(float, s))) for s in rng.dirichlet(w * concentration, size=n)]


def _combined(pop: Population, am: AttributeMatrices, weights: Mapping[str, float]) -> np.ndarray:
    w = blended_weights(pop, weights, am.names)
    return harmonic(directional_scores(am, w))


def rank_stability(
    pop: Population,
    point: Mapping[str, float],
    samples: Sequence[Mapping[str, float]],
    k: int = 5,
    subjects: Sequence[int] | None = None,
) -> dict:
    names = tuple(n for n in point)
    am = attribute_matrices(pop, [n for n in names])
    elig = eligible_mask(pop)
    base = _combined(pop, am, point)
    subjects = list(subjects) if subjects is not None else [i for i in range(pop.n) if elig[i].sum() >= k + 1]
    base_top = {i: top_k_fast(i, base, elig, k) for i in subjects}

    jacc = {i: [] for i in subjects}
    first_changed = {i: 0 for i in subjects}
    for s in samples:
        comb = _combined(pop, am, s)
        for i in subjects:
            top = top_k_fast(i, comb, elig, k)
            a, b = set(base_top[i].tolist()), set(top.tolist())
            jacc[i].append(len(a & b) / len(a | b) if a | b else 1.0)
            if top.size and base_top[i].size and top[0] != base_top[i][0]:
                first_changed[i] += 1
    per_subject_j = np.array([np.mean(v) for v in jacc.values()]) if subjects else np.array([])
    per_subject_p1 = np.array([first_changed[i] / len(samples) for i in subjects]) if subjects else np.array([])
    return {
        "k": k,
        "n_subjects": len(subjects),
        "n_samples": len(samples),
        "topk_jaccard_mean": float(per_subject_j.mean()) if per_subject_j.size else None,
        "topk_jaccard_quantiles": [float(q) for q in np.quantile(per_subject_j, [0.1, 0.25, 0.5, 0.75, 0.9])]
        if per_subject_j.size
        else [],
        "p_first_changes_mean": float(per_subject_p1.mean()) if per_subject_p1.size else None,
        "share_first_changes_over_half": float(np.mean(per_subject_p1 > 0.5)) if per_subject_p1.size else None,
        "jaccard_histogram": np.histogram(per_subject_j, bins=10, range=(0, 1))[0].tolist() if per_subject_j.size else [],
    }


def top3_tie_hint(
    candidate_scores: Sequence[np.ndarray],
) -> dict:
    """`candidate_scores[s]` = combined scores of the same ordered candidate
    list (point-estimate order, best first) under weight sample s. Decides
    whether the top three should be shown as effectively tied."""
    if not candidate_scores or len(candidate_scores[0]) < 3:
        return {"tied": False, "set_overlap": None, "order_change": None}
    base = {0, 1, 2}
    overlaps, changed = [], 0
    for sc in candidate_scores:
        order = np.argsort(-np.asarray(sc), kind="stable")[:3].tolist()
        overlaps.append(len(base & set(order)) / len(base | set(order)))
        if order != [0, 1, 2]:
            changed += 1
    overlap = float(np.mean(overlaps))
    order_change = changed / len(candidate_scores)
    return {
        "tied": overlap >= TIE_SET_OVERLAP and order_change >= TIE_ORDER_CHANGE,
        "set_overlap": overlap,
        "order_change": order_change,
    }

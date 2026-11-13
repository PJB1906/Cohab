"""Power and recovery study (Cohab v2 plan W5, tier D item 1).

Question: how many raters does Cohab Lab need before learned weights reliably
beat the expert prior, and how does that depend on how real raters deviate
from the model? Answered entirely in SIMULATION, before any real rater:
this is the sample-size justification for the study, and the headline of
the no-human-data fallback.

For each scenario and rater count, repeat: simulate raters on the real
design, run the full pre-registered pipeline (lambda by grouped CV, grouped
5-fold evaluation, rater bootstrap), and record whether the learned-minus-
expert log-loss interval lies entirely below zero ("learned reliably
better"), and the correlation of learned weights with the planted truth.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from cohab.analysis.fitting import build_choice_data, cross_validate, fit_weights, summarise_cv
from cohab.analysis.simulate_raters import GroundTruth, simulate_raters
from cohab.analysis.weights import EXPERT_STUDY
from cohab.services.study.instrument import STUDY_ATTRIBUTES


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    truth: GroundTruth


def scenarios(seed: int = 0) -> list[Scenario]:
    rng = np.random.default_rng(seed)
    different = rng.dirichlet(EXPERT_STUDY * 15)  # plausible, but not the expert vector
    base = GroundTruth(weights=different, scale=14)
    return [
        Scenario("linear", "Linear, weights differ from expert", base),
        Scenario("expert_true", "Expert weights are the truth", replace(base, weights=EXPERT_STUDY.copy(), label="expert_true")),
        Scenario("noisy", "Noisier choices (half the scale)", replace(base, scale=7, label="noisy")),
        Scenario("attend4", "Raters attend to only 4 attributes", replace(base, attend_k=4, label="attend4")),
        Scenario("heterogeneous", "Raters differ (Dirichlet 30)", replace(base, heterogeneity=30, label="heterogeneous")),
        Scenario("interaction", "Unmodelled cleanliness x guests interaction", replace(base, interaction=0.3, label="interaction")),
        Scenario("inattentive", "15% inattentive raters, exclusions applied", replace(base, inattentive_share=0.15, label="inattentive")),
    ]


def one_rep(truth: GroundTruth, n_raters: int, seed: int, apply_exclusions: bool = True) -> dict:
    from cohab.analysis.reliability import apply_exclusions as excl

    raters = simulate_raters(n_raters, truth, seed=seed)
    if apply_exclusions:
        raters, _ = excl(raters)
    d = build_choice_data(raters)
    cv = cross_validate(d, k=5, seed=seed)
    s = summarise_cv(cv, n_boot=400, seed=seed)
    fit = fit_weights(d, cv.lam)
    diff = s["learned_minus_expert_log_loss"]
    return {
        "kept_raters": len(raters),
        "lambda": cv.lam,
        "learned_better": diff["ci"][1] < 0,
        "learned_worse": diff["ci"][0] > 0,
        "delta_log_loss": diff["estimate"],
        "delta_accuracy": s["learned_minus_expert_accuracy"]["estimate"],
        "weight_corr_truth": float(np.corrcoef(fit.weights, truth.weights)[0, 1]) if np.ptp(truth.weights) > 0 else None,
        "weight_l1_error": float(np.abs(fit.weights - truth.weights).sum()),
        "expert_l1_error": float(np.abs(EXPERT_STUDY - truth.weights).sum()),
    }


def power_curve(sizes: list[int], reps: int, seed: int = 0, keys: list[str] | None = None) -> dict:
    out = {"sizes": sizes, "reps": reps, "attributes": list(STUDY_ATTRIBUTES), "scenarios": []}
    for sc in scenarios(seed):
        if keys and sc.key not in keys:
            continue
        rows = []
        for n in sizes:
            reps_out = [one_rep(sc.truth, n, seed=seed * 100_000 + n * 1000 + r) for r in range(reps)]
            corr = [r["weight_corr_truth"] for r in reps_out if r["weight_corr_truth"] is not None]
            rows.append(
                {
                    "n_raters": n,
                    "p_learned_reliably_better": float(np.mean([r["learned_better"] for r in reps_out])),
                    "p_learned_reliably_worse": float(np.mean([r["learned_worse"] for r in reps_out])),
                    "mean_delta_log_loss": float(np.mean([r["delta_log_loss"] for r in reps_out])),
                    "mean_delta_accuracy": float(np.mean([r["delta_accuracy"] for r in reps_out])),
                    "mean_weight_corr_truth": float(np.mean(corr)) if corr else None,
                    "mean_weight_l1_error": float(np.mean([r["weight_l1_error"] for r in reps_out])),
                    "expert_l1_error": float(reps_out[0]["expert_l1_error"]),
                    "median_lambda": float(np.median([r["lambda"] for r in reps_out])),
                }
            )
        out["scenarios"].append({"key": sc.key, "label": sc.label, "rows": rows})
    return out


def minimum_raters(curve: dict, key: str = "linear", power: float = 0.8) -> int | None:
    sc = next(s for s in curve["scenarios"] if s["key"] == key)
    for row in sc["rows"]:
        if row["p_learned_reliably_better"] >= power:
            return row["n_raters"]
    return None

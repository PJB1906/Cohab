"""Calibration: from a directional score to "would message" probability
(Cohab v2 plan W4 / deck A3, with the target correction from the plan).

The only probability the study can support is one-sided: P(rater would
message this person | S(rater -> person)). Mutual interest needs live match
data and 90-day cohabitation needs outcomes; neither exists, so neither is
shown (docs/DECISIONS.md D-14.8).

Isotonic regression is fitted out-of-fold (grouped by rater) for every
reported metric; the deployable map is then fitted on all data and stored as
piecewise-linear knots, applied with `np.interp` at request time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression

from cohab.analysis.fitting import _folds, fit_weights, importance_matrix
from cohab.services.study.export import RaterRecord
from cohab.services.study.features import card_vector
from cohab.services.study.instrument import STUDY_ATTRIBUTES

K = len(STUDY_ATTRIBUTES)


@dataclass
class MessageData:
    V: np.ndarray  # n x K: s(R -> card)
    I: np.ndarray  # n x K importance indicators
    y: np.ndarray  # 1 if rater would message this card
    rater: np.ndarray


def build_message_data(raters: list[RaterRecord]) -> MessageData:
    V, I, y, who = [], [], [], []
    for ri, r in enumerate(raters):
        imp = importance_matrix(r.important)
        for t in r.trials:
            if t.kind != "pair" or not t.would_message:
                continue
            for cid, wants in t.would_message.items():
                V.append(card_vector(r.answers, t.cards[cid]))
                I.append(imp)
                y.append(1.0 if wants else 0.0)
                who.append(ri)
    return MessageData(np.array(V).reshape(-1, K), np.array(I).reshape(-1, K), np.array(y), np.array(who, dtype=int))


def directional_score(weights: np.ndarray, multiplier: float, V: np.ndarray, I: np.ndarray) -> np.ndarray:
    """S(R -> card) on [0, 1]: the importance-blended weights, renormalised per
    rater, as the matcher computes them."""
    w = weights[None, :] * (1 + (multiplier - 1) * I)
    w = w / w.sum(axis=1, keepdims=True)
    return np.sum(w * V, axis=1)


def fit_isotonic(score: np.ndarray, y: np.ndarray) -> IsotonicRegression:
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip", increasing=True)
    iso.fit(score, y)
    return iso


def knots(iso: IsotonicRegression) -> dict[str, list[float]]:
    return {"x": [float(v) for v in iso.X_thresholds_], "y": [float(v) for v in iso.y_thresholds_]}


def apply_knots(k: dict[str, list[float]], score: float | np.ndarray) -> float | np.ndarray:
    return np.interp(score, k["x"], k["y"])


def reliability_bins(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> list[dict]:
    edges = np.linspace(0, 1, n_bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.any():
            out.append({"lo": float(lo), "hi": float(hi), "n": int(m.sum()), "mean_p": float(p[m].mean()), "observed": float(y[m].mean())})
    return out


def calibration_metrics(p: np.ndarray, y: np.ndarray) -> dict:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    bins = reliability_bins(p, y)
    n = len(y)
    ece = sum(b["n"] / n * abs(b["mean_p"] - b["observed"]) for b in bins)
    logit = np.log(p / (1 - p))
    # Calibration slope/intercept: logistic regression of y on logit(p).
    from scipy.optimize import minimize

    def obj(theta):
        z = theta[0] + theta[1] * logit
        return float(np.sum(np.logaddexp(0, z) - y * z))

    res = minimize(obj, np.array([0.0, 1.0]), method="BFGS")
    return {
        "n": int(n),
        "ece": float(ece),
        "brier": float(np.mean((p - y) ** 2)),
        "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        "base_rate": float(y.mean()),
        "intercept": float(res.x[0]),
        "slope": float(res.x[1]),
        "bins": bins,
    }


def cross_validated_calibration(
    raters: list[RaterRecord], choice_data, lam: float, k: int = 5, seed: int = 0
) -> dict:
    """Out-of-fold: weights fitted on training raters' choices, isotonic map
    fitted on training raters' would-message labels, both applied to the
    held-out raters. Compared against the raw score used as a probability."""
    md = build_message_data(raters)
    raters_idx = np.unique(md.rater)
    folds = _folds(len(raters_idx), min(k, len(raters_idx)), seed)
    p_cal = np.full(len(md.y), np.nan)
    raw = np.full(len(md.y), np.nan)
    for f in folds:
        test = np.isin(md.rater, raters_idx[f])
        train_choices = np.isin(choice_data.rater, raters_idx[f], invert=True)
        fit = fit_weights(choice_data.subset(train_choices), lam)
        s_train = directional_score(fit.weights, fit.multiplier, md.V[~test], md.I[~test])
        s_test = directional_score(fit.weights, fit.multiplier, md.V[test], md.I[test])
        iso = fit_isotonic(s_train, md.y[~test])
        p_cal[test] = iso.predict(s_test)
        raw[test] = s_test
    return {"calibrated": calibration_metrics(p_cal, md.y), "raw_score_as_probability": calibration_metrics(raw, md.y)}


def final_calibration(raters: list[RaterRecord], weights: np.ndarray, multiplier: float) -> dict:
    md = build_message_data(raters)
    s = directional_score(weights, multiplier, md.V, md.I)
    iso = fit_isotonic(s, md.y)
    return {"knots": knots(iso), "n": int(len(md.y))}

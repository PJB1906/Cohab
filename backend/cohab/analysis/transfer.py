"""Transfer test on public two-sided choice data (Cohab v2 plan, tier D item 4).

Dataset: the Columbia speed-dating experiment (Fisman, Iyengar, Kamenica and
Simonson, 2006), in its widely distributed CSV form ("Speed Dating
Data.csv", one row per person per date). It is not roommate data. It is used
because it is real, two-sided and records each person's *stated* attribute
importance alongside their ratings of each partner and both decisions —
exactly the structure needed to test two Cohab design claims:

1. Combining two directional scores: does the harmonic mean predict a mutual
   "yes" better than the arithmetic mean? (Cohab spec §6.3.)
2. Stated versus revealed weights: do weights people *say* matter predict
   their decisions as well as weights learned from their choices? (The
   expert-prior versus learned question of W4, on real people.)

What this validates is the reciprocal-scoring machinery and the shrinkage
logic, not Cohab's roommate weights. Reported with `data_source="public"`.

The file is not shipped in the repository. `reproduce` looks for it at
`data/public/speed_dating.csv` and records "not available" if absent.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ATTRS = ("attr", "sinc", "intel", "fun", "amb", "shar")
STATED = tuple(f"{a}1_1" for a in ATTRS)  # what you look for (points)
PARTNER_STATED = ("pf_o_att", "pf_o_sin", "pf_o_int", "pf_o_fun", "pf_o_amb", "pf_o_sha")
RATING = ATTRS  # my rating of the partner, 1-10
PARTNER_RATING = tuple(f"{a}_o" for a in ATTRS)  # partner's rating of me
REQUIRED = ("iid", "pid", "wave", "dec", "dec_o", "match") + STATED + PARTNER_STATED + RATING + PARTNER_RATING


@dataclass
class Dates:
    iid: np.ndarray
    pid: np.ndarray
    wave: np.ndarray
    dec: np.ndarray
    dec_o: np.ndarray
    match: np.ndarray
    stated: np.ndarray  # n x 6, rows sum to 1
    partner_stated: np.ndarray
    rating: np.ndarray  # n x 6, scaled to [0, 1]
    partner_rating: np.ndarray
    n_dropped: int


def _f(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def load(path: str | Path) -> Dates:
    with open(path, newline="", encoding="latin-1") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in REQUIRED if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"not the Columbia speed-dating format; missing columns {missing}")
        rows = list(reader)
    cols = {c: np.array([_f(r[c]) for r in rows]) for c in REQUIRED}
    ok = np.all([~np.isnan(cols[c]) for c in REQUIRED], axis=0)

    def mat(names):
        return np.column_stack([cols[c][ok] for c in names])

    stated, pstated = mat(STATED), mat(PARTNER_STATED)
    good = (stated.sum(axis=1) > 0) & (pstated.sum(axis=1) > 0)
    stated, pstated = stated[good], pstated[good]
    sel = np.flatnonzero(ok)[good]

    def col(c):
        return cols[c][sel]

    return Dates(
        iid=col("iid").astype(int),
        pid=col("pid").astype(int),
        wave=col("wave").astype(int),
        dec=col("dec"),
        dec_o=col("dec_o"),
        match=col("match"),
        stated=stated / stated.sum(axis=1, keepdims=True),
        partner_stated=pstated / pstated.sum(axis=1, keepdims=True),
        rating=np.clip(mat(RATING)[good] / 10, 0, 1),
        partner_rating=np.clip(mat(PARTNER_RATING)[good] / 10, 0, 1),
        n_dropped=int(len(rows) - len(sel)),
    )


def auc(score: np.ndarray, y: np.ndarray) -> float:
    """Mann-Whitney AUC with average ranks for ties."""
    from scipy.stats import rankdata

    pos = y == 1
    n1, n0 = pos.sum(), (~pos).sum()
    if n1 == 0 or n0 == 0:
        return float("nan")
    r = rankdata(score)
    return float((r[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def _cluster_boot(fn, clusters: np.ndarray, n_boot: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    ids = np.unique(clusters)
    index = {c: np.flatnonzero(clusters == c) for c in ids}
    stats = []
    for _ in range(n_boot):
        rows = np.concatenate([index[c] for c in rng.choice(ids, size=len(ids), replace=True)])
        v = fn(rows)
        if not np.isnan(v):
            stats.append(v)
    return [float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))]


def reciprocal_combination(d: Dates, n_boot: int = 1000, seed: int = 0) -> dict:
    """One row per unordered date. S(i->j) = stated_i . rating_i(j)."""
    s_ij = np.sum(d.stated * d.rating, axis=1)
    s_ji = np.sum(d.partner_stated * d.partner_rating, axis=1)
    keep = d.iid < d.pid  # each date appears twice in the file
    s_ij, s_ji, y, cl = s_ij[keep], s_ji[keep], d.match[keep], d.iid[keep]
    combos = {
        "arithmetic": (s_ij + s_ji) / 2,
        "harmonic": np.where(s_ij + s_ji > 0, 2 * s_ij * s_ji / np.maximum(s_ij + s_ji, 1e-12), 0),
        "geometric": np.sqrt(s_ij * s_ji),
        "min": np.minimum(s_ij, s_ji),
    }
    out = {"n_dates": int(keep.sum()), "match_rate": float(y.mean()), "auc": {}}
    for name, sc in combos.items():
        out["auc"][name] = {"auc": auc(sc, y), "ci": _cluster_boot(lambda r, sc=sc: auc(sc[r], y[r]), cl, n_boot, seed)}
    diff = lambda r: auc(combos["harmonic"][r], y[r]) - auc(combos["arithmetic"][r], y[r])  # noqa: E731
    out["harmonic_minus_arithmetic"] = {"estimate": diff(np.arange(len(y))), "ci": _cluster_boot(diff, cl, n_boot, seed + 1)}
    return out


def _logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-3) -> np.ndarray:
    Xb = np.column_stack([np.ones(len(X)), X])

    def obj(b):
        z = Xb @ b
        return float(np.sum(np.logaddexp(0, z) - y * z) + l2 * b[1:] @ b[1:]), Xb.T @ (1 / (1 + np.exp(-z)) - y) + np.concatenate([[0], 2 * l2 * b[1:]])

    return minimize(obj, np.zeros(Xb.shape[1]), jac=True, method="L-BFGS-B").x


def _predict(b: np.ndarray, X: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-(b[0] + X @ b[1:])))


def stated_vs_revealed(d: Dates, k: int = 5, n_boot: int = 1000, seed: int = 0) -> dict:
    """Predict each person's own decision from their ratings of the partner.
    Stated: score = stated_i . rating (one feature, scale + intercept fitted).
    Revealed: logistic regression on the six ratings, pooled. Grouped CV by
    person, so a person's dates are never on both sides of a split."""
    people = np.unique(d.iid)
    rng = np.random.default_rng(seed)
    folds = np.array_split(rng.permutation(people), k)
    p_stated = np.zeros(len(d.dec))
    p_revealed = np.zeros(len(d.dec))
    s_stated = np.sum(d.stated * d.rating, axis=1)[:, None]
    revealed_weights = []
    for f in folds:
        test = np.isin(d.iid, f)
        b1 = _logistic(s_stated[~test], d.dec[~test])
        p_stated[test] = _predict(b1, s_stated[test])
        b2 = _logistic(d.rating[~test], d.dec[~test])
        p_revealed[test] = _predict(b2, d.rating[test])
        revealed_weights.append(b2[1:])
    y = d.dec

    def ll(p, r):
        p = np.clip(p[r], 1e-9, 1 - 1e-9)
        return float(-np.mean(y[r] * np.log(p) + (1 - y[r]) * np.log(1 - p)))

    all_r = np.arange(len(y))
    rw = np.mean(revealed_weights, axis=0)
    rw_pos = np.clip(rw, 0, None)
    return {
        "n_dates": int(len(y)),
        "n_people": int(len(people)),
        "stated": {"auc": auc(p_stated, y), "log_loss": ll(p_stated, all_r)},
        "revealed": {"auc": auc(p_revealed, y), "log_loss": ll(p_revealed, all_r)},
        "revealed_minus_stated_auc": {
            "estimate": auc(p_revealed, y) - auc(p_stated, y),
            "ci": _cluster_boot(lambda r: auc(p_revealed[r], y[r]) - auc(p_stated[r], y[r]), d.iid, n_boot, seed),
        },
        "mean_stated_weights": dict(zip(ATTRS, map(float, d.stated.mean(axis=0)))),
        "revealed_weights_normalised": dict(zip(ATTRS, map(float, rw_pos / rw_pos.sum()))) if rw_pos.sum() > 0 else None,
    }


def run(path: str | Path, n_boot: int = 1000) -> dict:
    p = Path(path)
    if not p.is_file():
        return {
            "status": "not_available",
            "expected_path": str(p),
            "how_to_get": "Download the Columbia speed-dating CSV ('Speed Dating Data.csv') and save it at the path above.",
        }
    d = load(p)
    return {
        "status": "ok",
        "source": "Fisman, Iyengar, Kamenica & Simonson (2006), Columbia speed-dating experiment",
        "rows_used": int(len(d.dec)),
        "rows_dropped_missing": d.n_dropped,
        "reciprocal": reciprocal_combination(d, n_boot=n_boot),
        "stated_vs_revealed": stated_vs_revealed(d, n_boot=n_boot),
        "caveat": "Romantic speed dates, not roommates: this tests the scoring machinery, not Cohab's weights.",
    }

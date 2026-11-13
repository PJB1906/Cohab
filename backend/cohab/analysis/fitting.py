"""Learning attribute weights from pairwise choices (Cohab v2 plan W4).

Model (Bradley-Terry / conditional logit over designed pairs):

    P(rater R picks card A over B) = sigma( sum_k beta_k * m_Rk * [s_k(R->A) - s_k(R->B)] )

- s_k(R->X) is the matcher's own directional score for attribute k.
- beta_k >= 0, so no attribute can ever reward a conflict.
- m_Rk = (1 + gamma) if R marked k as one of their three most important
  attributes, else 1. v1 hard-codes 1 + gamma = 1.5; here it is estimated.
- Regularisation shrinks beta toward the *expert* prior tau0 * w_expert, not
  toward zero: with little data the fit returns the expert weights, with more
  data it moves away from them (docs/DECISIONS.md D-14.4).

Learned weights are beta / sum(beta). Evaluation is grouped by rater: a
rater's trials are never split across train and test.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize, minimize_scalar

from cohab.analysis.weights import EXPERT_STUDY
from cohab.services.study.export import RaterRecord
from cohab.services.study.features import card_vector
from cohab.services.study.instrument import STUDY_ATTRIBUTES

V1_MULTIPLIER = 1.5
LAMBDA_GRID = (0.3, 1.0, 3.0, 10.0, 30.0, 100.0)
K = len(STUDY_ATTRIBUTES)


# --- data -------------------------------------------------------------------


@dataclass
class ChoiceData:
    """One row per answered pair trial with a preference (no "none")."""

    X: np.ndarray  # n x K feature differences s(R->A) - s(R->B)
    I: np.ndarray  # n x K, 1 where the rater marked attribute k important
    y: np.ndarray  # n, 1 if card A was chosen
    rater: np.ndarray  # n, rater index
    rater_ids: list[str]
    n_none: int = 0

    def subset(self, mask: np.ndarray) -> "ChoiceData":
        return ChoiceData(self.X[mask], self.I[mask], self.y[mask], self.rater[mask], self.rater_ids)

    def raters_subset(self, idx: np.ndarray) -> "ChoiceData":
        """Rows for the given rater indices, with repetition (for the bootstrap)."""
        parts = [np.flatnonzero(self.rater == r) for r in idx]
        rows = np.concatenate(parts) if parts else np.array([], dtype=int)
        return ChoiceData(self.X[rows], self.I[rows], self.y[rows], self.rater[rows], self.rater_ids)


def importance_matrix(important: list[str]) -> np.ndarray:
    return np.array([1.0 if a in important else 0.0 for a in STUDY_ATTRIBUTES])


def build_choice_data(raters: list[RaterRecord], kinds: tuple[str, ...] = ("pair",)) -> ChoiceData:
    X, I, y, who = [], [], [], []
    n_none = 0
    for ri, r in enumerate(raters):
        imp = importance_matrix(r.important)
        for t in r.trials:
            if t.kind not in kinds:
                continue
            if t.chosen is None:
                n_none += 1
                continue
            a, b = sorted(t.cards)  # "A", "B"
            X.append(card_vector(r.answers, t.cards[a]) - card_vector(r.answers, t.cards[b]))
            I.append(imp)
            y.append(1.0 if t.chosen == a else 0.0)
            who.append(ri)
    return ChoiceData(
        np.array(X).reshape(-1, K),
        np.array(I).reshape(-1, K),
        np.array(y),
        np.array(who, dtype=int),
        [r.rater_id for r in raters],
        n_none,
    )


# --- model ------------------------------------------------------------------


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def logits(beta: np.ndarray, gamma: float, X: np.ndarray, I: np.ndarray) -> np.ndarray:
    return X @ beta + gamma * ((I * X) @ beta)


def nll(beta: np.ndarray, gamma: float, d: ChoiceData) -> float:
    z = logits(beta, gamma, d.X, d.I)
    return float(np.sum(np.logaddexp(0, z) - d.y * z))


@dataclass
class Fit:
    beta: np.ndarray
    gamma: float
    lam: float
    tau0: float

    @property
    def weights(self) -> np.ndarray:
        s = self.beta.sum()
        return self.beta / s if s > 0 else np.full(len(self.beta), 1 / len(self.beta))

    @property
    def multiplier(self) -> float:
        return 1.0 + self.gamma

    def predict(self, X: np.ndarray, I: np.ndarray) -> np.ndarray:
        return _sigmoid(logits(self.beta, self.gamma, X, I))


def fit_scale(direction: np.ndarray, d: ChoiceData, gamma: float = 0.0) -> float:
    """Best logit scale tau for a fixed weight direction (1-D, tau >= 0)."""
    if len(d.y) == 0:
        return 0.0
    z0 = logits(direction, gamma, d.X, d.I)
    res = minimize_scalar(
        lambda t: float(np.sum(np.logaddexp(0, t * z0) - d.y * t * z0)), bounds=(0.0, 500.0), method="bounded"
    )
    return float(res.x)


def fit_weights(
    d: ChoiceData,
    lam: float,
    prior: np.ndarray = EXPERT_STUDY,
    *,
    fit_gamma: bool = True,
    gamma0: float = V1_MULTIPLIER - 1,
) -> Fit:
    tau0 = fit_scale(prior, d, gamma0)
    beta0 = tau0 * prior
    # Penalty is scaled by the number of rows so lambda means roughly the
    # same thing at 200 and 2,000 comparisons.
    n = max(len(d.y), 1)

    k = d.X.shape[1]

    def obj(theta: np.ndarray) -> tuple[float, np.ndarray]:
        beta, gamma = theta[:k], theta[k] if fit_gamma else gamma0
        a = d.X @ beta
        b = (d.I * d.X) @ beta
        z = a + gamma * b
        p = _sigmoid(z)
        r = p - d.y
        diff = beta - beta0
        f = float(np.sum(np.logaddexp(0, z) - d.y * z)) + lam * n * float(diff @ diff) / max(tau0**2, 1e-6)
        g_beta = d.X.T @ r + gamma * ((d.I * d.X).T @ r) + 2 * lam * n * diff / max(tau0**2, 1e-6)
        g_gamma = float(b @ r)
        return f, np.concatenate([g_beta, [g_gamma if fit_gamma else 0.0]])

    theta0 = np.concatenate([beta0, [gamma0]])
    bounds = [(0.0, None)] * k + [((-0.9, 4.0) if fit_gamma else (gamma0, gamma0))]
    res = minimize(obj, theta0, jac=True, method="L-BFGS-B", bounds=bounds)
    return Fit(beta=res.x[:k], gamma=float(res.x[k]), lam=lam, tau0=tau0)


# --- baselines ----------------------------------------------------------------


@dataclass
class Scorer:
    """Anything that turns ChoiceData into P(A chosen)."""

    name: str
    predict: callable


def train_scorers(train: ChoiceData, lam: float) -> dict[str, Scorer]:
    scorers: dict[str, Scorer] = {"random": Scorer("random", lambda d: np.full(len(d.y), 0.5))}

    uniform = np.full(K, 1 / K)
    tu = fit_scale(uniform, train)
    scorers["uniform"] = Scorer("uniform", lambda d, t=tu: _sigmoid(t * (d.X @ uniform)))

    best_k, best_nll, best_t = 0, np.inf, 0.0
    for k in range(K):
        e = np.zeros(K)
        e[k] = 1
        t = fit_scale(e, train)
        v = nll(t * e, 0.0, train)
        if v < best_nll:
            best_k, best_nll, best_t = k, v, t
    scorers["single_attribute"] = Scorer(
        f"single:{STUDY_ATTRIBUTES[best_k]}", lambda d, k=best_k, t=best_t: _sigmoid(t * d.X[:, k])
    )

    te = fit_scale(EXPERT_STUDY, train, V1_MULTIPLIER - 1)
    scorers["expert"] = Scorer(
        "expert", lambda d, t=te: _sigmoid(logits(t * EXPERT_STUDY, V1_MULTIPLIER - 1, d.X, d.I))
    )

    learned = fit_weights(train, lam)
    scorers["learned"] = Scorer("learned", lambda d, f=learned: f.predict(d.X, d.I))
    return scorers


# --- evaluation -----------------------------------------------------------------


def _folds(n_raters: int, k: int, seed: int) -> list[np.ndarray]:
    rng = np.random.default_rng(seed)
    order = rng.permutation(n_raters)
    return [order[i::k] for i in range(k)]


def choose_lambda(d: ChoiceData, k: int = 5, seed: int = 0, grid: tuple[float, ...] = LAMBDA_GRID) -> float:
    """Grouped-CV log loss over the grid; ties go to the larger lambda (more
    shrinkage toward the expert prior)."""
    raters = np.unique(d.rater)
    if len(raters) < k:
        return max(grid)
    folds = _folds(len(raters), k, seed)
    scores = []
    for lam in grid:
        total = 0.0
        for f in folds:
            test_r = raters[f]
            test = np.isin(d.rater, test_r)
            fit = fit_weights(d.subset(~test), lam)
            p = np.clip(fit.predict(d.X[test], d.I[test]), 1e-9, 1 - 1e-9)
            total += float(-np.sum(d.y[test] * np.log(p) + (1 - d.y[test]) * np.log(1 - p)))
        scores.append(total)
    best = min(scores)
    return max(lam for lam, s in zip(grid, scores) if s <= best * 1.0005)


@dataclass
class CVResult:
    lam: float
    per_rater: dict[str, dict[str, dict[str, float]]]  # scorer -> rater -> {acc, ll, n}
    oof: dict[str, np.ndarray]  # scorer -> out-of-fold P(A), aligned with data rows
    single_attribute_names: list[str] = field(default_factory=list)


def cross_validate(d: ChoiceData, k: int = 5, seed: int = 0, lam: float | None = None) -> CVResult:
    raters = np.unique(d.rater)
    k = min(k, len(raters))
    lam = lam if lam is not None else choose_lambda(d, k=k, seed=seed + 1)
    folds = _folds(len(raters), k, seed)
    oof: dict[str, np.ndarray] = {}
    singles = []
    for f in folds:
        test = np.isin(d.rater, raters[f])
        scorers = train_scorers(d.subset(~test), lam)
        singles.append(scorers["single_attribute"].name)
        for name, s in scorers.items():
            oof.setdefault(name, np.full(len(d.y), np.nan))[test] = s.predict(d.subset(test))
    per_rater: dict[str, dict[str, dict[str, float]]] = {}
    for name, p in oof.items():
        per_rater[name] = {}
        for r in raters:
            m = d.rater == r
            if not m.any():
                continue
            pr = np.clip(p[m], 1e-9, 1 - 1e-9)
            per_rater[name][d.rater_ids[r]] = {
                "acc": float(np.mean((pr > 0.5) == (d.y[m] == 1)) if np.any(pr != 0.5) else 0.5),
                "ll": float(-np.mean(d.y[m] * np.log(pr) + (1 - d.y[m]) * np.log(1 - pr))),
                "n": int(m.sum()),
            }
    return CVResult(lam, per_rater, oof, singles)


def _weighted_mean(per_rater: dict[str, dict[str, float]], key: str, ids: list[str]) -> float:
    n = sum(per_rater[i]["n"] for i in ids)
    return sum(per_rater[i][key] * per_rater[i]["n"] for i in ids) / n if n else float("nan")


def summarise_cv(cv: CVResult, n_boot: int = 2000, seed: int = 0) -> dict:
    """Accuracy and log loss per scorer with rater-bootstrap intervals, plus
    the pre-registered primary comparison: learned minus expert."""
    rng = np.random.default_rng(seed)
    ids = list(cv.per_rater["learned"].keys())
    samples = [list(rng.choice(ids, size=len(ids), replace=True)) for _ in range(n_boot)]
    out: dict = {"lambda": cv.lam, "n_raters": len(ids), "scorers": {}}
    for name, pr in cv.per_rater.items():
        acc = _weighted_mean(pr, "acc", ids)
        ll = _weighted_mean(pr, "ll", ids)
        bacc = [_weighted_mean(pr, "acc", s) for s in samples]
        bll = [_weighted_mean(pr, "ll", s) for s in samples]
        out["scorers"][name] = {
            "accuracy": acc,
            "accuracy_ci": [float(np.percentile(bacc, 2.5)), float(np.percentile(bacc, 97.5))],
            "log_loss": ll,
            "log_loss_ci": [float(np.percentile(bll, 2.5)), float(np.percentile(bll, 97.5))],
        }
    for metric in ("acc", "ll"):
        diffs = [
            _weighted_mean(cv.per_rater["learned"], metric, s) - _weighted_mean(cv.per_rater["expert"], metric, s)
            for s in samples
        ]
        point = _weighted_mean(cv.per_rater["learned"], metric, ids) - _weighted_mean(
            cv.per_rater["expert"], metric, ids
        )
        key = "accuracy" if metric == "acc" else "log_loss"
        out[f"learned_minus_expert_{key}"] = {
            "estimate": point,
            "ci": [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))],
        }
    single_counts: dict[str, int] = {}
    for s in cv.single_attribute_names:
        single_counts[s] = single_counts.get(s, 0) + 1
    out["single_attribute_chosen"] = single_counts
    return out


def bootstrap_weights(d: ChoiceData, lam: float, n_boot: int = 500, seed: int = 0) -> np.ndarray:
    """Refit on raters resampled with replacement. Returns n_boot x K weights."""
    rng = np.random.default_rng(seed)
    raters = np.unique(d.rater)
    out = np.empty((n_boot, K))
    for b in range(n_boot):
        sample = rng.choice(raters, size=len(raters), replace=True)
        out[b] = fit_weights(d.raters_subset(sample), lam).weights
    return out


def bootstrap_multiplier(d: ChoiceData, lam: float, n_boot: int = 300, seed: int = 0) -> list[float]:
    rng = np.random.default_rng(seed)
    raters = np.unique(d.rater)
    return [
        fit_weights(d.raters_subset(rng.choice(raters, size=len(raters), replace=True)), lam).multiplier
        for _ in range(n_boot)
    ]


# --- rank task -----------------------------------------------------------------


def kendall_tau(order_true: list[str], scores: dict[str, float]) -> float:
    """Kendall tau-a between a rater's ranking (best first) and model scores."""
    pos = {c: i for i, c in enumerate(order_true)}
    items = list(order_true)
    conc = disc = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]  # rater prefers a over b
            diff = scores[a] - scores[b]
            if diff > 0:
                conc += 1
            elif diff < 0:
                disc += 1
    n = len(items) * (len(items) - 1) / 2
    return (conc - disc) / n if n else float("nan")


def rank_task_taus(raters: list[RaterRecord], weights: np.ndarray, multiplier: float) -> list[float]:
    taus = []
    for r in raters:
        imp = importance_matrix(r.important)
        w = weights * (1 + (multiplier - 1) * imp)
        for t in r.trials:
            if t.kind == "rank" and t.ranking:
                scores = {cid: float(card_vector(r.answers, c) @ w) for cid, c in t.cards.items()}
                taus.append(kendall_tau(t.ranking, scores))
    return taus


# --- learning curve -------------------------------------------------------------


def learning_curve(d: ChoiceData, sizes: list[int], repeats: int = 5, seed: int = 0, lam: float = 10.0) -> list[dict]:
    """Held-out accuracy of learned vs expert as the number of training raters
    grows (test set: the raters not sampled). Shows whether more data helps."""
    rng = np.random.default_rng(seed)
    raters = np.unique(d.rater)
    out = []
    for n in sizes:
        if n >= len(raters):
            continue
        acc_l, acc_e = [], []
        for _ in range(repeats):
            train_r = rng.choice(raters, size=n, replace=False)
            train = np.isin(d.rater, train_r)
            test = ~train
            sc = train_scorers(d.subset(train), lam)
            te = d.subset(test)
            for name, sink in (("learned", acc_l), ("expert", acc_e)):
                p = sc[name].predict(te)
                sink.append(float(np.mean((p > 0.5) == (te.y == 1))))
        out.append(
            {
                "n_raters": int(n),
                "learned_accuracy": float(np.mean(acc_l)),
                "expert_accuracy": float(np.mean(acc_e)),
                "learned_sd": float(np.std(acc_l)),
            }
        )
    return out


# --- tier B: clusters instead of 17 free weights ---------------------------------

# Six clusters matching the deck's grouping (slide 8). Within a cluster the
# expert proportions are kept; only the cluster totals are learned.
CLUSTERS: dict[str, tuple[str, ...]] = {
    "cleanliness_chores_sharing": ("cleanliness_level", "chore_approach", "sharing_norm"),
    "sleep_noise": ("sleep_schedule", "noise"),
    "money": ("payment_reliability", "cost_split_preference"),
    "guests": ("guests",),
    "communication": ("communication_style",),
    "food_habits_rhythm": (
        "diet", "nonveg_cooking", "smoking", "alcohol", "life_stage", "daytime_presence", "home_orientation", "sociability",
    ),
}


def cluster_matrix(prior: np.ndarray = EXPERT_STUDY) -> tuple[np.ndarray, list[str]]:
    """K x C map: column c holds the expert proportions of cluster c."""
    names = list(CLUSTERS)
    M = np.zeros((K, len(names)))
    for c, cname in enumerate(names):
        idx = [STUDY_ATTRIBUTES.index(a) for a in CLUSTERS[cname]]
        M[idx, c] = prior[idx] / prior[idx].sum()
    assert np.all((M > 0).sum(axis=1) == 1)  # every attribute in exactly one cluster
    return M, names


def fit_clusters(d: ChoiceData, lam: float, prior: np.ndarray = EXPERT_STUDY) -> tuple[np.ndarray, np.ndarray]:
    """Fit cluster totals; returns (17 attribute weights, C cluster weights).
    The importance multiplier stays at v1's 1.5 (too few labels to estimate it)."""
    M, _ = cluster_matrix(prior)
    # Importance acts per attribute; fold it into the features before projecting.
    Xe = d.X * (1 + (V1_MULTIPLIER - 1) * d.I)
    dc = ChoiceData(Xe @ M, np.zeros((len(d.y), M.shape[1])), d.y, d.rater, d.rater_ids)
    cluster_prior = (M > 0).T.astype(float) @ prior  # cluster totals
    cluster_prior = cluster_prior / cluster_prior.sum()
    fit = fit_weights(dc, lam, prior=cluster_prior, fit_gamma=False, gamma0=0.0)
    w = M @ fit.weights
    return w / w.sum(), fit.weights

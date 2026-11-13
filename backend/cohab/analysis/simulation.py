"""Policy comparison in a transparent simulation (Cohab v2 plan W5).

SIMULATION. Every number this produces is a consequence of the assumptions
stated below, and is labelled `data_source="simulation"` wherever stored.
It is the honest substitute for a 90-day outcome no semester can observe:
a comparison of policies under declared assumptions, never a claim about
real roommates.

World model (one run):
- A population of N synthetic agents from the v1 seed distribution.
- Hidden true compatibility: true attribute weights w* (a Dirichlet draw
  around the expert vector), plus a symmetric pair-specific term eps_ij that
  no questionnaire can see. U_ij = sum_k w*_k s_kij + eps_ij. Held out from
  every policy.
- Each policy shows every agent a top-10 list of Stage-1-eligible candidates.
- Behaviour: an agent views rank r with probability 0.85^(r-1) and expresses
  interest with probability sigmoid(a * (U_ij - c)). A pair is mutual when
  both saw and liked each other. Mutual pairs are resolved into at most one
  cohabitation per person, greedily by true utility.

Policies: random (eligible), expert weights, learned weights (fitted to a
simulated 50-rater study drawn from w*), and the oracle (true U). Irving's
stable roommates on expert preferences is run as an assignment benchmark
(simulation only: the product never assigns).

Optional misreporting: a share of agents inflate their gameable answers one
step; policies see reported answers, the truth uses actual ones.
"""

from __future__ import annotations

import dataclasses
import random
from dataclasses import dataclass

import numpy as np

from cohab.analysis.fitting import build_choice_data, fit_weights
from cohab.analysis.irving import stable_roommates
from cohab.analysis.pair_analysis import FLATTERING_ORDER
from cohab.analysis.simulate_raters import GroundTruth, simulate_raters
from cohab.analysis.weights import EXPERT, full_weight_set, study_vector
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.population import synthetic_candidates
from cohab.services.matching.vectorised import (
    ALL_ATTRS,
    Population,
    attribute_matrices,
    blended_weights,
    directional_scores,
    eligible_mask,
    harmonic,
    top_k_fast,
)

LIST_K = 10
VIEW_DECAY = 0.85
INTEREST_SLOPE = 12.0
POLICIES = ("random", "expert", "learned", "oracle")


@dataclass
class WorldConfig:
    n_agents: int = 1000
    truth_concentration: float = 30.0  # Dirichlet spread of w* around expert
    pair_noise_sd: float = 0.05
    misreport_share: float = 0.0
    study_raters: int = 50
    include_irving: bool = True


def gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    if x.sum() == 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def _misreport(cands: list[Candidate], share: float, rng: random.Random) -> list[Candidate]:
    out = []
    for c in cands:
        if rng.random() >= share:
            out.append(c)
            continue
        q = dict(c.questionnaire)
        for f, order in FLATTERING_ORDER.items():
            if q.get(f) in order:
                q[f] = order[max(0, order.index(q[f]) - 1)]
        out.append(dataclasses.replace(c, questionnaire=q))
    return out


def _lists(policy_scores: np.ndarray | None, elig: np.ndarray, rng: np.random.Generator) -> list[np.ndarray]:
    n = elig.shape[0]
    out = []
    for i in range(n):
        if policy_scores is None:
            cand = np.flatnonzero(elig[i])
            out.append(rng.permutation(cand)[:LIST_K])
        else:
            out.append(top_k_fast(i, policy_scores, elig, LIST_K))
    return out


def _outcomes(lists: list[np.ndarray], U: np.ndarray, rng: np.random.Generator, centre: float) -> dict:
    n = len(lists)
    liked = np.zeros((n, n), dtype=bool)
    exposure = np.zeros(n)
    for i, lst in enumerate(lists):
        for r, j in enumerate(lst):
            exposure[j] += 1
            if rng.random() < VIEW_DECAY**r:
                p = 1 / (1 + np.exp(-INTEREST_SLOPE * (U[i, j] - centre)))
                liked[i, j] = rng.random() < p
    mutual = liked & liked.T
    HU = harmonic(U)
    pairs = np.argwhere(np.triu(mutual, 1))
    order = np.argsort(-HU[pairs[:, 0], pairs[:, 1]]) if len(pairs) else []
    matched = np.zeros(n, dtype=bool)
    welfare = []
    for idx in order:
        i, j = pairs[idx]
        if not matched[i] and not matched[j]:
            matched[i] = matched[j] = True
            welfare.append(HU[i, j])
    return {
        "match_rate": float(matched.mean()),
        "mean_true_utility_matched": float(np.mean(welfare)) if welfare else 0.0,
        "welfare_per_agent": float(np.sum(welfare) * 2 / n),
        "mutual_pairs": int(np.triu(mutual, 1).sum()),
        "exposure_gini": gini(exposure),
        "coverage": float(np.mean(exposure > 0)),
    }


def _irving(scores: np.ndarray, elig: np.ndarray, U: np.ndarray) -> dict:
    both = elig & elig.T
    prefs = []
    for i in range(scores.shape[0]):
        cand = np.flatnonzero(both[i])
        prefs.append(cand[np.argsort(-scores[i, cand], kind="stable")].tolist())
    m = stable_roommates(prefs)
    if m is None:
        return {"stable_matching_exists": False}
    HU = harmonic(U)
    vals = [HU[i, j] for i, j in m.items() if i < j]
    return {
        "stable_matching_exists": True,
        "match_rate": float(len(m) / scores.shape[0]),
        "mean_true_utility_matched": float(np.mean(vals)) if vals else 0.0,
        "welfare_per_agent": float(np.sum(vals) * 2 / scores.shape[0]),
    }


def run_world(cfg: WorldConfig, seed: int) -> dict:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    true_cands = synthetic_candidates(cfg.n_agents, seed=seed, all_verified=True)
    reported = _misreport(true_cands, cfg.misreport_share, rng) if cfg.misreport_share else true_cands

    names = tuple(n for n in ALL_ATTRS if n in EXPERT)
    pop_true = Population.from_candidates(true_cands)
    pop_rep = Population.from_candidates(reported)
    am_true = attribute_matrices(pop_true, names)
    am_rep = attribute_matrices(pop_rep, names) if reported is not true_cands else am_true
    elig = eligible_mask(pop_rep)

    # Hidden truth.
    w_star_study = nrng.dirichlet(study_vector(EXPERT) * cfg.truth_concentration)
    w_star = full_weight_set(w_star_study)
    eps = nrng.normal(0, cfg.pair_noise_sd, size=(cfg.n_agents, cfg.n_agents))
    eps = (eps + eps.T) / np.sqrt(2)
    U = directional_scores(am_true, blended_weights(pop_true, w_star, names)) + eps
    centre = float(np.median(U[elig]))

    # Learned weights from a simulated study drawn from w*.
    raters = simulate_raters(cfg.study_raters, GroundTruth(weights=w_star_study, scale=14), seed=seed + 7919)
    fit = fit_weights(build_choice_data(raters), lam=1.0)
    w_learned = full_weight_set(fit.weights)

    def policy_scores(weights) -> np.ndarray:
        return harmonic(directional_scores(am_rep, blended_weights(pop_rep, weights, names)))

    scores = {
        "random": None,
        "expert": policy_scores(EXPERT),
        "learned": policy_scores(w_learned),
        "oracle": harmonic(U),
    }
    lists = {p: _lists(scores[p], elig, nrng) for p in POLICIES}
    out: dict = {"seed": seed, "policies": {}}
    for p in POLICIES:
        res = _outcomes(lists[p], U, np.random.default_rng(seed * 31 + POLICIES.index(p)), centre)
        oracle_sets = [set(x.tolist()) for x in lists["oracle"]]
        res["top10_overlap_with_oracle"] = float(
            np.mean(
                [
                    len(set(lists[p][i].tolist()) & oracle_sets[i]) / len(oracle_sets[i])
                    for i in range(cfg.n_agents)
                    if oracle_sets[i]
                ]
            )
        )
        out["policies"][p] = res
    for p in POLICIES:
        out["policies"][p]["regret"] = out["policies"]["oracle"]["welfare_per_agent"] - out["policies"][p]["welfare_per_agent"]
    if cfg.include_irving:
        out["irving_expert"] = _irving(scores["expert"], elig, U)
    out["learned_weight_corr_with_truth"] = float(np.corrcoef(fit.weights, w_star_study)[0, 1])
    out["expert_weight_corr_with_truth"] = float(np.corrcoef(study_vector(EXPERT), w_star_study)[0, 1])
    return out


def _mean_ci(values: list[float]) -> dict:
    v = np.asarray(values, dtype=float)
    if v.size == 0:
        return {"mean": None, "ci95": [None, None], "n": 0}
    half = 1.96 * v.std(ddof=1) / np.sqrt(v.size) if v.size > 1 else 0.0
    return {"mean": float(v.mean()), "ci95": [float(v.mean() - half), float(v.mean() + half)], "n": int(v.size)}


def compare_policies(cfg: WorldConfig, runs: int, seed0: int = 1000) -> dict:
    results = [run_world(cfg, seed0 + r) for r in range(runs)]
    metrics = ("match_rate", "welfare_per_agent", "mean_true_utility_matched", "exposure_gini", "coverage", "regret", "top10_overlap_with_oracle")
    table = {p: {m: _mean_ci([r["policies"][p][m] for r in results]) for m in metrics} for p in POLICIES}
    irving = [r["irving_expert"] for r in results if "irving_expert" in r]
    irving_ok = [x for x in irving if x.get("stable_matching_exists")]
    return {
        "config": dataclasses.asdict(cfg),
        "runs": runs,
        "seeds": [seed0, seed0 + runs - 1],
        "table": table,
        "irving_expert": {
            "share_runs_with_stable_matching": len(irving_ok) / len(irving) if irving else None,
            "match_rate": _mean_ci([x["match_rate"] for x in irving_ok]),
            "welfare_per_agent": _mean_ci([x["welfare_per_agent"] for x in irving_ok]),
        },
        "learned_weight_corr_with_truth": _mean_ci([r["learned_weight_corr_with_truth"] for r in results]),
        "expert_weight_corr_with_truth": _mean_ci([r["expert_weight_corr_with_truth"] for r in results]),
        "assumptions": __doc__.split("World model (one run):")[1].split("Optional misreporting")[0].strip(),
    }


def misreporting_sweep(shares: list[float], runs: int, n_agents: int = 600, seed0: int = 5000) -> list[dict]:
    out = []
    for share in shares:
        cfg = WorldConfig(n_agents=n_agents, misreport_share=share, include_irving=False)
        res = compare_policies(cfg, runs, seed0)
        out.append(
            {
                "misreport_share": share,
                "expert_welfare": res["table"]["expert"]["welfare_per_agent"],
                "expert_regret": res["table"]["expert"]["regret"],
                "expert_overlap_with_oracle": res["table"]["expert"]["top10_overlap_with_oracle"],
            }
        )
    return out

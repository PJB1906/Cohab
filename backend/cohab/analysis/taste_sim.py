"""Does taste learning help? A simulation (SIMULATION, labelled as such).

Each synthetic member has *stated* weights (what the questionnaire gives the
matcher) and hidden *true* weights: a Dirichlet draw around the stated ones,
i.e. people roughly know what they want but not exactly. Each round the
member is shown the top 5 unseen eligible candidates under the policy, says
yes or no to each (a noisy logistic choice on their true utility), and the
taste model is refitted. We track how close each policy's full ranking gets
to the member's true ideal ranking.

Policies: "stated" (today's matcher, never changes) and "learned"
(services/taste.py). Also reported: the share of members whose ranking got
*worse* than stated, because a personalisation feature that hurts some
people is not free.
"""

from __future__ import annotations

import numpy as np

from cohab.analysis.weights import EXPERT
from cohab.services.matching.population import synthetic_candidates
from cohab.services.matching.vectorised import ALL_ATTRS, Population, attribute_matrices, eligible_mask
from cohab.services.taste import Decision, fit_taste, personal_score, stated_weights

SHOWN_PER_ROUND = 5
CHOICE_SCALE = 18.0


def _sims(am, i: int, j: int) -> dict[str, float]:
    out = {}
    for name in am.names:
        p = am.present[name]
        if p is None or (p[i] and p[j]):
            out[name] = float(am.sim[name][i, j])
    return out


def _score(weights: dict[str, float], sims: dict[str, float]) -> float:
    num = den = 0.0
    for a, w in weights.items():
        if a in sims:
            num += w * sims[a]
            den += w
    return num / den if den else 0.0


def _ndcg_at_k(order: list[int], true_util: dict[int, float], k: int = 10) -> float:
    ideal = sorted(true_util.values(), reverse=True)[:k]
    gains = [true_util[j] for j in order[:k]]
    disc = 1 / np.log2(np.arange(2, k + 2))
    idcg = float(np.sum(np.array(ideal) * disc[: len(ideal)]))
    return float(np.sum(np.array(gains) * disc[: len(gains)]) / idcg) if idcg else 0.0


def simulate_member(rng: np.random.Generator, am, elig_row: np.ndarray, i: int, important, rounds: int, concentration: float):
    names = [n for n in am.names if n in EXPERT]
    stated = stated_weights({n: EXPERT[n] for n in names}, important)
    w = np.array([stated[n] for n in names])
    true_w = dict(zip(names, rng.dirichlet(w * concentration + 1e-3)))
    cands = np.flatnonzero(elig_row)
    sims = {int(j): _sims(am, i, int(j)) for j in cands}
    true_u = {j: _score(true_w, s) for j, s in sims.items()}
    threshold = float(np.median(list(true_u.values())))
    true_top = set(sorted(true_u, key=true_u.get, reverse=True)[:10])

    decisions: list[Decision] = []
    seen: set[int] = set()
    curve = []
    model = fit_taste([], stated)
    for r in range(rounds + 1):
        scores = {
            j: (personal_score(model, s) if model.active else _score(stated, s)) for j, s in sims.items()
        }
        order = sorted(scores, key=scores.get, reverse=True)
        static_order = sorted(sims, key=lambda j: _score(stated, sims[j]), reverse=True)
        curve.append(
            {
                "round": r,
                "decisions": len(decisions),
                "learned_ndcg": _ndcg_at_k(order, true_u),
                "stated_ndcg": _ndcg_at_k(static_order, true_u),
                "learned_top10_overlap": len(set(order[:10]) & true_top) / 10,
                "stated_top10_overlap": len(set(static_order[:10]) & true_top) / 10,
                "active": model.active,
            }
        )
        if r == rounds:
            break
        shown = [j for j in order if j not in seen][:SHOWN_PER_ROUND]
        for j in shown:
            seen.add(j)
            p = 1 / (1 + np.exp(-CHOICE_SCALE * (true_u[j] - threshold)))
            decisions.append(Decision(sims=sims[j], liked=bool(rng.random() < p)))
        model = fit_taste(decisions, stated)
    return curve


def run(n_members: int = 120, rounds: int = 8, concentration: float = 12.0, seed: int = 0, pool: int = 500) -> dict:
    rng = np.random.default_rng(seed)
    cands = synthetic_candidates(pool, seed=seed + 1, all_verified=True)
    pop = Population.from_candidates(cands)
    am = attribute_matrices(pop, [n for n in ALL_ATTRS if n in EXPERT])
    elig = eligible_mask(pop)
    subjects = [i for i in range(pop.n) if elig[i].sum() >= 40]
    rng.shuffle(subjects)
    curves = [
        simulate_member(rng, am, elig[i], i, cands[i].important_attributes, rounds, concentration)
        for i in subjects[:n_members]
    ]

    def agg(key: str, r: int) -> dict:
        v = np.array([c[r][key] for c in curves])
        half = 1.96 * v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else 0.0
        return {"mean": float(v.mean()), "ci95": [float(v.mean() - half), float(v.mean() + half)]}

    rows = []
    for r in range(rounds + 1):
        lift = np.array([c[r]["learned_ndcg"] - c[r]["stated_ndcg"] for c in curves])
        rows.append(
            {
                "round": r,
                "decisions": r * SHOWN_PER_ROUND,
                "learned_ndcg": agg("learned_ndcg", r),
                "stated_ndcg": agg("stated_ndcg", r),
                "learned_top10_overlap": agg("learned_top10_overlap", r),
                "stated_top10_overlap": agg("stated_top10_overlap", r),
                "share_active": float(np.mean([c[r]["active"] for c in curves])),
                "share_worse_than_stated": float(np.mean(lift < -0.005)),
                "share_better_than_stated": float(np.mean(lift > 0.005)),
            }
        )
    return {
        "members": len(curves),
        "rounds": rounds,
        "shown_per_round": SHOWN_PER_ROUND,
        "truth_concentration": concentration,
        "rows": rows,
        "assumptions": __doc__.split("Policies:")[0].strip(),
    }

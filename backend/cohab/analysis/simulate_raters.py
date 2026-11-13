"""Simulated raters: SYNTHETIC data for tests, the power study and dry runs.

A simulated rater answers the real Cohab Lab design (`plan_trials`) under a
known ground truth, so the analysis pipeline can be checked for *recovery*:
does it get back the weights it was given? This is the only legitimate use of
these records. They are always marked `is_synthetic=True`, and no number
computed from them is ever reported as evidence about people (deck
invariant 6).

Ground-truth knobs, each a way real raters are known to deviate from the
model being fitted:
- `scale`: how deterministic choices are (logit scale on the score gap).
- `heterogeneity`: per-rater Dirichlet spread around the population weights.
- `attend_k`: each rater only attends to k attributes (bounded attention).
- `interaction`: a cleanliness x guests interaction the linear model lacks.
- `inattentive_share`: raters who answer at random, fast.
- `position_bias`: logit bonus for the left card.
- `importance_multiplier`: true effect of a rater's own "top 3" choice.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from cohab.services.study.design import plan_trials
from cohab.services.study.export import RaterRecord, TrialRecord
from cohab.services.study.features import card_vector
from cohab.services.study.instrument import OPTIONS, POPULATION_WEIGHTS, RATER_FIELDS, STUDY_ATTRIBUTES


@dataclass
class GroundTruth:
    weights: np.ndarray  # 17, sums to 1
    scale: float = 12.0
    heterogeneity: float | None = None  # Dirichlet concentration; None = identical raters
    attend_k: int | None = None
    interaction: float = 0.0
    inattentive_share: float = 0.0
    position_bias: float = 0.0
    importance_multiplier: float = 1.5
    none_share: float = 0.03
    label: str = "linear"
    extra: dict = field(default_factory=dict)


def _rater_answers(rng: random.Random) -> dict[str, str]:
    return {f: rng.choices(OPTIONS[f], weights=POPULATION_WEIGHTS.get(f), k=1)[0] for f in RATER_FIELDS}


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + np.exp(-z))


def simulate_raters(n: int, truth: GroundTruth, seed: int = 0) -> list[RaterRecord]:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    i_clean = STUDY_ATTRIBUTES.index("cleanliness_level")
    i_guest = STUDY_ATTRIBUTES.index("guests")
    out: list[RaterRecord] = []
    for r in range(n):
        answers = _rater_answers(rng)
        important = rng.sample(list(STUDY_ATTRIBUTES), k=rng.randint(0, 3))
        w = truth.weights.copy()
        if truth.heterogeneity is not None:
            w = nrng.dirichlet(truth.weights * truth.heterogeneity + 1e-3)
        if truth.attend_k is not None:
            keep = nrng.choice(len(w), size=truth.attend_k, replace=False, p=w / w.sum())
            mask = np.zeros_like(w)
            mask[keep] = 1
            w = w * mask
        boost = np.array([truth.importance_multiplier if a in important else 1.0 for a in STUDY_ATTRIBUTES])
        w = w * boost
        w = w / w.sum()
        inattentive = rng.random() < truth.inattentive_share

        def utility(card: dict[str, str]) -> float:
            v = card_vector(answers, card)
            u = float(v @ w)
            if truth.interaction:
                u += truth.interaction * (1 - v[i_clean]) * (1 - v[i_guest]) * -1
            return u

        trials: list[TrialRecord] = []
        for t in plan_trials(answers, seed=rng.randrange(2**31)):
            cards = {c["id"]: c["answers"] for c in t.cards}
            order = [c["id"] for c in t.cards]
            rec = TrialRecord(t.position, t.kind, cards, order, t.varied_attributes, t.repeat_of, t.expected_card)
            if t.kind == "rank":
                if inattentive:
                    ranking = order[:]
                    rng.shuffle(ranking)
                else:
                    noisy = {cid: utility(c) * truth.scale + nrng.gumbel() for cid, c in cards.items()}
                    ranking = sorted(noisy, key=noisy.get, reverse=True)
                rec.ranking = ranking
            else:
                left, right = order
                if inattentive:
                    p_left = 0.5
                else:
                    z = truth.scale * (utility(cards[left]) - utility(cards[right])) + truth.position_bias
                    p_left = _sigmoid(z)
                if rng.random() < truth.none_share and not inattentive:
                    rec.chosen = None
                else:
                    rec.chosen = left if rng.random() < p_left else right
                rec.confidence = rng.randint(1, 5)
                # Would-message: each card independently, logistic in utility.
                wm = {}
                for cid, card in cards.items():
                    pm = 0.5 if inattentive else _sigmoid(truth.scale * (utility(card) - 0.72))
                    wm[cid] = rng.random() < pm
                rec.would_message = wm
                rec.response_ms = int(rng.uniform(600, 1200) if inattentive else rng.lognormvariate(8.6, 0.4))
            trials.append(rec)
        out.append(
            RaterRecord(
                rater_id=f"sim-{seed}-{r}",
                cohort=f"synthetic:{truth.label}",
                is_synthetic=True,
                answers=answers,
                important=important,
                trials=trials,
                completed=True,
            )
        )
    return out


def simulate_pairs(
    n: int,
    weights: dict[str, float],
    *,
    signal: float = 6.0,
    self_inflation: float = 0.3,
    seed: int = 0,
):
    """SYNTHETIC roommate pairs. Satisfaction rises with the true combined
    score at strength `signal` (0 = no relationship); each person flatters
    themselves on the gameable items with probability `self_inflation`."""
    import uuid as _uuid

    from cohab.analysis.pair_analysis import FLATTERING_ORDER, candidate_from_answers
    from cohab.services.matching.scoring import CompatibilityMatcher
    from cohab.services.study.export import PairMemberRecord, PairRecord
    from cohab.services.study.instrument import GAMEABLE_FIELDS, OUTCOME_ITEMS

    rng = random.Random(seed)
    matcher = CompatibilityMatcher(dict(weights), _uuid.uuid4())
    out = []
    for i in range(n):
        truth_a, truth_b = _rater_answers(rng), _rater_answers(rng)
        ca = candidate_from_answers(truth_a, [], _uuid.UUID(int=1))
        cb = candidate_from_answers(truth_b, [], _uuid.UUID(int=2))
        score = matcher.score(ca, cb).combined_score
        members = []
        for me, other in ((truth_a, truth_b), (truth_b, truth_a)):
            reported = dict(me)
            for f in GAMEABLE_FIELDS:
                if f in FLATTERING_ORDER and rng.random() < self_inflation:
                    order = FLATTERING_ORDER[f]
                    reported[f] = order[max(0, order.index(me[f]) - 1)]
            view_of_other = {f: other[f] for f in GAMEABLE_FIELDS}
            base = 3 + signal * (score - 0.72) + rng.gauss(0, 0.8)
            outcomes = {k: int(min(5, max(1, round(base + rng.gauss(0, 0.6))))) for k in OUTCOME_ITEMS}
            members.append((reported, view_of_other, outcomes))
        months = round(rng.uniform(2, 24), 1)
        together = rng.random() < 0.8
        recs = [
            PairMemberRecord(role, rep, [], view, outc, months, together)
            for role, (rep, view, outc) in zip(("a", "b"), members)
        ]
        out.append(PairRecord(f"simpair-{seed}-{i}", True, recs[0], recs[1]))
    return out

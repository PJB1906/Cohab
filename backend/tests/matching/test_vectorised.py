"""The vectorised scorer must reproduce the reference matcher exactly
(Cohab v2 plan W5 prerequisite). If these fail, no simulation number built on
`vectorised.py` can be trusted."""

from __future__ import annotations

import dataclasses
import random
import uuid

import numpy as np
import pytest

from cohab.seed import DEFAULT_WEIGHTS
from cohab.services.matching.eligibility import EligibilityFilter
from cohab.services.matching.population import synthetic_candidates
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher
from cohab.services.matching.vectorised import (
    ELIGIBLE,
    REASON_ORDER,
    SELF,
    Population,
    eligibility_reasons,
    rank_for,
    score_population,
    top_k_fast,
)

WS = uuid.uuid4()


@pytest.fixture(scope="module")
def cands():
    return synthetic_candidates(120, seed=7)


def _drop_some_answers(cands, seed=1):
    """Exercise the spec §8 drop-and-renormalise path."""
    rng = random.Random(seed)
    out = []
    optional = ["life_stage", "daytime_presence", "home_orientation", "sociability", "noise_behaviour", "diet"]
    for c in cands:
        q = dict(c.questionnaire)
        for key in optional:
            if rng.random() < 0.25:
                q.pop(key, None)
        out.append(dataclasses.replace(c, questionnaire=q))
    return out


@pytest.mark.parametrize("drop", [False, True])
def test_directional_and_combined_scores_equal_reference(cands, drop) -> None:
    cands = _drop_some_answers(cands) if drop else cands
    matcher = CompatibilityMatcher(DEFAULT_WEIGHTS, WS)
    pop = Population.from_candidates(cands)
    sm = score_population(pop, DEFAULT_WEIGHTS)
    rng = random.Random(3)
    pairs = [(rng.randrange(len(cands)), rng.randrange(len(cands))) for _ in range(1500)]
    for i, j in pairs:
        if i == j:
            continue
        ref = matcher.score(cands[i], cands[j])
        assert sm.score[i, j] == pytest.approx(ref.score_ab, abs=1e-12)
        assert sm.score[j, i] == pytest.approx(ref.score_ba, abs=1e-12)
        assert sm.combined[i, j] == pytest.approx(ref.combined_score, abs=1e-12)


def test_text_vectors_use_cosine_like_reference(cands) -> None:
    rng = np.random.default_rng(0)
    with_text = [
        dataclasses.replace(c, text_vector=list(rng.random(8)) if k % 3 else None, text_vector_kind="tfidf")
        for k, c in enumerate(cands[:40])
    ]
    matcher = CompatibilityMatcher(DEFAULT_WEIGHTS, WS)
    sm = score_population(Population.from_candidates(with_text), DEFAULT_WEIGHTS)
    for i in range(40):
        for j in range(40):
            if i != j:
                assert sm.score[i, j] == pytest.approx(matcher.score(with_text[i], with_text[j]).score_ab, abs=1e-9)


def test_eligibility_reasons_equal_reference(cands) -> None:
    blocked = {frozenset({cands[0].user_id, cands[1].user_id})}
    settled = {frozenset({cands[2].user_id, cands[3].user_id})}
    pop = Population.from_candidates(cands, blocked_pairs=blocked, settled_pairs=settled)
    reasons = eligibility_reasons(pop)
    flt = EligibilityFilter(blocked_pairs=blocked, settled_pairs=settled)
    seen_codes = set()
    for i, subject in enumerate(cands):
        eligible, excluded = flt.filter(subject, cands)
        got = {cands[j].user_id: reasons[i, j] for j in range(len(cands)) if j != i}
        assert reasons[i, i] == SELF
        for c in eligible:
            assert got[c.user_id] == ELIGIBLE
        for ex in excluded:
            assert REASON_ORDER[got[ex.candidate.user_id]] == ex.reason
            seen_codes.add(ex.reason)
    # The fixture must actually exercise most constraints, or this test is weak.
    assert len(seen_codes) >= 5


def test_ranking_order_equals_match_ranker(cands) -> None:
    matcher = CompatibilityMatcher(DEFAULT_WEIGHTS, WS)
    ranker = MatchRanker(matcher)
    pop = Population.from_candidates(cands)
    sm = score_population(pop, DEFAULT_WEIGHTS)
    elig = eligibility_reasons(pop) == ELIGIBLE
    for i in range(0, len(cands), 7):
        ref = [m.candidate.user_id for m in ranker.rank(cands[i], cands)]
        got = [pop.ids[j] for j in rank_for(i, sm, elig, pop.ids)]
        assert got == ref


def test_top_k_fast_matches_scores() -> None:
    combined = np.array([[0, 0.9, 0.2, 0.5], [0.9, 0, 0.1, 0.3], [0.2, 0.1, 0, 0.8], [0.5, 0.3, 0.8, 0]])
    elig = ~np.eye(4, dtype=bool)
    elig[0, 1] = False
    assert top_k_fast(0, combined, elig, 2).tolist() == [3, 2]
    assert top_k_fast(0, combined, np.zeros((4, 4), bool), 2).tolist() == []


def test_population_generator_is_deterministic() -> None:
    a = synthetic_candidates(10, seed=5)
    b = synthetic_candidates(10, seed=5)
    assert [c.user_id for c in a] == [c.user_id for c in b]
    assert [c.questionnaire for c in a] == [c.questionnaire for c in b]
    assert [c.user_id for c in synthetic_candidates(10, seed=6)] != [c.user_id for c in a]

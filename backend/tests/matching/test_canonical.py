"""`flip()` — pure bookkeeping for canonical `match_score` storage. Hand
fixtures, no DB, matching the existing suite's style."""

import uuid

from cohab.services.matching.canonical import flip
from cohab.services.matching.explanations import build_explanation
from cohab.services.matching.scoring import CompatibilityMatcher
from tests.matching.fixtures import make_candidate

WEIGHTS = {
    "cleanliness_level": 0.3,
    "sleep_schedule": 0.3,
    "guests": 0.2,
    "payment_reliability": 0.2,
}
WEIGHT_SET_ID = uuid.UUID(int=1)


def _matcher() -> CompatibilityMatcher:
    return CompatibilityMatcher(WEIGHTS, WEIGHT_SET_ID)


def test_flip_swaps_ids_and_directional_scores() -> None:
    a = make_candidate(1, gender="female")
    b = make_candidate(2, gender="female", answers={"cleanliness_level": "relaxed"})
    result = _matcher().score(a, b)

    flipped = flip(result)

    assert flipped.subject_id == result.candidate_id
    assert flipped.candidate_id == result.subject_id
    assert flipped.score_ab == result.score_ba
    assert flipped.score_ba == result.score_ab
    assert flipped.combined_score == result.combined_score  # order-independent
    assert flipped.weight_set_id == result.weight_set_id


def test_flip_swaps_breakdown_sim_and_weight_fields() -> None:
    a = make_candidate(1, important_attributes={"cleanliness_level"})
    b = make_candidate(2, answers={"cleanliness_level": "relaxed"})
    result = _matcher().score(a, b)

    flipped = flip(result)

    for name, cell in result.breakdown.items():
        flipped_cell = flipped.breakdown[name]
        assert flipped_cell["sim_a"] == cell["sim_b"]
        assert flipped_cell["sim_b"] == cell["sim_a"]
        assert flipped_cell["w_a"] == cell["w_b"]
        assert flipped_cell["w_b"] == cell["w_a"]
        assert flipped_cell["type"] == cell["type"]  # untouched field preserved


def test_flip_is_its_own_inverse() -> None:
    a = make_candidate(1)
    b = make_candidate(2, answers={"sleep_schedule": "night_owl"})
    result = _matcher().score(a, b)

    assert flip(flip(result)) == result


def test_flipped_result_renders_explanation_from_the_other_viewpoint() -> None:
    # a is a very tidy early riser; b is relaxed and a night owl — a clear
    # divergence from either side, just described in the opposite direction.
    a = make_candidate(1, name="Asha", answers={"cleanliness_level": "very_tidy", "sleep_schedule": "early"})
    b = make_candidate(2, name="Bala", answers={"cleanliness_level": "relaxed", "sleep_schedule": "night_owl"})
    result = _matcher().score(a, b)

    explanation_from_a = build_explanation(a, b, result)
    explanation_from_b = build_explanation(b, a, flip(result))

    # Same underlying pair, viewed from the other side: a divergence exists
    # on both, and the flipped reconstruction doesn't invent or drop one.
    assert explanation_from_a.divergence is not None
    assert explanation_from_b.divergence is not None
    assert explanation_from_a.divergence.attribute == explanation_from_b.divergence.attribute

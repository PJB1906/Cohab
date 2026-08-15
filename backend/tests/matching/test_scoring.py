"""Stage 2 — directional scoring, blending and the harmonic mean.
COHAB_MATCHING_SPEC.md §8 (weights, missing answers) and §9 (procedure).
"""

import uuid

import pytest

from cohab.services.matching.scoring import (
    CompatibilityMatcher,
    blend,
    harmonic_mean,
)
from tests.matching.fixtures import make_candidate

# A small, valid weight vector summing to 1 (subset of spec §8, renormalised for
# the tests that need exact arithmetic; the matcher itself renormalises anyway).
WEIGHTS = {
    "cleanliness_level": 0.11,
    "chore_approach": 0.06,
    "sharing_norm": 0.04,
    "sleep_schedule": 0.09,
    "noise": 0.09,
    "guests": 0.10,
    "payment_reliability": 0.08,
    "cost_split_preference": 0.03,
    "communication_style": 0.08,
    "budget_proximity": 0.06,
    "diet": 0.03,
    "nonveg_cooking": 0.03,
    "smoking": 0.03,
    "alcohol": 0.02,
    "life_stage": 0.04,
    "daytime_presence": 0.02,
    "home_orientation": 0.02,
    "sociability": 0.02,
    "interests": 0.02,
    "lifestyle_notes": 0.03,
}
WEIGHT_SET_ID = uuid.UUID(int=999)


def matcher() -> CompatibilityMatcher:
    return CompatibilityMatcher(WEIGHTS, WEIGHT_SET_ID)


# --- harmonic mean ---------------------------------------------------------

def test_harmonic_mean_punishes_lopsidedness() -> None:
    # spec §6.3 / PRD §6.3: 0.9 and 0.3 → 0.45, below the arithmetic 0.60.
    assert harmonic_mean(0.9, 0.3) == pytest.approx(0.45)


def test_harmonic_mean_equal_inputs() -> None:
    assert harmonic_mean(0.8, 0.8) == pytest.approx(0.8)


def test_harmonic_mean_zero_guard() -> None:
    assert harmonic_mean(0.0, 0.0) == 0.0
    assert harmonic_mean(0.0, 0.5) == 0.0


# --- blend (spec §9) -------------------------------------------------------

def test_blend_without_importance_is_identity() -> None:
    result = blend(WEIGHTS, frozenset())
    assert result == pytest.approx(WEIGHTS)
    assert sum(result.values()) == pytest.approx(1.0)


def test_blend_boosts_selected_to_exactly_1_5x_default() -> None:
    result = blend(WEIGHTS, frozenset({"cleanliness_level"}))
    # Selected attribute is exactly 1.5× its default in the final vector...
    assert result["cleanliness_level"] == pytest.approx(0.11 * 1.5)
    # ...the rest are scaled down, and the whole vector still sums to 1.
    assert sum(result.values()) == pytest.approx(1.0)
    assert result["chore_approach"] < 0.06


# --- directional scoring ---------------------------------------------------

def test_identical_pair_scores_high_and_symmetric() -> None:
    a = make_candidate(1)
    b = make_candidate(2)
    result = matcher().score(a, b)
    assert result.score_ab == pytest.approx(result.score_ba)
    assert result.combined_score > 0.9
    assert result.weight_set_id == WEIGHT_SET_ID


def test_tolerance_is_directional() -> None:
    # sharing: A separate, B communal. spec §5: T[separate][communal]=0.35,
    # T[communal][separate]=0.55 — the harm is asymmetric.
    a = make_candidate(1, answers={"sharing_norm": "separate"})
    b = make_candidate(2, answers={"sharing_norm": "communal"})
    result = matcher().score(a, b)
    cell = result.breakdown["sharing_norm"]
    assert cell["sim_a"] == 0.35
    assert cell["sim_b"] == 0.55


def test_absolute_depends_only_on_other_party() -> None:
    # payment: A on_time, B early. spec §6: sim_a = table[B]=1.0, sim_b = table[A]=0.95.
    a = make_candidate(1, answers={"payment_reliability": "on_time"})
    b = make_candidate(2, answers={"payment_reliability": "early"})
    cell = matcher().score(a, b).breakdown["payment_reliability"]
    assert cell["sim_a"] == 1.00
    assert cell["sim_b"] == 0.95


def test_lopsided_pair_combined_below_arithmetic_mean() -> None:
    # A demands strict quiet and weights noise heavily; B is loud. A is unhappier
    # than B, so the directional scores diverge and the harmonic mean bites.
    a = make_candidate(
        1,
        answers={"noise_preference": "strict", "noise_behaviour": "quiet"},
        important_attributes={"noise"},
    )
    b = make_candidate(
        2,
        answers={"noise_preference": "flexible", "noise_behaviour": "loud"},
    )
    result = matcher().score(a, b)
    assert result.score_ab < result.score_ba  # A suffers more
    assert result.combined_score < (result.score_ab + result.score_ba) / 2


# --- missing answers (spec §8) --------------------------------------------

def test_missing_optional_attribute_is_dropped_and_renormalised() -> None:
    # A did not answer life_stage: it drops from both weight vectors, and the
    # remaining weights renormalise to 1 (never imputed to 0.5).
    a = make_candidate(1, answers={"life_stage": None})
    b = make_candidate(2)
    result = matcher().score(a, b)
    assert "life_stage" not in result.breakdown
    # Weights actually used (present attributes) renormalise to 1.
    used = sum(cell["w_a"] for cell in result.breakdown.values())
    assert used == pytest.approx(1.0)


def test_interests_and_notes_are_never_dropped_when_empty() -> None:
    # Empty interests / notes carry their own empty-handling (floor 0.3, neutral
    # 0.5) and stay in the breakdown rather than being dropped.
    a = make_candidate(1, answers={"interests": [], "lifestyle_notes": None})
    b = make_candidate(2, answers={"interests": [], "lifestyle_notes": None})
    result = matcher().score(a, b)
    assert result.breakdown["interests"]["sim_a"] == 0.3
    assert result.breakdown["lifestyle_notes"]["sim_a"] == 0.5

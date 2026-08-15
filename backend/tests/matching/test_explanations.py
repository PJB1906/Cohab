"""Explanation cards — COHAB_MATCHING_SPEC.md §10. Top-3 agreements (≥ 0.8) and
the single divergence (< 0.5), rendered from the viewer's direction.
"""

import uuid

from cohab.services.matching.explanations import build_explanation
from cohab.services.matching.scoring import CompatibilityMatcher
from tests.matching.test_scoring import WEIGHTS
from tests.matching.fixtures import make_candidate

WEIGHT_SET_ID = uuid.UUID(int=999)


def _matcher() -> CompatibilityMatcher:
    return CompatibilityMatcher(WEIGHTS, WEIGHT_SET_ID)


def test_agreements_capped_at_three_and_no_divergence_for_identical_pair() -> None:
    a = make_candidate(1)
    b = make_candidate(2, name="Meera")
    result = _matcher().score(a, b)
    exp = build_explanation(a, b, result)
    assert len(exp.agreements) == 3
    assert all(card.score >= 0.8 for card in exp.agreements)
    assert exp.divergence is None


def test_divergence_names_the_difference() -> None:
    a = make_candidate(1, answers={"cleanliness_level": "very_tidy"})
    b = make_candidate(2, name="Rohan", answers={"cleanliness_level": "relaxed"})
    result = _matcher().score(a, b)
    exp = build_explanation(a, b, result)
    assert exp.divergence is not None
    assert exp.divergence.attribute == "cleanliness_level"
    assert exp.divergence.score < 0.5
    assert "Rohan" in exp.divergence.text


def test_divergence_is_directional() -> None:
    # A tolerates no guests; B has guests often. For A the guest attribute is a
    # divergence; for B (tolerant) it is not.
    a = make_candidate(1, name="Asha", answers={"guest_tolerance": "prefer_none"})
    b = make_candidate(
        2, name="Bala",
        answers={"guest_tolerance": "anytime", "guest_frequency": "often"},
    )
    from_a = build_explanation(a, b, _matcher().score(a, b))
    from_b = build_explanation(b, a, _matcher().score(b, a))
    assert from_a.divergence is not None and from_a.divergence.attribute == "guests"
    # B tolerates anything, so guests is not B's divergence.
    assert from_b.divergence is None or from_b.divergence.attribute != "guests"


def test_agreement_text_is_populated() -> None:
    a = make_candidate(1)
    b = make_candidate(2, name="Priya")
    exp = build_explanation(a, b, _matcher().score(a, b))
    for card in exp.agreements:
        assert card.text  # non-empty rendered copy

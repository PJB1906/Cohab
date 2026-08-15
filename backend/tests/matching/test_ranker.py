"""MatchRanker — filter → score → sort/tie-break → explain.
COHAB_BUILD_PLAN.md §4 Phase 2 step 4.
"""

import uuid

from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher
from tests.matching.test_scoring import WEIGHTS
from tests.matching.fixtures import make_candidate

WEIGHT_SET_ID = uuid.UUID(int=999)


def _ranker() -> MatchRanker:
    return MatchRanker(CompatibilityMatcher(WEIGHTS, WEIGHT_SET_ID))


def test_ranked_in_descending_combined_score() -> None:
    subject = make_candidate(1)
    good = make_candidate(2, name="Good")  # identical → high
    poor = make_candidate(
        3, name="Poor",
        answers={"cleanliness_level": "relaxed", "sleep_schedule": "night_owl",
                 "communication_style": "let_go"},
    )
    ranked = _ranker().rank(subject, [poor, good])
    assert [m.candidate.name for m in ranked] == ["Good", "Poor"]
    scores = [m.result.combined_score for m in ranked]
    assert scores == sorted(scores, reverse=True)


def test_ineligible_candidates_excluded_from_ranking() -> None:
    subject = make_candidate(1)
    ok = make_candidate(2, name="Ok")
    unverified = make_candidate(3, name="Nope", verification_status="unverified")
    ranked = _ranker().rank(subject, [ok, unverified])
    assert [m.candidate.name for m in ranked] == ["Ok"]


def test_tie_break_is_deterministic() -> None:
    subject = make_candidate(1)
    # Two candidates with identical answers score identically; tie-break falls to
    # user_id ascending for a stable order.
    lo = make_candidate(2, name="Lo")
    hi = make_candidate(3, name="Hi")
    ranked_forward = _ranker().rank(subject, [hi, lo])
    ranked_reversed = _ranker().rank(subject, [lo, hi])
    assert [m.candidate.name for m in ranked_forward] == ["Lo", "Hi"]
    assert [m.candidate.name for m in ranked_reversed] == ["Lo", "Hi"]


def test_explanation_attached_to_each_match() -> None:
    subject = make_candidate(1)
    other = make_candidate(2, name="Sara")
    ranked = _ranker().rank(subject, [other])
    assert ranked[0].explanation is not None
    assert len(ranked[0].explanation.agreements) >= 1

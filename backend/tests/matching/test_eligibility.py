"""Stage 1 eligibility — COHAB_MATCHING_SPEC.md §2. One test per constraint:
the passing case, and each failure with its retained reason.
"""

from datetime import date, timedelta

from cohab.services.matching.eligibility import EligibilityFilter, Reason
from tests.matching.fixtures import make_candidate

SUBJECT = make_candidate(1, gender="female", gender_preference="any")


def _reason(subject, candidate):
    """Reason a single candidate is excluded relative to subject (or None)."""
    _eligible, excluded = EligibilityFilter().filter(subject, [candidate])
    return excluded[0].reason if excluded else None


def test_compatible_pair_passes() -> None:
    other = make_candidate(2, gender="male", gender_preference="any")
    eligible, excluded = EligibilityFilter().filter(SUBJECT, [other])
    assert [c.user_id for c in eligible] == [other.user_id]
    assert excluded == []


def test_self_is_skipped() -> None:
    eligible, excluded = EligibilityFilter().filter(SUBJECT, [SUBJECT])
    assert eligible == []
    assert excluded == []


def test_both_have_place_fails() -> None:
    a = make_candidate(1, seeker_type="has_place")
    b = make_candidate(2, seeker_type="has_place")
    assert _reason(a, b) == Reason.BOTH_HAVE_PLACE


def test_needs_and_has_place_passes() -> None:
    a = make_candidate(1, seeker_type="needs_place")
    b = make_candidate(2, seeker_type="has_place")
    assert _reason(a, b) is None


def test_different_city_fails() -> None:
    b = make_candidate(2, city="Chennai")
    assert _reason(SUBJECT, b) == Reason.DIFFERENT_CITY


def test_budget_disjoint_fails() -> None:
    a = make_candidate(1, budget_min=6000, budget_max=9000)
    b = make_candidate(2, budget_min=12000, budget_max=15000)
    assert _reason(a, b) == Reason.BUDGET_NO_OVERLAP


def test_budget_touching_bands_pass() -> None:
    # Bands that just touch (a.max == b.min) intersect (spec §2 uses <, not <=).
    a = make_candidate(1, budget_min=6000, budget_max=10000)
    b = make_candidate(2, budget_min=10000, budget_max=14000)
    assert _reason(a, b) is None


def test_move_in_beyond_tolerance_fails() -> None:
    a = make_candidate(1, move_in_date=date(2026, 9, 1))
    b = make_candidate(2, move_in_date=date(2026, 9, 1) + timedelta(days=31))
    assert _reason(a, b) == Reason.MOVE_IN_TOO_FAR


def test_move_in_at_tolerance_boundary_passes() -> None:
    a = make_candidate(1, move_in_date=date(2026, 9, 1))
    b = make_candidate(2, move_in_date=date(2026, 9, 1) + timedelta(days=30))
    assert _reason(a, b) is None


def test_gender_preference_not_mutual_fails() -> None:
    # A wants female only; B is male.
    a = make_candidate(1, gender="female", gender_preference="female")
    b = make_candidate(2, gender="male", gender_preference="any")
    assert _reason(a, b) == Reason.GENDER_PREFERENCE


def test_gender_preference_any_matches_all() -> None:
    a = make_candidate(1, gender="non_binary", gender_preference="any")
    b = make_candidate(2, gender="male", gender_preference="any")
    assert _reason(a, b) is None


def test_gender_non_binary_excluded_by_binary_preference() -> None:
    a = make_candidate(1, gender="female", gender_preference="female")
    b = make_candidate(2, gender="non_binary", gender_preference="female")
    assert _reason(a, b) == Reason.GENDER_PREFERENCE


def test_severe_allergy_conflict_fails() -> None:
    # A is severely allergic to peanuts; B cooks with peanuts (spec §2, asymmetric).
    a = make_candidate(1, severe_allergy=["peanuts"])
    b = make_candidate(2, kitchen_allergens=["peanuts"])
    assert _reason(a, b) == Reason.SEVERE_ALLERGY
    # Evaluated both ways.
    assert _reason(b, a) == Reason.SEVERE_ALLERGY


def test_severe_allergy_without_kitchen_signal_passes() -> None:
    # Current seed has no kitchen-allergen data, so allergy alone never excludes.
    a = make_candidate(1, severe_allergy=["peanuts"])
    b = make_candidate(2)
    assert _reason(a, b) is None


def test_pet_conflict_fails() -> None:
    a = make_candidate(1, pet_tolerance="cannot_live_with_pets")
    b = make_candidate(2, has_pet=True)
    assert _reason(a, b) == Reason.PET_CONFLICT
    # Detected whichever party is the subject (spec §2: evaluated both ways).
    assert _reason(b, a) == Reason.PET_CONFLICT
    # And with the pet/intolerance roles swapped between the two candidates.
    c = make_candidate(3, has_pet=True)
    d = make_candidate(4, pet_tolerance="cannot_live_with_pets")
    assert _reason(c, d) == Reason.PET_CONFLICT


def test_smoking_dealbreaker_fails() -> None:
    a = make_candidate(1, smoking_dealbreaker=True)
    b = make_candidate(2, answers={"smoking_behaviour": "indoors"})
    assert _reason(a, b) == Reason.SMOKING_DEALBREAKER
    # Both ways.
    c = make_candidate(3, answers={"smoking_behaviour": "indoors"})
    d = make_candidate(4, smoking_dealbreaker=True)
    assert _reason(c, d) == Reason.SMOKING_DEALBREAKER


def test_unverified_candidate_excluded() -> None:
    b = make_candidate(2, verification_status="unverified")
    assert _reason(SUBJECT, b) == Reason.NOT_VERIFIED_OR_ACTIVE


def test_suspended_candidate_excluded() -> None:
    b = make_candidate(2, account_status="suspended")
    assert _reason(SUBJECT, b) == Reason.NOT_VERIFIED_OR_ACTIVE


def test_blocked_pair_excluded() -> None:
    a = make_candidate(1)
    b = make_candidate(2)
    blocked = {frozenset({a.user_id, b.user_id})}
    _eligible, excluded = EligibilityFilter(blocked_pairs=blocked).filter(a, [b])
    assert excluded[0].reason == Reason.BLOCKED

"""Hand-checked cases for the precision@k/NDCG@10 recovery-experiment ground
truth (COHAB_BUILD_PLAN.md §3: known inputs, known outputs)."""

from __future__ import annotations

import random
import uuid

from cohab.seed import DEFAULT_WEIGHTS
from cohab.services.matching.eligibility import passes_hard_constraints
from cohab.services.matching.recovery import (
    CANDIDATES_PER_GRADE,
    GRADE_FRACTIONS,
    PERTURBABLE_ATTRIBUTES,
    PERTURBATIONS,
    build_graded_pool,
    perturb_candidate,
)
from cohab.services.matching.scoring import CompatibilityMatcher
from tests.matching.fixtures import make_candidate

WEIGHT_SET_ID = uuid.UUID(int=1)


def matcher() -> CompatibilityMatcher:
    return CompatibilityMatcher(DEFAULT_WEIGHTS, WEIGHT_SET_ID)


# --- individual perturbations against known matrix values ------------------

def test_similarity_perturbation_picks_the_matrix_minimum():
    # cleanliness_level row "very_tidy": very_tidy=1.00 moderate=0.60 relaxed=0.15
    subject = make_candidate(1, answers={"cleanliness_level": "very_tidy"})
    assert PERTURBATIONS["cleanliness_level"](subject) == {"cleanliness_level": "relaxed"}


def test_ordinal_perturbation_picks_the_farthest_endpoint():
    # order = ("out", "partly", "home"); "out" (index 0) is farthest from "home".
    subject = make_candidate(1, answers={"daytime_presence": "out"})
    assert PERTURBATIONS["daytime_presence"](subject) == {"daytime_presence": "home"}


def test_absolute_perturbation_is_worst_value_regardless_of_subject():
    # PAYMENT_RELIABILITY: early=1.00 on_time=0.95 needs_grace=0.50 needs_reminding=0.25
    for value in ("early", "on_time", "needs_grace", "needs_reminding"):
        subject = make_candidate(1, answers={"payment_reliability": value})
        assert PERTURBATIONS["payment_reliability"](subject) == {"payment_reliability": "needs_reminding"}


def test_tolerance_perturbation_moves_both_directional_fields():
    # noise matrix, row "moderate" (pref): quiet=1.00 moderate=0.85 loud=0.40 -> min "loud"
    # noise matrix, column "moderate" (behav): flexible=1.00 moderate=0.85 strict=0.60 -> min "strict"
    subject = make_candidate(1, answers={"noise_preference": "moderate", "noise_behaviour": "moderate"})
    assert PERTURBATIONS["noise"](subject) == {
        "noise_behaviour": "loud",
        "noise_preference": "strict",
    }


def test_sharing_norm_shared_field_picks_the_minimum_combined_pair():
    # sharing matrix, value "ask_first": communal sums to 0.90+0.85=1.75,
    # ask_first sums to 1.00+1.00=2.00, separate sums to 0.85+0.90=1.75.
    # communal and separate tie for the minimum; ask_first (no change) never wins.
    subject = make_candidate(1, answers={"sharing_norm": "ask_first"})
    result = PERTURBATIONS["sharing_norm"](subject)["sharing_norm"]
    assert result in {"communal", "separate"}


def test_nonveg_cooking_only_overrides_its_own_field():
    # nonveg_cooking matrix, column "nonveg": fine=1.00 prefer_not=0.45 not_at_all=0.15
    subject = make_candidate(1, answers={"diet": "nonveg", "nonveg_cooking_tolerance": "fine"})
    result = PERTURBATIONS["nonveg_cooking"](subject)
    assert result == {"nonveg_cooking_tolerance": "not_at_all"}
    assert "diet" not in result  # owned by the separate `diet` attribute, not touched here


# --- perturb_candidate / build_graded_pool ----------------------------------

def test_perturb_candidate_preserves_the_fields_a_real_pairing_needs_to_agree_on():
    subject = make_candidate(1)
    candidate = perturb_candidate(subject, fraction=1.0, rng=random.Random(0))

    assert candidate.user_id != subject.user_id
    for field in ("city", "budget_min", "budget_max", "move_in_date", "verification_status", "account_status"):
        assert getattr(candidate, field) == getattr(subject, field)


def test_perturb_candidate_neutralises_stage_one_fields_that_can_self_conflict():
    # A subject who has a pet but can't tolerate a roommate's, is seeking
    # only the opposite gender, already has a place, has flagged indoor
    # smoking a dealbreaker, and isn't yet verified — a real, valid
    # combination that would fail eligibility.py's checks against a plain
    # copy of itself. Every one of these seven field pairs must come out
    # neutralised, not copied.
    subject = make_candidate(
        1,
        gender="non_binary", gender_preference="male", seeker_type="has_place",
        has_pet=True, pet_tolerance="cannot_live_with_pets",
        severe_allergy=["peanuts"], kitchen_allergens=["peanuts"],
        smoking_dealbreaker=True,
        verification_status="pending", account_status="suspended",
    )
    candidate = perturb_candidate(subject, fraction=1.0, rng=random.Random(0))

    assert candidate.gender == "male"
    assert candidate.gender_preference == "any"
    assert candidate.seeker_type == "needs_place"
    assert candidate.has_pet is False
    assert candidate.pet_tolerance == "comfortable"
    assert candidate.severe_allergy == []
    assert candidate.kitchen_allergens == []
    assert candidate.smoking_dealbreaker is False
    assert candidate.verification_status == "verified"
    assert candidate.account_status == "active"

    passes, reason = passes_hard_constraints(subject, candidate)
    assert passes, reason


def test_perturbed_candidates_clear_stage_one_even_when_subject_is_unverified():
    # eligibility.py's very first check is the candidate's own verification/
    # account state (Reason.NOT_VERIFIED_OR_ACTIVE) — copying the subject's
    # own (unverified) state onto every candidate would fail that check
    # against every grade, including an identical clone at grade 4. Not
    # something evaluation.py could trigger live (it only ever samples
    # already-verified/active subjects), but recovery.py should not rely on
    # a caller to avoid it — found by a code-review pass, not a live run.
    subject = make_candidate(1, verification_status="pending", account_status="suspended")
    pool = build_graded_pool(subject, rng=random.Random(0))
    for candidate, _grade in pool:
        passes, reason = passes_hard_constraints(subject, candidate)
        assert passes, reason


def test_perturb_candidate_skips_an_attribute_the_subject_never_answered():
    # A droppable questionnaire field can be unanswered on a real profile
    # (attributes.py's `is_present` is what drops it from real scoring).
    # Looking a None answer up in a matrix/order used to raise ValueError.
    subject = make_candidate(1, answers={"daytime_presence": None})
    candidate = perturb_candidate(subject, fraction=1.0, rng=random.Random(0))
    assert candidate.answer("daytime_presence") is None


def test_perturb_candidate_leaves_notes_and_interests_untouched():
    subject = make_candidate(1, answers={"lifestyle_notes": "quiet evenings, tidy kitchen"})
    candidate = perturb_candidate(subject, fraction=1.0, rng=random.Random(0))
    assert candidate.answer("lifestyle_notes") == subject.answer("lifestyle_notes")
    assert candidate.answer("interests") == subject.answer("interests")


def test_perturb_candidate_zero_fraction_is_an_identical_clone():
    subject = make_candidate(1)
    candidate = perturb_candidate(subject, fraction=0.0, rng=random.Random(0))
    assert candidate.questionnaire == subject.questionnaire


def test_build_graded_pool_shape():
    subject = make_candidate(1)
    pool = build_graded_pool(subject, rng=random.Random(0))

    assert len(pool) == len(GRADE_FRACTIONS) * CANDIDATES_PER_GRADE
    relevances = [grade for _, grade in pool]
    for grade in range(len(GRADE_FRACTIONS)):
        assert relevances.count(grade) == CANDIDATES_PER_GRADE

    # relevance 4 (fraction 0.0) candidates are identical clones of the subject.
    top_grade_candidates = [c for c, grade in pool if grade == len(GRADE_FRACTIONS) - 1]
    for c in top_grade_candidates:
        assert c.questionnaire == subject.questionnaire


def test_seventeen_of_twenty_attributes_are_perturbable():
    assert len(PERTURBABLE_ATTRIBUTES) == 17
    assert "budget_proximity" not in PERTURBABLE_ATTRIBUTES
    assert "interests" not in PERTURBABLE_ATTRIBUTES
    assert "lifestyle_notes" not in PERTURBABLE_ATTRIBUTES


# --- recovery property: the real matcher scores full deviation lower -------

def test_fully_deviated_candidate_scores_lower_than_an_identical_clone():
    subject = make_candidate(1, answers={"lifestyle_notes": "quiet evenings, tidy kitchen"})
    rng = random.Random(42)
    clone = perturb_candidate(subject, fraction=0.0, rng=rng)
    deviated = perturb_candidate(subject, fraction=1.0, rng=rng)

    m = matcher()
    clone_result = m.score(subject, clone)
    deviated_result = m.score(subject, deviated)

    assert clone_result.combined_score > 0.9
    assert deviated_result.combined_score < clone_result.combined_score


# --- regression: Stage 1 must actually pass, not just "look untouched" -----
# All three found by running the recovery experiment against the seeded dev
# DB (CLAUDE.md's run-it-yourself rule) — `fixtures.make_candidate`'s
# defaults (gender_preference="any", smoking_dealbreaker=False,
# seeker_type="needs_place") never exercised any of the three branches, so
# the original unit tests above passed while the real DB run silently
# zeroed out most subjects' precision@k/NDCG@10.

def test_perturbed_candidates_clear_stage_one_even_when_subject_excludes_own_gender():
    # A subject seeking only the opposite gender is an ordinary real profile.
    # Copying the subject's own gender onto every candidate (the first
    # version of perturb_candidate) made every candidate fail eligibility
    # .py's mutual gender check every time.
    subject = make_candidate(1, gender="female", gender_preference="male")
    pool = build_graded_pool(subject, rng=random.Random(0))
    for candidate, _grade in pool:
        passes, reason = passes_hard_constraints(subject, candidate)
        assert passes, reason


def test_perturbed_candidates_clear_stage_one_even_when_subject_has_a_place():
    # eligibility.py excludes a pair where *both* are "has_place". Copying
    # the subject's own seeker_type onto every candidate made every
    # candidate fail that check whenever the subject was a has_place member.
    subject = make_candidate(1, seeker_type="has_place")
    pool = build_graded_pool(subject, rng=random.Random(0))
    for candidate, _grade in pool:
        passes, reason = passes_hard_constraints(subject, candidate)
        assert passes, reason


def test_perturbed_candidates_clear_stage_one_when_subject_has_smoking_dealbreaker():
    # smoking's least-compatible value is always "indoors" (every matrix row
    # bottoms out there — see test_tolerance_perturbation... above uses a
    # different attribute, but the same matrix shape applies). Against a
    # subject with the dealbreaker flag set, that would otherwise trip
    # eligibility.py's SMOKING_DEALBREAKER check instead of merely scoring
    # the candidate lower.
    subject = make_candidate(1, smoking_dealbreaker=True)
    pool = build_graded_pool(subject, rng=random.Random(0))
    for candidate, _grade in pool:
        passes, reason = passes_hard_constraints(subject, candidate)
        assert passes, reason

    # and confirm smoking_tolerance is genuinely left alone (unlike
    # smoking_behaviour, forced below, smoking_tolerance never conflicts
    # with the dealbreaker check, so it's fine to keep the subject's own):
    fully_deviated = [c for c, grade in pool if grade == 0]
    for candidate in fully_deviated:
        assert candidate.answer("smoking_tolerance") == subject.answer("smoking_tolerance")


def test_perturbed_candidates_clear_stage_one_when_subject_already_smokes_indoors_and_has_the_dealbreaker():
    # A self-contradictory-looking but real, valid profile: the subject
    # smokes indoors themselves *and* has flagged indoor smoking a
    # dealbreaker for a roommate. An unperturbed (grade-4) candidate would
    # otherwise just inherit the subject's own "indoors" and fail the
    # subject's own dealbreaker against its own clone — found running this
    # against the seeded dev DB, where it was the dominant remaining
    # failure after the other Stage-1 fixes above.
    subject = make_candidate(
        1, smoking_dealbreaker=True,
        answers={"smoking_behaviour": "indoors", "smoking_tolerance": "fine"},
    )
    pool = build_graded_pool(subject, rng=random.Random(0))
    for candidate, _grade in pool:
        passes, reason = passes_hard_constraints(subject, candidate)
        assert passes, reason
    for candidate, _grade in pool:
        assert candidate.answer("smoking_behaviour") == "none"

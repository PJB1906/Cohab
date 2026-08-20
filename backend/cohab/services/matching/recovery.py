"""Ground truth for the precision@k / NDCG@10 recovery experiment (PRD §15;
PRD §6.6 "recovery experiments" — plant a known ordering, confirm the real
matcher recovers it).

For 17 of the 20 scored attributes (COHAB_MATCHING_SPEC.md §8), this module
can replace a copy of a subject's own answer with the value the
*already spec-sourced* matrices in `matrices.py` record as least compatible
with it — no new compatibility model is invented, the existing hand-specified
matrices define "least compatible." `budget_proximity`, `interests` and
`lifestyle_notes` are excluded — see docs/DECISIONS.md's Phase 9 section,
D-9.1.

`build_graded_pool` uses this to construct, for one real subject, synthetic
candidates at controlled "how many attributes were deliberately made
incompatible" grades. Grade is a *construction* label the matcher never sees
— `evaluation.py` checks whether the real, unmodified `CompatibilityMatcher`/
`MatchRanker` pipeline ranks lower-grade (more deviated) candidates lower,
which is what "recovers a known ordering" means here. This validates the
implementation's wiring, not the underlying theory of what makes roommates
compatible (PRD §6.6) — every caller of this module must carry that caveat.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import replace
from typing import Any, Callable

from cohab.services.matching.attributes import ATTRIBUTES
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.matrices import (
    ORDINAL_ORDERS,
    PAYMENT_RELIABILITY,
    SIMILARITY_MATRICES,
    TOLERANCE_MATRICES,
)

Perturbation = Callable[[Candidate], dict[str, Any]]


def _least_column(matrix: dict[str, dict[str, float]], row_value: str) -> str:
    """The column value scoring lowest against a fixed row (spec §4/§5)."""
    row = matrix[row_value]
    return min(row, key=row.get)


def _least_row(matrix: dict[str, dict[str, float]], col_value: str) -> str:
    """The row value scoring lowest against a fixed column."""
    return min(matrix, key=lambda r: matrix[r][col_value])


def _least_combined(matrix: dict[str, dict[str, float]], value: str) -> str:
    """For a tolerance matrix read with the *same* field on both sides
    (sharing_norm): the single replacement value minimising the sum of both
    directional lookups."""
    return min(matrix, key=lambda c: matrix[value][c] + matrix[c][value])


def _farthest_ordinal(order: tuple[str, ...], value: str) -> str:
    i = order.index(value)
    j = max(range(len(order)), key=lambda j: abs(i - j))
    return order[j]


def _similarity_perturbation(field: str, matrix: dict[str, dict[str, float]]) -> Perturbation:
    """Symmetric similarity matrix, one shared field (spec §4)."""

    def perturb(subject: Candidate) -> dict[str, Any]:
        return {field: _least_column(matrix, subject.answer(field))}

    return perturb


def _ordinal_perturbation(field: str) -> Perturbation:
    order = ORDINAL_ORDERS[field]

    def perturb(subject: Candidate) -> dict[str, Any]:
        return {field: _farthest_ordinal(order, subject.answer(field))}

    return perturb


def _absolute_perturbation(field: str) -> Perturbation:
    """spec §6: score depends only on the candidate's own value, so the
    worst replacement doesn't depend on the subject at all."""
    worst = min(PAYMENT_RELIABILITY, key=PAYMENT_RELIABILITY.get)

    def perturb(subject: Candidate) -> dict[str, Any]:
        return {field: worst}

    return perturb


def _tolerance_perturbation(matrix_name: str, pref_field: str, behav_field: str) -> Perturbation:
    """The common tolerance case (spec §5): two distinct fields, neither
    shared with another attribute's own scored field. Moves both directional
    components — the candidate's behaviour away from the subject's
    preference, and the candidate's preference away from the subject's
    behaviour."""
    matrix = TOLERANCE_MATRICES[matrix_name]

    def perturb(subject: Candidate) -> dict[str, Any]:
        return {
            behav_field: _least_column(matrix, subject.answer(pref_field)),
            pref_field: _least_row(matrix, subject.answer(behav_field)),
        }

    return perturb


def _tolerance_shared_field_perturbation(matrix_name: str, field: str) -> Perturbation:
    """sharing_norm: pref_field and behav_field are the *same* questionnaire
    field (attributes.py: `_tolerance("sharing", "sharing_norm",
    "sharing_norm")`), so one replacement value has to serve both directions
    at once."""
    matrix = TOLERANCE_MATRICES[matrix_name]

    def perturb(subject: Candidate) -> dict[str, Any]:
        return {field: _least_combined(matrix, subject.answer(field))}

    return perturb


def _tolerance_owned_field_only_perturbation(
    matrix_name: str, owned_pref_field: str, shared_behav_field: str
) -> Perturbation:
    """nonveg_cooking: its behaviour field is `diet`, which is *also* the
    `diet` attribute's own scored field (attributes.py:
    `_tolerance("nonveg_cooking", "nonveg_cooking_tolerance", "diet")`).
    Deviating `diet` here would silently double up with the separate `diet`
    attribute's own perturbation, so this only ever touches the field
    nonveg_cooking exclusively owns (`nonveg_cooking_tolerance`) — this
    attribute's own slot reliably moves sim_b (the candidate's tolerance
    against the subject's diet); sim_a moves only if `diet` is independently
    selected in the same draw too. Averaging over many random subsets
    (`build_graded_pool`) is what keeps this an honest approximation rather
    than a silent bug."""
    matrix = TOLERANCE_MATRICES[matrix_name]

    def perturb(subject: Candidate) -> dict[str, Any]:
        return {owned_pref_field: _least_row(matrix, subject.answer(shared_behav_field))}

    return perturb


# Canonical order mirrors attributes.py's registry (spec §8). 17 of the 20
# scored attributes — budget_proximity/interests/lifestyle_notes excluded,
# D-9.1.
PERTURBATIONS: dict[str, Perturbation] = {
    "cleanliness_level": _similarity_perturbation("cleanliness_level", SIMILARITY_MATRICES["cleanliness_level"]),
    "chore_approach": _similarity_perturbation("chore_approach", SIMILARITY_MATRICES["chore_approach"]),
    "sharing_norm": _tolerance_shared_field_perturbation("sharing", "sharing_norm"),
    "sleep_schedule": _similarity_perturbation("sleep_schedule", SIMILARITY_MATRICES["sleep_schedule"]),
    "noise": _tolerance_perturbation("noise", "noise_preference", "noise_behaviour"),
    "guests": _tolerance_perturbation("guests", "guest_tolerance", "guest_frequency"),
    "payment_reliability": _absolute_perturbation("payment_reliability"),
    "cost_split_preference": _similarity_perturbation("cost_split_preference", SIMILARITY_MATRICES["cost_split_preference"]),
    "communication_style": _similarity_perturbation("communication_style", SIMILARITY_MATRICES["communication_style"]),
    "diet": _similarity_perturbation("diet", SIMILARITY_MATRICES["diet"]),
    "nonveg_cooking": _tolerance_owned_field_only_perturbation("nonveg_cooking", "nonveg_cooking_tolerance", "diet"),
    "smoking": _tolerance_perturbation("smoking", "smoking_tolerance", "smoking_behaviour"),
    "alcohol": _tolerance_perturbation("alcohol", "alcohol_tolerance", "alcohol_behaviour"),
    "life_stage": _similarity_perturbation("life_stage", SIMILARITY_MATRICES["life_stage"]),
    "daytime_presence": _ordinal_perturbation("daytime_presence"),
    "home_orientation": _ordinal_perturbation("home_orientation"),
    "sociability": _similarity_perturbation("sociability", SIMILARITY_MATRICES["sociability"]),
}

PERTURBABLE_ATTRIBUTES: tuple[str, ...] = tuple(PERTURBATIONS)

# 5 relevance grades: 0%, 25%, 50%, 75%, 100% of the 17 attributes deviated.
# Higher relevance = fewer deviations = more compatible by construction.
GRADE_FRACTIONS: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)
CANDIDATES_PER_GRADE = 6  # -> 30 synthetic candidates per subject


def _gender_that_clears_stage_one(subject: Candidate) -> tuple[str, str]:
    """(gender, gender_preference) for a candidate that is *guaranteed* to
    mutually satisfy `eligibility.py`'s gender check against `subject`,
    however the subject's own gender/preference are set.

    A naive "copy the subject's own gender and preference" (the first
    version of this function) breaks whenever the subject's preference
    excludes their own gender (e.g. a female subject seeking only male
    roommates) — every candidate would then share the subject's gender and
    fail `_gender_pref_satisfied(subject.gender_preference, candidate.gender)`
    every time, silently zeroing out that subject's whole graded pool. Found
    by actually running the recovery experiment against the seeded dev DB
    (CLAUDE.md's "read the matching code properly" / run-it-yourself rule) —
    the unit tests never caught it because `fixtures.make_candidate`'s
    default is `gender_preference="any"`, which never hits this branch.

    Setting the candidate's own preference to "any" makes the reverse
    direction unconditional; setting its gender to whatever the subject
    requires (or leaving it as the subject's own gender when the subject
    accepts anyone) makes the forward direction unconditional too.
    """
    gender = subject.gender if subject.gender_preference == "any" else subject.gender_preference
    return gender, "any"


def perturb_candidate(subject: Candidate, fraction: float, rng: random.Random) -> Candidate:
    """A copy of `subject` with a random `fraction` of the perturbable
    attributes swapped to their least-compatible value — guaranteed to
    clear Stage 1 against `subject` regardless of the subject's own gender
    preference, seeker type, pets, allergies, smoking dealbreaker or
    verification/account state.

    All of gender/gender_preference, seeker_type, has_pet/pet_tolerance,
    severe_allergy/kitchen_allergens, smoking_dealbreaker and
    verification_status/account_status are overridden to values that can
    never trip eligibility.py's mutual checks, rather than copied from the
    subject unchanged. A plain copy looks safe — the candidate then agrees
    with the subject on every one of these fields — but several of
    eligibility.py's checks are symmetric self-comparisons when a == b on
    the relevant field (e.g. `a.has_pet and b.pet_tolerance ==
    "cannot_live_with_pets"` — true for a subject who owns a pet but can't
    tolerate a roommate's, which is a real, valid profile, not a data
    error; or `b.verification_status != "verified"` — true for *any*
    not-yet-verified or suspended subject, since `b` here would just be a
    clone of `a`), so an identical clone of such a subject fails Stage 1
    against *itself*. Found by actually running this against the seeded dev
    DB one field at a time (gender, then seeker_type, then pets/allergies/
    smoking) — the unit tests never caught any of them because
    `fixtures.make_candidate`'s defaults happen to avoid every one of these
    self-conflicts. verification_status/account_status were the one field
    pair *not* found that way — `evaluation.py` only ever samples subjects
    that are already verified/active (`_is_valid_subject`), so the gap was
    latent rather than live; added directly once a reviewer traced it
    rather than waiting for it to surface against real data (see
    docs/DECISIONS.md's Phase 9 section, D-9.2). None of these seven
    field pairs has a Stage-2 scoring role (attributes.py's registry never
    reads any of them), so neutralising all of them costs nothing.

    Budget, move-in date and city are still untouched copies of the
    subject's own values — a real pairing needs those to actually agree,
    and none of them has a self-referential failure mode like the seven
    above (an identical range/date/string always matches itself).
    `lifestyle_notes`/`text_vector` are inherited unchanged too: held
    constant at the subject's own value (D-9.1), so that attribute's
    contribution stays maximally similar across every grade, exactly as
    "not perturbed" should behave.
    """
    # Real profiles can leave a droppable questionnaire field unanswered
    # (attributes.py's own `is_present` check is what drops such an
    # attribute from real scoring) — a perturbation keyed on that field
    # would otherwise crash looking up `None` in a matrix/order. Found the
    # same way as the Stage-1 conflicts above: running this against the
    # seeded dev DB, not the unit tests (whose fixtures answer every field).
    eligible_attrs = tuple(a for a in PERTURBABLE_ATTRIBUTES if ATTRIBUTES[a].is_present(subject, subject))

    forced: dict[str, Any] = {}
    if subject.smoking_dealbreaker:
        # "smoking"'s least-compatible value is always "indoors" (every row
        # of the matrix bottoms out there), so it's dropped from the
        # perturbable set for these subjects — the candidate's own
        # dealbreaker flag is already neutralised above, but the subject's
        # real one still excludes a candidate whose smoking_behaviour is
        # "indoors". That alone isn't enough, though: an unperturbed
        # (grade-4) candidate otherwise inherits the subject's own real
        # smoking_behaviour, and a subject can themselves already smoke
        # indoors while separately flagging it a dealbreaker for a
        # roommate — a real, self-contradictory-looking but valid profile
        # that would then fail eligibility.py's check against its own
        # clone. Forcing "none" (column "none" scores 1.00 against every
        # tolerance level) is the one safe baseline for every grade of
        # this subject's pool, not just the perturbed ones.
        eligible_attrs = tuple(a for a in eligible_attrs if a != "smoking")
        forced["smoking_behaviour"] = "none"

    n = round(fraction * len(eligible_attrs))
    chosen = rng.sample(eligible_attrs, n)

    overrides: dict[str, Any] = {}
    for attr in chosen:
        overrides.update(PERTURBATIONS[attr](subject))

    questionnaire = dict(subject.questionnaire)
    questionnaire.update(overrides)
    questionnaire.update(forced)

    gender, gender_preference = _gender_that_clears_stage_one(subject)

    return replace(
        subject,
        user_id=uuid.uuid4(),
        name=f"{subject.name} (perturbed {fraction:.0%})",
        gender=gender,
        gender_preference=gender_preference,
        seeker_type="needs_place",
        has_pet=False,
        pet_tolerance="comfortable",
        severe_allergy=[],
        kitchen_allergens=[],
        smoking_dealbreaker=False,
        verification_status="verified",
        account_status="active",
        questionnaire=questionnaire,
    )


def build_graded_pool(subject: Candidate, rng: random.Random) -> list[tuple[Candidate, int]]:
    """`CANDIDATES_PER_GRADE` synthetic candidates at each of 5 grades,
    returned as (candidate, relevance_grade) pairs — the format
    `ranking_metrics.py` expects. Sized (5 grades x 6 = 30 per subject, with
    the top-2 grades giving 12 "relevant" candidates) so a perfect recovery
    is achievable at k=10, not capped by construction."""
    pool: list[tuple[Candidate, int]] = []
    for grade_index, fraction in enumerate(GRADE_FRACTIONS):
        relevance = len(GRADE_FRACTIONS) - 1 - grade_index
        for _ in range(CANDIDATES_PER_GRADE):
            candidate = perturb_candidate(subject, fraction, rng)
            pool.append((candidate, relevance))
    return pool

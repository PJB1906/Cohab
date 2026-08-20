"""Stage 1 — hard-constraint filtering (COHAB_MATCHING_SPEC.md §2).

A candidate passes or fails; failure is never compensable by scoring well in
Stage 2 (spec §2, PRD §6.1). The reason for each exclusion is retained.

`passes_hard_constraints` is the per-pair core; `EligibilityFilter.filter` runs
it across a pool and splits it into the eligible list and the excluded list with
reasons.
"""

from __future__ import annotations

import uuid
from typing import Iterable, NamedTuple

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.matrices import MOVE_IN_TOLERANCE_DAYS


class Reason:
    """Retained exclusion reasons (spec §2), in evaluation order."""

    NOT_VERIFIED_OR_ACTIVE = "not_verified_or_active"
    BOTH_HAVE_PLACE = "both_have_place"
    DIFFERENT_CITY = "different_city"
    BUDGET_NO_OVERLAP = "budget_no_overlap"
    MOVE_IN_TOO_FAR = "move_in_too_far"
    GENDER_PREFERENCE = "gender_preference"
    SEVERE_ALLERGY = "severe_allergy"
    PET_CONFLICT = "pet_conflict"
    SMOKING_DEALBREAKER = "smoking_dealbreaker"
    BLOCKED = "blocked"
    ALREADY_DECIDED = "already_decided"


class Exclusion(NamedTuple):
    candidate: Candidate
    reason: str


def _gender_pref_satisfied(preference: str, gender: str) -> bool:
    """spec §2: `any` matches all; otherwise the gender must equal the preference."""
    return preference == "any" or preference == gender


def _budget_bands_intersect(a: Candidate, b: Candidate) -> bool:
    # spec §2: NOT (a.max < b.min OR b.max < a.min).
    return not (a.budget_max < b.budget_min or b.budget_max < a.budget_min)


def passes_hard_constraints(
    a: Candidate,
    b: Candidate,
    blocked_pairs: frozenset[frozenset[uuid.UUID]] | set | None = None,
    settled_pairs: frozenset[frozenset[uuid.UUID]] | set | None = None,
) -> tuple[bool, str | None]:
    """Return (passes, reason). `a` is the subject, `b` the candidate.

    The subject's own account state is assumed valid (guaranteed by the API layer
    in Phase 4); only the candidate's state is checked here.
    """
    # Account state — candidate must be Verified and Active (spec §2).
    if b.verification_status != "verified" or b.account_status != "active":
        return False, Reason.NOT_VERIFIED_OR_ACTIVE

    # Seeker type — two place-owners cannot pair (spec §2).
    if a.seeker_type == "has_place" and b.seeker_type == "has_place":
        return False, Reason.BOTH_HAVE_PLACE

    # City — must be equal (spec §2).
    if a.city != b.city:
        return False, Reason.DIFFERENT_CITY

    # Budget bands must intersect (spec §2).
    if not _budget_bands_intersect(a, b):
        return False, Reason.BUDGET_NO_OVERLAP

    # Move-in within tolerance (spec §2).
    if abs((a.move_in_date - b.move_in_date).days) > MOVE_IN_TOLERANCE_DAYS:
        return False, Reason.MOVE_IN_TOO_FAR

    # Gender preference mutually satisfied (spec §2).
    if not (
        _gender_pref_satisfied(a.gender_preference, b.gender)
        and _gender_pref_satisfied(b.gender_preference, a.gender)
    ):
        return False, Reason.GENDER_PREFERENCE

    # Severe allergy vs the other party's kitchen allergens, both ways (spec §2).
    if (set(a.severe_allergy) & set(b.kitchen_allergens)) or (
        set(b.severe_allergy) & set(a.kitchen_allergens)
    ):
        return False, Reason.SEVERE_ALLERGY

    # Pets — a pet owner against a cannot_live_with_pets tolerance, both ways (spec §2).
    if (b.has_pet and a.pet_tolerance == "cannot_live_with_pets") or (
        a.has_pet and b.pet_tolerance == "cannot_live_with_pets"
    ):
        return False, Reason.PET_CONFLICT

    # Indoor smoking against a declared deal-breaker, both ways (spec §2).
    if (b.answer("smoking_behaviour") == "indoors" and a.smoking_dealbreaker) or (
        a.answer("smoking_behaviour") == "indoors" and b.smoking_dealbreaker
    ):
        return False, Reason.SMOKING_DEALBREAKER

    # Blocks — either direction (spec §2; data wired in Phase 7).
    if blocked_pairs and frozenset({a.user_id, b.user_id}) in blocked_pairs:
        return False, Reason.BLOCKED

    # Already rejected or cohabiting (Phase 8) — not a spec §2 hard
    # constraint, but the same shape of pair-level exclusion as blocking:
    # a settled pair must not resurface as a fresh suggestion.
    # RejectConfirmDialog.tsx's own copy promises "neither of you can pick
    # this back up from here" — found in code review that nothing enforced
    # it; Stage 1 never knew a match_score row existed at all.
    if settled_pairs and frozenset({a.user_id, b.user_id}) in settled_pairs:
        return False, Reason.ALREADY_DECIDED

    return True, None


class EligibilityFilter:
    """Runs Stage 1 across a candidate pool."""

    def __init__(
        self,
        blocked_pairs: frozenset[frozenset[uuid.UUID]] | set | None = None,
        settled_pairs: frozenset[frozenset[uuid.UUID]] | set | None = None,
    ) -> None:
        self.blocked_pairs = blocked_pairs
        self.settled_pairs = settled_pairs

    def filter(
        self, subject: Candidate, pool: Iterable[Candidate]
    ) -> tuple[list[Candidate], list[Exclusion]]:
        eligible: list[Candidate] = []
        excluded: list[Exclusion] = []
        for candidate in pool:
            if candidate.user_id == subject.user_id:
                continue  # never match a user with themselves
            ok, reason = passes_hard_constraints(
                subject, candidate, self.blocked_pairs, self.settled_pairs
            )
            if ok:
                eligible.append(candidate)
            else:
                excluded.append(Exclusion(candidate, reason))
        return eligible, excluded

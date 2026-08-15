"""`Candidate` — the typed, framework-free view of a user the matcher scores.

The scoring code must be importable and testable without FastAPI *or* a database
(CLAUDE.md architecture rules; Phase 2 is headless). So the matcher never touches
ORM objects directly: `Candidate.from_orm(...)` adapts a (User, PreferenceProfile,
Listing) triple into this dataclass for the seed run, while hand-written test
fixtures construct it directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cohab.models import Listing, PreferenceProfile, User


@dataclass
class Candidate:
    """One user, flattened to exactly what Stage 1 and Stage 2 need."""

    user_id: uuid.UUID
    name: str

    # Account state + seeker type (spec §2).
    gender: str
    seeker_type: str
    verification_status: str
    account_status: str

    # Stage 1 hard-constraint fields (spec §2). `budget_min`/`budget_max` are the
    # *effective* band: for a has_place member with a listing they collapse to the
    # listing rent as a point value (spec §2/§7); see `from_orm`.
    city: str
    budget_min: int
    budget_max: int
    move_in_date: date
    gender_preference: str
    severe_allergy: list[str] = field(default_factory=list)
    # Allergens this person cooks with / needs in the shared kitchen. Spec §2's
    # allergy rule is asymmetric — "A allergic ⇒ B must not require it" — so it
    # needs this counterpart signal, which the Phase 1 schema does not yet carry.
    # Empty until a Phase 4 profile field populates it; the constraint is
    # therefore structurally present but inert on current seed data. Flagged.
    kitchen_allergens: list[str] = field(default_factory=list)
    has_pet: bool = False
    pet_tolerance: str = "comfortable"
    smoking_dealbreaker: bool = False

    # Stage 2 scored answers — the 24 keys of preference.QUESTIONNAIRE_KEYS.
    questionnaire: dict[str, Any] = field(default_factory=dict)

    # Cached text vector (populated at profile save in Phase 4; unused by the
    # Phase 2 headless path, which fits TF-IDF over the pool in report.py).
    text_vector: dict | list | None = None
    text_vector_kind: str | None = None

    @property
    def budget_midpoint(self) -> float:
        """spec §7: midpoint of the effective band."""
        return (self.budget_min + self.budget_max) / 2

    @property
    def lifestyle_notes(self) -> str | None:
        return self.questionnaire.get("lifestyle_notes")

    def answer(self, key: str) -> Any:
        """The user's answer for a questionnaire key, or None if unanswered."""
        return self.questionnaire.get(key)

    @classmethod
    def from_orm(
        cls,
        user: "User",
        profile: "PreferenceProfile",
        listing: "Listing | None" = None,
    ) -> "Candidate":
        # has_place with a listing: the listing rent is a point value on both the
        # Stage-1 band test and the §7 budget midpoint. Fall back to the profile
        # band if a has_place member somehow has no listing.
        if user.seeker_type == "has_place" and listing is not None:
            budget_min = budget_max = listing.rent_per_person
        else:
            budget_min, budget_max = profile.budget_min, profile.budget_max

        return cls(
            user_id=user.id,
            name=user.full_name,
            gender=user.gender,
            seeker_type=user.seeker_type,
            verification_status=user.verification_status,
            account_status=user.account_status,
            city=profile.city,
            budget_min=budget_min,
            budget_max=budget_max,
            move_in_date=profile.move_in_date,
            gender_preference=profile.gender_preference,
            severe_allergy=list(profile.severe_allergy or []),
            has_pet=profile.has_pet,
            pet_tolerance=profile.pet_tolerance,
            smoking_dealbreaker=profile.smoking_dealbreaker,
            questionnaire=dict(profile.questionnaire or {}),
            text_vector=profile.text_vector,
            text_vector_kind=profile.text_vector_kind,
        )

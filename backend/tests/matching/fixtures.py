"""Hand-written Candidate fixtures — COHAB_BUILD_PLAN.md §3: known inputs, known
outputs. Volume adds nothing here; correctness of a few hand-computed pairs does.

`make_candidate` starts from a fully-answered, middle-of-the-road questionnaire
so each test overrides only the fields it exercises.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from cohab.services.matching.candidate import Candidate

# A complete, valid set of answers for all 24 questionnaire keys (spec §3).
BASELINE_QUESTIONNAIRE: dict[str, Any] = {
    "sleep_schedule": "regular",
    "noise_preference": "moderate",
    "noise_behaviour": "moderate",
    "cleanliness_level": "moderate",
    "chore_approach": "shared",
    "sharing_norm": "ask_first",
    "guest_frequency": "occasionally",
    "guest_tolerance": "with_notice",
    "communication_style": "calm_later",
    "payment_reliability": "on_time",
    "cost_split_preference": "equal",
    "diet": "veg",
    "nonveg_cooking_tolerance": "fine",
    "smoking_behaviour": "none",
    "smoking_tolerance": "fine",
    "alcohol_behaviour": "none",
    "alcohol_tolerance": "fine",
    "life_stage": "job",
    "daytime_presence": "partly",
    "home_orientation": "balanced",
    "sociability": "friendly",
    "interests": ["music", "reading"],
    "lifestyle_notes": None,
}


def make_candidate(
    n: int = 1,
    *,
    name: str | None = None,
    gender: str = "female",
    seeker_type: str = "needs_place",
    verification_status: str = "verified",
    account_status: str = "active",
    city: str = "Bangalore",
    budget_min: int = 10000,
    budget_max: int = 15000,
    move_in_date: date = date(2026, 9, 1),
    gender_preference: str = "any",
    severe_allergy: list[str] | None = None,
    kitchen_allergens: list[str] | None = None,
    has_pet: bool = False,
    pet_tolerance: str = "comfortable",
    smoking_dealbreaker: bool = False,
    important_attributes: frozenset[str] | set[str] | None = None,
    answers: dict[str, Any] | None = None,
) -> Candidate:
    """Build a Candidate. `answers` is merged over BASELINE_QUESTIONNAIRE; a value
    of None in `answers` deletes that key (to test the missing-answer path)."""
    questionnaire = dict(BASELINE_QUESTIONNAIRE)
    if answers:
        for key, value in answers.items():
            if value is None and key in questionnaire:
                del questionnaire[key]
            else:
                questionnaire[key] = value

    return Candidate(
        user_id=uuid.UUID(int=n),
        name=name or f"User {n}",
        gender=gender,
        seeker_type=seeker_type,
        verification_status=verification_status,
        account_status=account_status,
        city=city,
        budget_min=budget_min,
        budget_max=budget_max,
        move_in_date=move_in_date,
        gender_preference=gender_preference,
        severe_allergy=severe_allergy or [],
        kitchen_allergens=kitchen_allergens or [],
        has_pet=has_pet,
        pet_tolerance=pet_tolerance,
        smoking_dealbreaker=smoking_dealbreaker,
        important_attributes=frozenset(important_attributes or ()),
        questionnaire=questionnaire,
    )

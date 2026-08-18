"""Pydantic request/response models for the API layer.

Hard-constraint enums are typed `Literal`s against the constants that already
define them in `models/user.py`/`models/preference.py` — one source of truth,
reused rather than re-declared. The `questionnaire` dict is validated for
known keys only, not per-option vocabulary: `matrices.py` is already that
vocabulary's one source of truth, and duplicating ~15 fields' worth of option
literals here buys little when the caller is this project's own trusted
frontend. A bad option value fails at match time (`KeyError` in
`matrices.py`), not at save time — a scope boundary, not an oversight.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from cohab.models.preference import GENDER_PREFERENCES, PET_TOLERANCES, QUESTIONNAIRE_KEYS
from cohab.models.user import GENDERS, SEEKER_TYPES

Gender = Literal[GENDERS]  # type: ignore[valid-type]
SeekerType = Literal[SEEKER_TYPES]  # type: ignore[valid-type]
GenderPreference = Literal[GENDER_PREFERENCES]  # type: ignore[valid-type]
PetTolerance = Literal[PET_TOLERANCES]  # type: ignore[valid-type]


# --- auth --------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt's own input limit
    full_name: str = Field(min_length=1, max_length=200)
    gender: Gender
    seeker_type: SeekerType
    course: str | None = None


class RegisterResponse(BaseModel):
    user_id: uuid.UUID


class VerifyOTPRequest(BaseModel):
    user_id: uuid.UUID
    code: str = Field(min_length=1, max_length=16)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    gender: str
    seeker_type: str
    verification_status: str
    account_status: str

    model_config = {"from_attributes": True}


# --- profile -------------------------------------------------------------

class ProfileUpsertRequest(BaseModel):
    city: str = "Bangalore"
    budget_min: int = Field(gt=0)
    budget_max: int = Field(gt=0)
    move_in_date: date
    gender_preference: GenderPreference = "any"
    severe_allergy: list[str] = Field(default_factory=list)
    kitchen_allergens: list[str] = Field(default_factory=list)
    has_pet: bool = False
    pet_tolerance: PetTolerance = "comfortable"
    smoking_dealbreaker: bool = False
    questionnaire: dict[str, Any] = Field(default_factory=dict)
    # Screen 6 — "pick the three that matter most to you" (spec §3).
    important_attributes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _budget_band_valid(self) -> "ProfileUpsertRequest":
        if self.budget_min > self.budget_max:
            raise ValueError("budget_min must be <= budget_max")
        return self

    @model_validator(mode="after")
    def _questionnaire_keys_known(self) -> "ProfileUpsertRequest":
        unknown = set(self.questionnaire) - set(QUESTIONNAIRE_KEYS)
        if unknown:
            raise ValueError(f"unknown questionnaire keys: {sorted(unknown)}")
        return self


class ProfileOut(BaseModel):
    city: str
    budget_min: int
    budget_max: int
    move_in_date: date
    gender_preference: str
    severe_allergy: list[str]
    kitchen_allergens: list[str]
    has_pet: bool
    pet_tolerance: str
    smoking_dealbreaker: bool
    questionnaire: dict[str, Any]
    important_attributes: list[str]

    model_config = {"from_attributes": True}


# --- listing ---------------------------------------------------------------

class ListingUpsertRequest(BaseModel):
    locality: str = Field(min_length=1)
    rent_per_person: int = Field(gt=0)
    deposit: int = Field(ge=0)
    room_type: Literal["private", "shared"]
    available_from: date
    amenities: list[str] = Field(default_factory=list)
    photos: list[str] = Field(default_factory=list)
    current_housemates: int = Field(ge=0, default=0)


class ListingOut(BaseModel):
    locality: str
    rent_per_person: int
    deposit: int
    room_type: str
    available_from: date
    amenities: list[str]
    photos: list[str]
    current_housemates: int

    model_config = {"from_attributes": True}


# --- matches -----------------------------------------------------------

class MatchListItem(BaseModel):
    match_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    combined_score: float
    agreements: list[str]
    divergence: str | None


class ExplanationCard(BaseModel):
    attribute: str
    kind: Literal["agreement", "divergence"]
    text: str
    score: float


class MatchExplanationResponse(BaseModel):
    match_id: uuid.UUID
    candidate_id: uuid.UUID
    candidate_name: str
    combined_score: float
    score_towards_candidate: float
    score_from_candidate: float
    breakdown: dict[str, dict[str, Any]]
    agreements: list[ExplanationCard]
    divergence: ExplanationCard | None

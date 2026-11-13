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
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator

from cohab.models.feedback import COHABITING_OUTCOMES, REJECTED_OUTCOMES
from cohab.models.preference import GENDER_PREFERENCES, PET_TOLERANCES, QUESTIONNAIRE_KEYS
from cohab.models.safety import REPORT_REASONS, REPORT_SANCTIONS
from cohab.models.user import GENDERS, SEEKER_TYPES

Gender = Literal[GENDERS]  # type: ignore[valid-type]
SeekerType = Literal[SEEKER_TYPES]  # type: ignore[valid-type]
GenderPreference = Literal[GENDER_PREFERENCES]  # type: ignore[valid-type]
PetTolerance = Literal[PET_TOLERANCES]  # type: ignore[valid-type]
ReportReason = Literal[REPORT_REASONS]  # type: ignore[valid-type]
ReportSanction = Literal[REPORT_SANCTIONS]  # type: ignore[valid-type]
# Permissive union — FeedbackService.submit enforces which subset is valid
# for the match's actual state (rejected vs cohabiting); Pydantic only rules
# out values that are never valid for either.
FeedbackOutcome = Literal[REJECTED_OUTCOMES + COHABITING_OUTCOMES]  # type: ignore[valid-type]


# --- auth --------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt's own input limit
    full_name: str = Field(min_length=1, max_length=200)
    gender: Gender
    seeker_type: SeekerType
    course: str | None = None
    phone_number: str | None = None


class AccountUpdateRequest(BaseModel):
    """Editable account details (docs/DECISIONS.md D-13.9).

    Everything here was previously write-once at registration, so a member
    who mistyped their name or wanted to add a phone number later had no way
    to change it. Deliberately narrow: `email` is the verification anchor and
    `gender`/`seeker_type` feed Stage 1 eligibility, so neither belongs in a
    casual profile edit — changing a seeker type would silently invalidate an
    existing listing and every match computed from it.

    All three fields are optional; only those present in the body are
    applied, so the client can PATCH one field without echoing the rest.
    """

    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    course: str | None = Field(default=None, max_length=200)
    phone_number: str | None = Field(default=None, max_length=32)


class RegisterResponse(BaseModel):
    user_id: uuid.UUID


class VerifyOTPRequest(BaseModel):
    user_id: uuid.UUID
    code: str = Field(min_length=1, max_length=16)


class ResendOTPRequest(BaseModel):
    email: EmailStr


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
    course: str | None = None
    avatar_url: str | None = None
    phone_number: str | None = None
    # Phase 7 — gates the moderator queue link/route in the SPA.
    is_moderator: bool = False

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
    # Enrichment beyond PRD §9 row 7's minimum ("name, score, three agreement
    # tags, one divergence tag") — a bare card with none of these read as
    # unfinished; all four are already on `Candidate` at zero extra query cost.
    seeker_type: str
    city: str
    budget_min: int
    budget_max: int
    avatar_url: str | None = None
    state: str
    # Second enrichment wave (mockup screen 8, docs/DECISIONS.md D-13.1). All
    # four are already on `Candidate` by the time the card is built, so this
    # costs no extra query. `course` was previously detail-only; the three
    # `listing_*` fields are what the "Room type" and "Move-in window" filters
    # and the move-in summary line are computed from, and are null for a
    # needs_place candidate, who has no listing.
    course: str | None = None
    move_in_date: date | None = None
    listing_room_type: str | None = None
    listing_available_from: date | None = None
    listing_locality: str | None = None
    # v2: present only while a calibration model is active (insights.py).
    would_message_probability: float | None = None
    confidence_tier: str | None = None
    calibration_version: int | None = None
    calibration_source: str | None = None


class ExplanationCard(BaseModel):
    attribute: str
    kind: Literal["agreement", "divergence"]
    text: str
    score: float


class MatchListingSummary(BaseModel):
    """PRD §9 row 8: match detail shows "listing if applicable"."""

    locality: str
    rent_per_person: int
    deposit: int
    room_type: str
    available_from: date
    amenities: list[str]
    photos: list[str]
    # Mockup screen 9's OCCUPANCY fact. Already a column on `Listing`; the
    # detail response just never carried it (docs/DECISIONS.md D-13.1).
    current_housemates: int = 0


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
    state: str
    you_expressed_interest: bool
    candidate_course: str | None = None
    candidate_avatar_url: str | None = None
    listing: MatchListingSummary | None = None
    # Mockup screen 9 prints "under weight set v2" beside the harmonic mean.
    # CLAUDE.md makes the stored `weight_set_id` an invariant precisely so a
    # historical explanation stays reproducible; showing the version is what
    # makes that guarantee visible to the user rather than only true in the
    # database. Sourced from the active `WeightSet.version`.
    weight_set_version: int | None = None
    would_message_probability: float | None = None
    confidence_tier: str | None = None
    calibration_version: int | None = None
    calibration_source: str | None = None


class ExpressInterestResponse(BaseModel):
    state: str


class RejectRequest(BaseModel):
    """v2 W1: optional, so v1 clients that POST with no body still work."""

    reason: Literal[
        "not_interested", "budget", "location", "lifestyle", "schedule", "found_elsewhere", "safety", "other"
    ] | None = None


class MarkReadRequest(BaseModel):
    up_to: datetime | None = None


class MarkReadResponse(BaseModel):
    marked: int


# --- saved matches -------------------------------------------------------
# New scope, not in COHAB_PRD.md/COHAB_MATCHING_SPEC.md — see
# services/saved.py. Wraps the existing `MatchListItem` card rather than
# inventing a parallel shape, plus the one field a saved-list view needs
# that a live match list doesn't: when it was saved.


class SavedMatchOut(BaseModel):
    saved_at: datetime
    match: MatchListItem


# --- feedback ---------------------------------------------------------

class FeedbackRequest(BaseModel):
    outcome: FeedbackOutcome
    # Only meaningful (and only read) for a "moved_out" outcome — the one
    # case the server can't derive the figure itself (FeedbackService.submit).
    cohabitation_duration_days: int | None = Field(default=None, ge=0)


class FeedbackOut(BaseModel):
    id: uuid.UUID
    outcome: str
    cohabitation_duration_days: int | None
    submitted_at: datetime


class PendingFeedbackOut(BaseModel):
    match_id: uuid.UUID
    other_user_id: uuid.UUID
    other_user_name: str
    state: str


# --- chat -----------------------------------------------------------------

class SendMessageRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    # PRD §9.1 item 1: the PII interrupt can be overridden once shown once
    # (e.g. a false positive) rather than being a permanent hard block.
    confirm: bool = False


class MessageOut(BaseModel):
    """Deliberately omits `flagged`/`pii_detected` — internal moderation
    signals (Phase 7's queue), not shown to the user whose message it is."""

    id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime
    is_read: bool


class ContactStatusOut(BaseModel):
    you_consented: bool
    other_consented: bool
    other_phone: str | None = None


# --- reports & blocks (PRD §8.3, §9 screen 11, §10) ------------------------


class ReportRequest(BaseModel):
    reported_user_id: uuid.UUID
    reason: ReportReason
    details: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    """Deliberately minimal — mirrors `ExpressInterestResponse`'s ack shape.
    The reporter doesn't need the full case record back, just confirmation
    of what was filed and whether it escalated."""

    id: uuid.UUID
    status: str
    escalated: bool


class BlockRequest(BaseModel):
    blocked_id: uuid.UUID


class BlockedUserOut(BaseModel):
    """PRD §10: blocking "cannot be undone by the blocked party" implies
    the blocker *can* — this is what a "who have I blocked" screen renders."""

    id: uuid.UUID
    full_name: str
    avatar_url: str | None = None


# --- moderation (PRD §8.3, §9 screen 13) ------------------------------------


class ReportSummaryOut(BaseModel):
    """Queue list row."""

    id: uuid.UUID
    reporter_name: str
    reported_user_name: str
    reason: str
    status: str
    escalated: bool
    created_at: datetime


class FlaggedMessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime


class ReportDetailOut(BaseModel):
    id: uuid.UUID
    reporter_id: uuid.UUID
    reporter_name: str
    reported_user_id: uuid.UUID
    reported_user_name: str
    reason: str
    details: str | None
    status: str
    escalated: bool
    resolution_note: str | None
    sanction: str | None
    created_at: datetime
    resolved_at: datetime | None
    # The reported user's flagged messages only — not the whole thread
    # (services/moderation_queue.py: `list_flagged_evidence`).
    evidence: list[FlaggedMessageOut]


class ResolveReportRequest(BaseModel):
    finding: Literal["substantiated", "dismissed"]
    sanction: ReportSanction | None = None
    note: str | None = Field(default=None, max_length=2000)


# --- analytics ----------------------------------------------------------

class FunnelStageOut(BaseModel):
    stage: str
    reached: int
    conversion_from_previous: float | None
    median_hours_from_suggested: float | None


class FunnelOut(BaseModel):
    total_matches: int
    stages: list[FunnelStageOut]
    rejected: int
    rejection_reasons: dict[str, int]


class AnalyticsSummaryOut(BaseModel):
    members_by_verification_status: dict[str, int]
    members_by_account_status: dict[str, int]
    matches_by_state: dict[str, int]
    reports_by_status: dict[str, int]


class PoolReasonOut(BaseModel):
    reason: str
    label: str
    count: int


class PoolSuggestionOut(BaseModel):
    kind: str
    label: str
    adds: int


class PoolInsightsOut(BaseModel):
    eligible: int
    considered: int
    excluded_by_reason: list[PoolReasonOut]
    suggestions: list[PoolSuggestionOut]


class TieHintOut(BaseModel):
    tied: bool
    set_overlap: float | None
    order_change: float | None
    method: str | None = None
    top3_candidate_ids: list[str] = []


class CalibrationStatusOut(BaseModel):
    active: bool
    version: int | None = None
    data_source: str | None = None
    target: str | None = None


class MatchInsightsOut(BaseModel):
    pool: PoolInsightsOut | None
    tie_hint: TieHintOut | None
    calibration: CalibrationStatusOut | None

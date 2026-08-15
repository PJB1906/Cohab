import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPKMixin,
    check_in,
)

# Hard-constraint enums — COHAB_MATCHING_SPEC.md §2.
GENDER_PREFERENCES = ("male", "female", "any")
# `cannot_live_with_pets` is the only value COHAB_MATCHING_SPEC.md §2 names;
# `comfortable` added to complete the pair — flagged as a proposal.
PET_TOLERANCES = ("comfortable", "cannot_live_with_pets")

# Tier 1-3 questionnaire keys stored in the `questionnaire` JSONB document —
# COHAB_MATCHING_SPEC.md §3. Listed here so seed.py and, later, the Phase 2
# matcher share one source of truth for the expected keys.
QUESTIONNAIRE_KEYS = (
    "sleep_schedule",
    "noise_preference",
    "noise_behaviour",
    "cleanliness_level",
    "chore_approach",
    "sharing_norm",
    "guest_frequency",
    "guest_tolerance",
    "communication_style",
    "payment_reliability",
    "cost_split_preference",
    "diet",
    "nonveg_cooking_tolerance",
    "smoking_behaviour",
    "smoking_tolerance",
    "alcohol_behaviour",
    "alcohol_tolerance",
    "life_stage",
    "daytime_presence",
    "home_orientation",
    "sociability",
    "interests",
    "lifestyle_notes",
)

TEXT_VECTOR_KINDS = ("tfidf", "embedding")


class PreferenceProfile(Base, UUIDPKMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "preference_profile"
    __table_args__ = (
        CheckConstraint("budget_min <= budget_max", name="ck_preference_profile_budget"),
        CheckConstraint(
            check_in("gender_preference", GENDER_PREFERENCES),
            name="ck_preference_profile_gender_preference",
        ),
        CheckConstraint(
            check_in("pet_tolerance", PET_TOLERANCES), name="ck_preference_profile_pet_tolerance"
        ),
        CheckConstraint(
            f"text_vector_kind IS NULL OR {check_in('text_vector_kind', TEXT_VECTOR_KINDS)}",
            name="ck_preference_profile_text_vector_kind",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, unique=True
    )

    # --- Stage 1 hard constraints (COHAB_MATCHING_SPEC.md §2) ---
    city: Mapped[str] = mapped_column(String, nullable=False, default="Bangalore")
    budget_min: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_max: Mapped[int] = mapped_column(Integer, nullable=False)
    move_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    gender_preference: Mapped[str] = mapped_column(String, nullable=False, default="any")
    severe_allergy: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    has_pet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pet_tolerance: Mapped[str] = mapped_column(String, nullable=False, default="comfortable")
    smoking_dealbreaker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Stage 2 scored attributes, plus cached text vector ---
    questionnaire: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    text_vector: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    text_vector_kind: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship(back_populates="preference_profile")


class UserAttributeWeight(Base, UUIDPKMixin):
    __tablename__ = "user_attribute_weight"
    __table_args__ = (
        CheckConstraint(
            "attribute_name <> ''", name="ck_user_attribute_weight_attribute_name_not_empty"
        ),
        UniqueConstraint(
            "user_id", "attribute_name", name="uq_user_attribute_weight_user_attribute"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    attribute_name: Mapped[str] = mapped_column(String, nullable=False)
    is_selected_important: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(back_populates="attribute_weights")

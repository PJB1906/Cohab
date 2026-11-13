import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import (
    Base,
    CreatedAtMixin,
    UpdatedAtMixin,
    UUIDPKMixin,
    check_in,
)

WEIGHT_SET_SOURCES = ("expert", "fitted", "gbt")

# v2: why a match was rejected. Optional; "other" carries no free text on
# purpose (free text here would be an unmoderated channel about a person).
REJECTION_REASONS = (
    "not_interested",
    "budget",
    "location",
    "lifestyle",
    "schedule",
    "found_elsewhere",
    "safety",
    "other",
)

# COHAB_PRD.md §8.2 match lifecycle states.
MATCH_STATES = (
    "suggested",
    "viewed",
    "interested",
    "mutual",
    "chatting",
    "contact_shared",
    "cohabiting",
    "rejected",
    "expired",
)


class WeightSet(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "weight_set"
    __table_args__ = (
        CheckConstraint(check_in("source", WEIGHT_SET_SOURCES), name="ck_weight_set_source"),
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="expert")
    # Full attribute -> weight dict, COHAB_MATCHING_SPEC.md §8.
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Immutable once set — COHAB_MATCHING_SPEC.md §6.5 / CLAUDE.md.
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    match_scores: Mapped[list["MatchScore"]] = relationship(back_populates="weight_set")


class MatchScore(Base, UUIDPKMixin, CreatedAtMixin, UpdatedAtMixin):
    __tablename__ = "match_score"
    __table_args__ = (
        CheckConstraint("user_id_a < user_id_b", name="ck_match_score_ordered_pair"),
        UniqueConstraint("user_id_a", "user_id_b", name="uq_match_score_pair"),
        CheckConstraint(check_in("state", MATCH_STATES), name="ck_match_score_state"),
        CheckConstraint(
            "rejection_reason IS NULL OR " + check_in("rejection_reason", REJECTION_REASONS),
            name="ck_match_score_rejection_reason",
        ),
    )

    user_id_a: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    user_id_b: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    weight_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weight_set.id"), nullable=False
    )
    score_ab: Mapped[float] = mapped_column(Float, nullable=False)
    score_ba: Mapped[float] = mapped_column(Float, nullable=False)
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)
    # Per-attribute {sim_a, sim_b} — COHAB_MATCHING_SPEC.md §9.
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[str] = mapped_column(String, nullable=False, default="suggested")
    interested_by_a: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    interested_by_b: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set once, by confirm_move_in (ContactShared -> Cohabiting, PRD §8.2).
    # Anchors both the 30/90-day feedback cadence and the survival duration
    # Phase 9's Kaplan-Meier estimator needs — never overwritten afterwards.
    cohabiting_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # v2 W1 instrumentation. `first_shown_at` is set by the first exposure,
    # `first_messaged_at` by the first chat message; neither is overwritten.
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    first_shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_messaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    weight_set: Mapped["WeightSet"] = relationship(back_populates="match_scores")

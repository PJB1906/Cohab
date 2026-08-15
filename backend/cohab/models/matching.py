import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String, UniqueConstraint
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

    weight_set: Mapped["WeightSet"] = relationship(back_populates="match_scores")

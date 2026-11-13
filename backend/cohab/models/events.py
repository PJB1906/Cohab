"""v2 A1 instrumentation tables (Cohab v2 plan W1).

Both tables are append-only: no service ever updates or deletes a row in them.
They exist so every exposure, ranking decision and lifecycle transition can be
reconstructed after the fact, which nothing in v1 allowed (v1 overwrote
`match_score.state` in place).
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, UUIDPKMixin, check_in, utcnow
from sqlalchemy import CheckConstraint

EXPOSURE_SURFACES = ("list", "detail", "lab")


class MatchExposure(Base, UUIDPKMixin):
    """One row per impression of a candidate to a viewer."""

    __tablename__ = "match_exposure"
    __table_args__ = (
        CheckConstraint(check_in("surface", EXPOSURE_SURFACES), name="ck_match_exposure_surface"),
        Index("ix_match_exposure_viewer_shown", "viewer_id", "shown_at"),
        Index("ix_match_exposure_match", "match_score_id"),
    )

    match_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_score.id", ondelete="CASCADE"), nullable=False
    )
    viewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    # 1-based position in the list returned to the viewer.
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    surface: Mapped[str] = mapped_column(String, nullable=False)
    # e.g. "expert-v2", "fitted-v3": which ranking policy produced the list.
    policy_version: Mapped[str] = mapped_column(String, nullable=False)
    # P(this candidate shown at this position | logging policy). 1.0 for the
    # deterministic ranker; kept so off-policy estimators have what they need.
    propensity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    weight_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weight_set.id"), nullable=False
    )
    combined_score: Mapped[float] = mapped_column(Float, nullable=False)


class MatchStateEvent(Base, UUIDPKMixin):
    """Append-only lifecycle log: one row per `match_score.state` change."""

    __tablename__ = "match_state_event"
    __table_args__ = (Index("ix_match_state_event_match_at", "match_score_id", "at"),)

    match_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_score.id", ondelete="CASCADE"), nullable=False
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String, nullable=True)
    to_state: Mapped[str] = mapped_column(String, nullable=False)
    # None for system transitions (creation, expiry, recompute).
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=True
    )
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)

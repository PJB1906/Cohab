import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, UUIDPKMixin


class Feedback(Base, UUIDPKMixin):
    __tablename__ = "feedback"
    __table_args__ = (
        UniqueConstraint("match_score_id", "submitted_by", name="uq_feedback_score_submitter"),
    )

    match_score_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("match_score.id"), nullable=False
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    # Plain string, not a CHECK-enum: the outcome taxonomy isn't specified
    # anywhere in the docs and isn't used until Phase 8.
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    cohabitation_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False)

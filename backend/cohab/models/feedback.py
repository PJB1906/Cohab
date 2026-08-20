import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, UUIDPKMixin

# Proposed in Phase 8 (docs/DECISIONS.md) — not sourced from PRD/spec, which
# name no taxonomy. Which set applies depends on the match_score's state at
# submission time (cohabiting vs rejected), so it's enforced by
# FeedbackService.submit, not a DB CHECK — same precedent as
# models/safety.py's Report.reason (REPORT_REASONS), a proposed vocabulary
# enforced at the service/API boundary so it can grow without a migration.
REJECTED_OUTCOMES = ("not_pursued", "incompatible", "other")
COHABITING_OUTCOMES = ("still_together", "moved_out")


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
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    cohabitation_duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(nullable=False)

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin, check_in

# COHAB_PRD.md §8.3 report state machine.
REPORT_STATUSES = ("open", "under_review", "substantiated", "dismissed", "action_taken")


class Moderator(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "moderator"

    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class Report(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "report"
    __table_args__ = (
        CheckConstraint(check_in("status", REPORT_STATUSES), name="ck_report_status"),
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    # Plain string — PRD screen 11 lists no fixed set of reasons.
    reason: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_moderator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("moderator.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class UserBlock(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "user_block"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_user_block_pair"),
    )

    blocker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )

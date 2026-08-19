import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin, check_in

# COHAB_PRD.md §8.3 report state machine.
REPORT_STATUSES = ("open", "under_review", "substantiated", "dismissed", "action_taken")

# Phase 7 (docs/DECISIONS.md D-7.2). PRD screen 11 ("Reason, details, submit")
# fixes no vocabulary; this set is proposed and enforced at the API boundary
# (api/schemas.py's `Literal`), matching how ProfileUpsertRequest validates
# questionnaire keys at the schema layer rather than a DB CHECK — `reason`
# stays free-text here so this list can grow without a migration.
REPORT_REASONS = (
    "harassment",
    "threats",
    "sexual_harassment",
    "spam",
    "scam_or_fraud",
    "fake_profile",
    "inappropriate_behaviour",
    "other",
)

# PRD §8.3: "Reports alleging threats or sexual harassment escalate
# immediately and may suspend pending review." `harassment` is added to that
# named pair — proposed, flagged in DECISIONS — since a plain-language
# harassment allegation is the same order of urgency and PRD screen 11 gives
# no separate, narrower category for it.
ESCALATING_REASONS = ("harassment", "threats", "sexual_harassment")

# PRD §8.3: "Substantiated -> ActionTaken: warn / suspend / ban." Recorded
# separately from `Report.status` (the finding) per PRD's own framing:
# "Finding and sanction are recorded separately, so the audit trail shows
# what was concluded as well as what was done."
REPORT_SANCTIONS = ("warn", "suspend", "ban")


class Moderator(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "moderator"

    # Phase 7: links the audit/reviewer entity to a real, authenticated
    # account (docs/DECISIONS.md D-7.1) — moderator auth reuses the existing
    # cookie session via `user.is_moderator`, rather than a second login
    # flow. `name`/`email` are kept as a display snapshot, populated from the
    # linked user the first time they act as a moderator
    # (`services/moderation_queue.get_or_create_moderator`).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class Report(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "report"
    __table_args__ = (
        CheckConstraint(check_in("status", REPORT_STATUSES), name="ck_report_status"),
        CheckConstraint(
            f"sanction IS NULL OR ({check_in('sanction', REPORT_SANCTIONS)})",
            name="ck_report_sanction",
        ),
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    # Plain string — PRD screen 11 lists no fixed set of reasons. Vocabulary
    # enforced at the API boundary (REPORT_REASONS above), not here.
    reason: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_moderator_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("moderator.id"), nullable=True
    )
    # The moderator's finding rationale — PRD §8.3's "Finding and sanction
    # are recorded separately." `status` (substantiated/dismissed) is the
    # finding itself; this is the free-text reasoning behind it.
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The sanction actually applied — NULL until `action_taken` (or ever, for
    # a dismissed report). Kept off `status` so "what was concluded" and
    # "what was done" don't collapse into one field.
    sanction: Mapped[str | None] = mapped_column(String, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)

    reporter: Mapped["User"] = relationship(foreign_keys=[reporter_id])
    reported_user: Mapped["User"] = relationship(foreign_keys=[reported_user_id])
    assigned_moderator: Mapped["Moderator | None"] = relationship()


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

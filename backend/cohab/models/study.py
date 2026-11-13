"""Cohab Lab (preference study) and roommate-pair validation tables
(Cohab v2 plan W2 and W3).

Deliberately isolated from the product schema: no foreign key points from
any product table into these, and these reference no product user. A study
participant is identified only by a random token whose SHA-256 is stored, so
deleting every `study_*` row (scripts/delete_study_data) removes the study
without touching the product. `is_synthetic` marks dry-run rows generated to
test the pipeline; every analysis excludes them unless explicitly asked, and
the report labels any number computed from them.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cohab.models.base import Base, CreatedAtMixin, UUIDPKMixin, check_in

TRIAL_KINDS = ("pair", "repeat", "attention", "rank")
CHOICES = ("left", "right", "none")
WOULD_MESSAGE = ("left", "right", "both", "neither")
PAIR_ROLES = ("a", "b")


class StudyRater(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "study_rater"

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    # Free-form recruitment label ("pilot", "main", "class-session-1", "dryrun").
    cohort: Mapped[str] = mapped_column(String, nullable=False, default="main")
    consent_version: Mapped[str | None] = mapped_column(String, nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The rater's own answers (the 21 lifestyle fields), so features can be
    # computed as directional scores from the rater to each card.
    questionnaire: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Up to three attribute names the rater calls most important (spec §3).
    important_attributes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Optional, coarse: {"age_band": "21-23", "gender": "female", "living": "pg"}.
    demographics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    design_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_trials_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    trials: Mapped[list["StudyTrial"]] = relationship(
        back_populates="rater", cascade="all, delete-orphan", order_by="StudyTrial.position"
    )


class StudyTrial(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "study_trial"
    __table_args__ = (
        CheckConstraint(check_in("kind", TRIAL_KINDS), name="ck_study_trial_kind"),
        UniqueConstraint("rater_id", "position", name="uq_study_trial_position"),
    )

    rater_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_rater.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    # Card profiles as shown, in display order. Pair trials: [left, right].
    # Rank trials: six cards. Each card: {"id": "A"|..., "answers": {...}}.
    cards: Mapped[list] = mapped_column(JSONB, nullable=False)
    # Attribute names that differ between the two cards (conjoint design).
    varied_attributes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # For "repeat": the position of the trial it repeats (cards swapped).
    repeat_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # For "attention": which card id is the obviously better fit.
    expected_card: Mapped[str | None] = mapped_column(String, nullable=True)
    presented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rater: Mapped["StudyRater"] = relationship(back_populates="trials")
    response: Mapped["StudyResponse | None"] = relationship(
        back_populates="trial", cascade="all, delete-orphan", uselist=False
    )


class StudyResponse(Base, UUIDPKMixin):
    __tablename__ = "study_response"
    __table_args__ = (
        CheckConstraint(f"choice IS NULL OR {check_in('choice', CHOICES)}", name="ck_study_response_choice"),
        CheckConstraint(
            f"would_message IS NULL OR {check_in('would_message', WOULD_MESSAGE)}",
            name="ck_study_response_would_message",
        ),
        CheckConstraint("confidence IS NULL OR (confidence BETWEEN 1 AND 5)", name="ck_study_response_confidence"),
    )

    trial_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_trial.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    choice: Mapped[str | None] = mapped_column(String, nullable=True)
    # Rank trials: card ids, best first.
    ranking: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    would_message: Mapped[str | None] = mapped_column(String, nullable=True)
    reason_text: Mapped[str | None] = mapped_column(String(140), nullable=True)
    response_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trial: Mapped["StudyTrial"] = relationship(back_populates="response")


class StudyPair(Base, UUIDPKMixin, CreatedAtMixin):
    """W3: two people who live (or lived) together, each answering alone."""

    __tablename__ = "study_pair"

    invite_token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    cohort: Mapped[str] = mapped_column(String, nullable=False, default="main")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    members: Mapped[list["StudyPairMember"]] = relationship(
        back_populates="pair", cascade="all, delete-orphan", order_by="StudyPairMember.role"
    )


class StudyPairMember(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "study_pair_member"
    __table_args__ = (
        CheckConstraint(check_in("role", PAIR_ROLES), name="ck_study_pair_member_role"),
        UniqueConstraint("pair_id", "role", name="uq_study_pair_member_role"),
    )

    pair_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("study_pair.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(1), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    consent_version: Mapped[str | None] = mapped_column(String, nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    questionnaire: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    important_attributes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # How this person thinks their roommate would answer the gameable items.
    roommate_ratings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # The eight outcome items (see services/study/instrument.py OUTCOME_ITEMS).
    outcomes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    months_together: Mapped[float | None] = mapped_column(Float, nullable=True)
    still_together: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    free_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pair: Mapped["StudyPair"] = relationship(back_populates="members")

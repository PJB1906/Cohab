"""Outcome logging — build plan §4 Phase 8; PRD §8.2's lifecycle diagram and
§9 screen 12.

PRD §8.2 only ever annotates "outcome logged" on the Cohabiting and Rejected
terminal transitions, so those are the only two states feedback can be
submitted from. Screen 12's "triggered at 30 and 90 days after Cohabiting" is
read as a *reminder cadence* for one eventual report, not two mandatory
submissions — reconciled against CLAUDE.md's `UNIQUE (score_id,
submitted_by)` invariant ("each participant reports once"), which the schema
has enforced since Phase 1. `pending_for` implements that cadence (gating
only *when the app prompts*); `submit` itself imposes no elapsed-time
requirement, since a voluntary early report (e.g. moved out after two weeks)
is itself informative and PRD names no reason to refuse it. See
docs/DECISIONS.md's Phase 8 section for the full reasoning.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import Feedback, MatchScore, User
from cohab.models.feedback import COHABITING_OUTCOMES, REJECTED_OUTCOMES
from cohab.services.match_access import load_match

# PRD §9 screen 12's first checkpoint. The 90-day checkpoint is a second
# reminder for the same still-unanswered report, not a second submission
# opportunity — nothing in pending_for distinguishes the two only the
# "hasn't submitted yet" check, which is true at both.
FEEDBACK_DUE_AFTER_DAYS = 30


class FeedbackError(Exception):
    pass


class NotEligibleForFeedback(FeedbackError):
    """The match hasn't reached Cohabiting or Rejected yet."""


class InvalidOutcome(FeedbackError):
    pass


class AlreadySubmitted(FeedbackError):
    pass


@dataclass(frozen=True)
class PendingFeedback:
    match_id: uuid.UUID
    other_user_id: uuid.UUID
    state: str


class FeedbackService:
    """Loads/authorizes via `match_access.load_match` rather than a local
    copy — `services/match_access.py` exists specifically so chat,
    contact-share and now feedback share one lookup+authorize primitive
    (and its `MatchNotFound`/`NotAParty` pair) rather than each keeping a
    copy a fix could miss (found in code review: this module had its own
    third copy)."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _days_since_cohabiting(self, row: MatchScore) -> int | None:
        if row.cohabiting_since is None:
            return None
        return max((datetime.now(timezone.utc) - row.cohabiting_since).days, 0)

    def submit(
        self,
        subject_user: User,
        match_id: uuid.UUID,
        outcome: str,
        cohabitation_duration_days: int | None = None,
    ) -> Feedback:
        row = load_match(self.session, subject_user, match_id)

        if row.state == "rejected":
            if outcome not in REJECTED_OUTCOMES:
                raise InvalidOutcome(outcome)
            duration = None
        elif row.state == "cohabiting":
            if outcome not in COHABITING_OUTCOMES:
                raise InvalidOutcome(outcome)
            if outcome == "still_together":
                # Computed server-side, never trusting a client-supplied
                # figure — this feeds Phase 9's Kaplan-Meier censoring time.
                duration = self._days_since_cohabiting(row)
            else:  # moved_out — the move-out date isn't otherwise observable
                duration = cohabitation_duration_days
        else:
            raise NotEligibleForFeedback(row.state)

        existing = self.session.scalar(
            select(Feedback).where(
                Feedback.match_score_id == row.id, Feedback.submitted_by == subject_user.id
            )
        )
        if existing is not None:
            raise AlreadySubmitted(match_id)

        feedback = Feedback(
            match_score_id=row.id,
            submitted_by=subject_user.id,
            outcome=outcome,
            cohabitation_duration_days=duration,
            submitted_at=datetime.now(timezone.utc),
        )
        self.session.add(feedback)
        self.session.commit()
        return feedback

    def pending_for(self, user: User) -> list[PendingFeedback]:
        """Matches where `user` is a party, the match is due for feedback
        (see module docstring), and `user` hasn't submitted yet."""
        stmt = select(MatchScore).where(
            (MatchScore.user_id_a == user.id) | (MatchScore.user_id_b == user.id),
            MatchScore.state.in_(("cohabiting", "rejected")),
        )
        due: list[PendingFeedback] = []
        for row in self.session.scalars(stmt).all():
            if row.state == "cohabiting":
                if row.cohabiting_since is None:
                    continue  # defensive — shouldn't happen once state is cohabiting
                if (datetime.now(timezone.utc) - row.cohabiting_since).days < FEEDBACK_DUE_AFTER_DAYS:
                    continue

            already = self.session.scalar(
                select(Feedback).where(
                    Feedback.match_score_id == row.id, Feedback.submitted_by == user.id
                )
            )
            if already is not None:
                continue

            other_id = row.user_id_b if row.user_id_a == user.id else row.user_id_a
            due.append(PendingFeedback(match_id=row.id, other_user_id=other_id, state=row.state))
        return due

"""Moderator queue — build plan §4 Phase 7, PRD §8.3 state machine / §9
screen 13.

Moderator auth reuses the reviewer's existing user session
(docs/DECISIONS.md D-7.1): `get_or_create_moderator` resolves the caller's
own `Moderator` audit row, creating it on first use rather than requiring a
separate provisioning step. Framework-free per CLAUDE.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from cohab.core.crypto import decrypt_message_safe
from cohab.models import Message, Moderator, Report, User
from cohab.models.safety import REPORT_SANCTIONS

__all__ = [
    "FlaggedMessage",
    "ModerationService",
    "NotAssignedModerator",
    "ReportNotFound",
    "ReportNotOpen",
    "ReportNotUnderReview",
    "SanctionRequired",
    "get_or_create_moderator",
]


class ModerationError(Exception):
    pass


class ReportNotFound(ModerationError):
    pass


class ReportNotOpen(ModerationError):
    """claim() requires the report to be `open`."""


class ReportNotUnderReview(ModerationError):
    """resolve() requires the report to already be claimed (`under_review`)."""


class SanctionRequired(ModerationError):
    """A `substantiated` finding requires a sanction (PRD §8.3: warn/suspend/ban)."""


class NotAssignedModerator(ModerationError):
    """resolve() requires the caller to be the moderator who claimed this
    report — claiming assigns responsibility for it; letting any other
    moderator close it out from under them would let two reviewers race to
    the same case with different verdicts."""


def get_or_create_moderator(session: Session, user: User) -> Moderator:
    moderator = session.scalar(select(Moderator).where(Moderator.user_id == user.id))
    if moderator is None:
        moderator = Moderator(user_id=user.id, name=user.full_name, email=user.email)
        session.add(moderator)
        try:
            session.flush()
        except IntegrityError:
            # Two near-simultaneous first-uses of `claim`/`resolve` from the
            # same newly-promoted moderator race on `Moderator.user_id`'s
            # unique constraint. Safe to fully rollback: this runs before
            # either caller has mutated the `Report` row it's about to
            # touch, so there's nothing else to lose.
            session.rollback()
            moderator = session.scalar(select(Moderator).where(Moderator.user_id == user.id))
    return moderator


@dataclass(frozen=True)
class FlaggedMessage:
    id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime


class ModerationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_reports(self, status: str | None = None) -> list[Report]:
        # Live, moderator-polled endpoint (unlike the offline scripts' N+1s
        # already accepted in D-9.6) — `_summary`/`_detail`
        # (api/moderation.py) dereference `.reporter`/`.reported_user` per
        # report, so this is two extra queries per row without eager
        # loading. `selectinload` over `joinedload`: avoids duplicate-row
        # fan-out from two to-one joins on the same query. D-10.3.
        stmt = (
            select(Report)
            .options(selectinload(Report.reporter), selectinload(Report.reported_user))
            .order_by(Report.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(Report.status == status)
        return list(self.session.scalars(stmt).all())

    def get_report(self, report_id: uuid.UUID) -> Report:
        # `session.get` doesn't accept loader options, so this needs a
        # `select` even for a single row — same eager-loading reasoning as
        # `list_reports` above (D-10.3): `_detail` also dereferences both.
        report = self.session.scalar(
            select(Report)
            .where(Report.id == report_id)
            .options(selectinload(Report.reporter), selectinload(Report.reported_user))
        )
        if report is None:
            raise ReportNotFound(report_id)
        return report

    def list_flagged_evidence(self, report: Report) -> list[FlaggedMessage]:
        """The reported user's flagged messages only (PRD §10: chat is
        server-readable *so that* it can be moderated) — not the whole
        thread, so disclosure stays scoped to what's actually evidence."""
        rows = self.session.scalars(
            select(Message)
            .where(Message.sender_id == report.reported_user_id, Message.flagged.is_(True))
            .order_by(Message.created_at)
        ).all()
        return [
            FlaggedMessage(
                id=m.id,
                sender_id=m.sender_id,
                body=decrypt_message_safe(m.body_encrypted),
                created_at=m.created_at,
            )
            for m in rows
        ]

    def claim(self, moderator_user: User, report_id: uuid.UUID) -> Report:
        """PRD §8.3: Open -> UnderReview, "moderator claims (SLA 24h)"."""
        report = self.get_report(report_id)
        if report.status != "open":
            raise ReportNotOpen(report_id)
        moderator = get_or_create_moderator(self.session, moderator_user)
        report.status = "under_review"
        report.assigned_moderator_id = moderator.id
        self.session.commit()
        # `commit()` expires every attribute on every session object
        # (default `expire_on_commit=True`), including the `reporter`/
        # `reported_user` relationships `get_report()` just eager-loaded —
        # the API layer's `_detail()` would otherwise re-trigger a fresh
        # lazy load per relationship on next access, reintroducing the N+1
        # this eager load exists to close (D-10.3). Re-fetching gives the
        # caller a non-expired, still-eager-loaded object.
        return self.get_report(report_id)

    def resolve(
        self,
        moderator_user: User,
        report_id: uuid.UUID,
        finding: str,
        sanction: str | None,
        note: str | None,
    ) -> Report:
        """PRD §8.3: UnderReview -> Substantiated/Dismissed ->
        ActionTaken/[*]. Finding (`status`) and sanction (`Report.sanction`)
        are recorded separately, per PRD's own framing: "so the audit trail
        shows what was concluded as well as what was done." """
        report = self.get_report(report_id)
        if report.status != "under_review":
            raise ReportNotUnderReview(report_id)
        moderator = get_or_create_moderator(self.session, moderator_user)
        if report.assigned_moderator_id != moderator.id:
            raise NotAssignedModerator(report_id)

        if finding == "dismissed":
            report.status = "dismissed"
            report.sanction = None
        elif finding == "substantiated":
            if sanction not in REPORT_SANCTIONS:
                raise SanctionRequired()
            report.status = "action_taken"
            report.sanction = sanction
            if sanction in ("suspend", "ban"):
                reported_user = self.session.get(User, report.reported_user_id)
                if reported_user is not None:
                    reported_user.account_status = "banned" if sanction == "ban" else "suspended"
        else:
            raise ValueError(f"unknown finding: {finding!r}")

        report.resolution_note = note
        report.resolved_at = datetime.now(timezone.utc)

        if report.status == "dismissed":
            self._maybe_reactivate(report.reported_user_id)

        # PRD §8.3: "reporter notified" — no notification channel exists
        # this phase (build plan defers it); a documented no-op, not a bug.
        self.session.commit()
        return self.get_report(report_id)  # re-fetch: see claim()'s comment on commit expiry (D-10.3)

    def _maybe_reactivate(self, reported_user_id: uuid.UUID) -> None:
        """A dismissal closes this case; if it was the only thing keeping
        the user suspended — the escalation suspend or the volume
        auto-suspend, both PRD §8.3, both explicitly framed as *pending
        review* — lift it. Never touches a `banned` account (a concluded
        sanction, not a pending one), and never reactivates while another
        open/under_review report against the same user remains."""
        user = self.session.get(User, reported_user_id)
        if user is None or user.account_status != "suspended":
            return
        still_open = self.session.scalar(
            select(Report.id).where(
                Report.reported_user_id == reported_user_id,
                Report.status.in_(("open", "under_review")),
            )
        )
        if still_open is None:
            user.account_status = "active"

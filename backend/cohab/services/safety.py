"""Reporting and blocking — build plan §4 Phase 7, PRD §8.3 / §10.

Framework-free per CLAUDE.md: raises plain exceptions, the API layer maps
them to HTTP status codes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cohab.core.config import REPORT_AUTOSUSPEND_THRESHOLD, REPORT_RATE_LIMIT_PER_DAY
from cohab.models import Report, User, UserBlock
from cohab.models.safety import ESCALATING_REASONS

# PRD §8.3: "repeated reports by one user against the same person collapse
# into a single case" — only while the earlier case is still live. A report
# that's already been through review is a closed case; a fresh filing after
# that is a new incident, not a continuation.
_OPEN_REPORT_STATUSES = ("open", "under_review")

# The volume trigger ("three or more independent reports... trigger
# automatic temporary suspension", PRD §8.3) counts reports that haven't
# been found groundless. A `dismissed` report was reviewed and rejected — it
# shouldn't go on counting as evidence toward suspending someone.
_COUNTS_TOWARD_AUTOSUSPEND = ("open", "under_review", "substantiated", "action_taken")


class SafetyError(Exception):
    pass


class CannotReportSelf(SafetyError):
    pass


class ReportedUserNotFound(SafetyError):
    pass


class ReportRateLimited(SafetyError):
    pass


class CannotBlockSelf(SafetyError):
    pass


class BlockedUserNotFound(SafetyError):
    pass


def _maybe_suspend(user: User) -> None:
    """Suspend only from `active` — never downgrades an existing `banned`
    sanction back to `suspended`, and is a no-op if already suspended."""
    if user.account_status == "active":
        user.account_status = "suspended"


class ReportService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _autosuspend_reporter_count(self, reported_user_id: uuid.UUID) -> int:
        return (
            self.session.scalar(
                select(func.count(func.distinct(Report.reporter_id))).where(
                    Report.reported_user_id == reported_user_id,
                    Report.status.in_(_COUNTS_TOWARD_AUTOSUSPEND),
                )
            )
            or 0
        )

    def file_report(
        self,
        reporter: User,
        reported_user_id: uuid.UUID,
        reason: str,
        details: str | None,
    ) -> Report:
        if reporter.id == reported_user_id:
            raise CannotReportSelf()
        reported_user = self.session.get(User, reported_user_id)
        if reported_user is None:
            raise ReportedUserNotFound(reported_user_id)

        existing = self.session.scalar(
            select(Report).where(
                Report.reporter_id == reporter.id,
                Report.reported_user_id == reported_user_id,
                Report.status.in_(_OPEN_REPORT_STATUSES),
            )
        )
        if existing is not None:
            existing.reason = reason
            existing.details = details
            report = existing
        else:
            window_start = datetime.now(timezone.utc) - timedelta(days=1)
            recent = (
                self.session.scalar(
                    select(func.count())
                    .select_from(Report)
                    .where(Report.reporter_id == reporter.id, Report.created_at >= window_start)
                )
                or 0
            )
            if recent >= REPORT_RATE_LIMIT_PER_DAY:
                raise ReportRateLimited()
            report = Report(
                reporter_id=reporter.id,
                reported_user_id=reported_user_id,
                reason=reason,
                details=details,
                status="open",
            )
            self.session.add(report)

        # Escalation is monotonic — a later, calmer follow-up from the same
        # reporter never un-escalates an already-escalated case.
        if reason in ESCALATING_REASONS:
            report.escalated = True
            _maybe_suspend(reported_user)

        self.session.flush()
        if self._autosuspend_reporter_count(reported_user_id) >= REPORT_AUTOSUSPEND_THRESHOLD:
            _maybe_suspend(reported_user)

        self.session.commit()
        return report


class BlockService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _find(self, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> UserBlock | None:
        return self.session.scalar(
            select(UserBlock).where(
                UserBlock.blocker_id == blocker_id, UserBlock.blocked_id == blocked_id
            )
        )

    def block(self, blocker: User, blocked_id: uuid.UUID) -> UserBlock:
        if blocker.id == blocked_id:
            raise CannotBlockSelf()
        if self.session.get(User, blocked_id) is None:
            raise BlockedUserNotFound(blocked_id)

        existing = self._find(blocker.id, blocked_id)
        if existing is None:
            existing = UserBlock(blocker_id=blocker.id, blocked_id=blocked_id)
            self.session.add(existing)
            self.session.commit()
        return existing

    def unblock(self, blocker: User, blocked_id: uuid.UUID) -> None:
        # Only ever deletes the blocker's own row — PRD §10: blocking
        # "cannot be undone by the blocked party." A blocked user calling
        # this with the blocker's id finds no row of theirs to delete.
        row = self._find(blocker.id, blocked_id)
        if row is not None:
            self.session.delete(row)
            self.session.commit()

    def list_blocked(self, blocker: User) -> list[User]:
        """The full `User` rows, not just ids — the one caller of this
        (the "who have I blocked" screen, PRD §10: blocking "cannot be
        undone by the blocked party," which implies the blocker *can* undo
        it, and needs somewhere to do that from) has to display who each
        block actually is, not a bare UUID."""
        return list(
            self.session.scalars(
                select(User)
                .join(UserBlock, UserBlock.blocked_id == User.id)
                .where(UserBlock.blocker_id == blocker.id)
                .order_by(User.full_name)
            ).all()
        )


def blocked_pairs_for(session: Session, user_id: uuid.UUID) -> frozenset[frozenset[uuid.UUID]]:
    """Every pair `{user_id, other}` blocked in *either* direction — feeds
    `MatchRanker(blocked_pairs=...)` / `EligibilityFilter` (Stage 1, spec §2).
    Scoped to `user_id` rather than the whole table: `EligibilityFilter.filter`
    is only ever called with one subject at a time, so only blocks touching
    that subject can ever matter to the pool it's filtering.
    """
    rows = session.scalars(
        select(UserBlock).where(
            (UserBlock.blocker_id == user_id) | (UserBlock.blocked_id == user_id)
        )
    ).all()
    return frozenset(frozenset({row.blocker_id, row.blocked_id}) for row in rows)


def is_blocked_between(session: Session, a_id: uuid.UUID, b_id: uuid.UUID) -> bool:
    return (
        session.scalar(
            select(UserBlock).where(
                ((UserBlock.blocker_id == a_id) & (UserBlock.blocked_id == b_id))
                | ((UserBlock.blocker_id == b_id) & (UserBlock.blocked_id == a_id))
            )
        )
        is not None
    )

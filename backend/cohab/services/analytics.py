"""Institutional analytics — build plan §4 Phase 8, PRD §3.2's Dr Sathya
persona ("aggregated visibility into whether students are housed and where
problems cluster. Read-only, anonymised").

PRD §4 formally scopes the "institutional analytics dashboard" to v2, and §9's
v1 screen table has no dashboard screen — this exists anyway because the
build plan names it explicitly in Phase 8, and Dr Sathya's persona describes
some minimal visibility as "the reason institutions cooperate with the
pilot." Deliberately minimal: aggregate counts already implied by tables
that exist, gated by the same `is_moderator` flag Phase 7 already uses for
the moderation queue — no new institution-admin actor is introduced, no
per-user drill-down, no exports. Full survival analysis (Kaplan-Meier over
`feedback`) is Phase 9's evaluation chapter, not here — this only counts.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cohab.models import MatchScore, Report, User
from cohab.models.matching import MATCH_STATES
from cohab.models.safety import REPORT_STATUSES
from cohab.models.user import ACCOUNT_STATUSES, VERIFICATION_STATUSES


@dataclass(frozen=True)
class AnalyticsSummary:
    members_by_verification_status: dict[str, int]
    members_by_account_status: dict[str, int]
    matches_by_state: dict[str, int]
    reports_by_status: dict[str, int]


def _counts(session: Session, column, all_values: tuple[str, ...]) -> dict[str, int]:
    rows = session.execute(select(column, func.count()).group_by(column)).all()
    counts = {value: 0 for value in all_values}
    counts.update({value: count for value, count in rows})
    return counts


def summary(session: Session) -> AnalyticsSummary:
    return AnalyticsSummary(
        members_by_verification_status=_counts(session, User.verification_status, VERIFICATION_STATUSES),
        members_by_account_status=_counts(session, User.account_status, ACCOUNT_STATUSES),
        matches_by_state=_counts(session, MatchScore.state, MATCH_STATES),
        reports_by_status=_counts(session, Report.status, REPORT_STATUSES),
    )

"""GET /analytics/summary — build plan §4 Phase 8. Gated by `require_moderator`,
same as the Phase 7 moderation queue (docs/DECISIONS.md D-7.1) — no separate
institution-admin actor exists, so this reuses the one privileged role the
platform already has.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_moderator
from cohab.api.schemas import AnalyticsSummaryOut, FunnelOut, FunnelStageOut
from cohab.models import User
from cohab.services.analytics import summary
from cohab.services.funnel import funnel

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummaryOut)
def get_summary(
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
) -> AnalyticsSummaryOut:
    s = summary(db)
    return AnalyticsSummaryOut(
        members_by_verification_status=s.members_by_verification_status,
        members_by_account_status=s.members_by_account_status,
        matches_by_state=s.matches_by_state,
        reports_by_status=s.reports_by_status,
    )


@router.get("/funnel", response_model=FunnelOut)
def get_funnel(
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
) -> FunnelOut:
    """v2 W1: suggested -> cohabiting funnel with median stage durations,
    built from the append-only `match_state_event` log. Aggregate only."""
    f = funnel(db)
    return FunnelOut(
        total_matches=f.total_matches,
        stages=[FunnelStageOut(**st.__dict__) for st in f.stages],
        rejected=f.rejected,
        rejection_reasons=f.rejection_reasons,
    )

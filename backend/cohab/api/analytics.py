"""GET /analytics/summary — build plan §4 Phase 8. Gated by `require_moderator`,
same as the Phase 7 moderation queue (docs/DECISIONS.md D-7.1) — no separate
institution-admin actor exists, so this reuses the one privileged role the
platform already has.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_moderator
from cohab.api.schemas import AnalyticsSummaryOut
from cohab.models import User
from cohab.services.analytics import summary

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

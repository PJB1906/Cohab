"""GET/POST /moderation/reports/* — build plan §4 Phase 7, PRD §8.3 / §9
screen 13. Every route requires `require_moderator`
(docs/DECISIONS.md D-7.1: `is_moderator` flag on the caller's own account,
same session cookie as everything else — no separate moderator login).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_moderator
from cohab.api.schemas import (
    FlaggedMessageOut,
    ReportDetailOut,
    ReportSummaryOut,
    ResolveReportRequest,
)
from cohab.models import Report, User
from cohab.models.safety import REPORT_STATUSES
from cohab.services.moderation_queue import (
    ModerationService,
    NotAssignedModerator,
    ReportNotFound,
    ReportNotOpen,
    ReportNotUnderReview,
    SanctionRequired,
)

router = APIRouter(prefix="/moderation", tags=["moderation"])


def _summary(r: Report) -> ReportSummaryOut:
    return ReportSummaryOut(
        id=r.id,
        reporter_name=r.reporter.full_name,
        reported_user_name=r.reported_user.full_name,
        reason=r.reason,
        status=r.status,
        escalated=r.escalated,
        created_at=r.created_at,
    )


def _detail(service: ModerationService, r: Report) -> ReportDetailOut:
    evidence = service.list_flagged_evidence(r)
    return ReportDetailOut(
        id=r.id,
        reporter_id=r.reporter_id,
        reporter_name=r.reporter.full_name,
        reported_user_id=r.reported_user_id,
        reported_user_name=r.reported_user.full_name,
        reason=r.reason,
        details=r.details,
        status=r.status,
        escalated=r.escalated,
        resolution_note=r.resolution_note,
        sanction=r.sanction,
        created_at=r.created_at,
        resolved_at=r.resolved_at,
        evidence=[
            FlaggedMessageOut(id=m.id, sender_id=m.sender_id, body=m.body, created_at=m.created_at)
            for m in evidence
        ],
    )


@router.get("/reports", response_model=list[ReportSummaryOut])
def list_reports(
    report_status: Literal[REPORT_STATUSES] | None = None,  # type: ignore[valid-type]
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
) -> list[ReportSummaryOut]:
    reports = ModerationService(db).list_reports(status=report_status)
    return [_summary(r) for r in reports]


@router.get("/reports/{report_id}", response_model=ReportDetailOut)
def get_report(
    report_id: uuid.UUID,
    _moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
) -> ReportDetailOut:
    service = ModerationService(db)
    try:
        r = service.get_report(report_id)
    except ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such report")
    return _detail(service, r)


@router.post("/reports/{report_id}/claim", response_model=ReportDetailOut)
def claim_report(
    report_id: uuid.UUID,
    moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
) -> ReportDetailOut:
    service = ModerationService(db)
    try:
        r = service.claim(moderator, report_id)
    except ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such report")
    except ReportNotOpen:
        raise HTTPException(status.HTTP_409_CONFLICT, "report is not open")
    return _detail(service, r)


@router.post("/reports/{report_id}/resolve", response_model=ReportDetailOut)
def resolve_report(
    report_id: uuid.UUID,
    body: ResolveReportRequest,
    moderator: User = Depends(require_moderator),
    db: Session = Depends(get_db),
) -> ReportDetailOut:
    service = ModerationService(db)
    try:
        r = service.resolve(moderator, report_id, body.finding, body.sanction, body.note)
    except ReportNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such report")
    except ReportNotUnderReview:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "report must be claimed before it can be resolved"
        )
    except NotAssignedModerator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the moderator who claimed this report can resolve it")
    except SanctionRequired:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "a substantiated finding requires a sanction")
    return _detail(service, r)

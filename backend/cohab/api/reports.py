"""POST /reports, POST/DELETE/GET /blocks — build plan §4 Phase 7, PRD
§8.3 / §9 screen 11 / §10.

Thin per CLAUDE.md: validate, call `ReportService`/`BlockService`, serialise.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_verified_user
from cohab.api.schemas import BlockRequest, ReportOut, ReportRequest
from cohab.models import User
from cohab.services.safety import (
    BlockedUserNotFound,
    BlockService,
    CannotBlockSelf,
    CannotReportSelf,
    ReportedUserNotFound,
    ReportRateLimited,
    ReportService,
)

router = APIRouter(tags=["safety"])


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def file_report(
    body: ReportRequest,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = ReportService(db).file_report(user, body.reported_user_id, body.reason, body.details)
    except CannotReportSelf:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "you can't report yourself")
    except ReportedUserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such user")
    except ReportRateLimited:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too many reports filed recently")
    return ReportOut(id=report.id, status=report.status, escalated=report.escalated)


@router.post("/blocks", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def create_block(
    body: BlockRequest,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        BlockService(db).block(user, body.blocked_id)
    except CannotBlockSelf:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "you can't block yourself")
    except BlockedUserNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such user")


@router.delete("/blocks/{blocked_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_block(
    blocked_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> None:
    # No error on a missing row — PRD §10: unblocking is the blocker's own
    # action and idempotent either way (BlockService.unblock is a no-op if
    # there's nothing of the caller's to delete, including when the *other*
    # party was the one who did the original blocking).
    BlockService(db).unblock(user, blocked_id)


@router.get("/blocks", response_model=list[uuid.UUID])
def list_blocks(
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> list[uuid.UUID]:
    return BlockService(db).list_blocked(user)

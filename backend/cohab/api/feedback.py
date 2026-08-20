"""POST /matches/{id}/feedback, GET /feedback/pending — build plan §4 Phase 8.

Thin per CLAUDE.md: validate, call `FeedbackService`, serialise.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_verified_user
from cohab.api.schemas import FeedbackOut, FeedbackRequest, PendingFeedbackOut
from cohab.models import User
from cohab.services.feedback import (
    AlreadySubmitted,
    FeedbackService,
    InvalidOutcome,
    NotEligibleForFeedback,
)
from cohab.services.match_access import MatchNotFound, NotAParty

router = APIRouter(tags=["feedback"])


@router.post("/matches/{match_id}/feedback", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    match_id: uuid.UUID,
    body: FeedbackRequest,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> FeedbackOut:
    try:
        feedback = FeedbackService(db).submit(user, match_id, body.outcome, body.cohabitation_duration_days)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except NotEligibleForFeedback:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "this match hasn't reached a state feedback can be given for"
        )
    except InvalidOutcome:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid outcome for this match's state")
    except AlreadySubmitted:
        raise HTTPException(status.HTTP_409_CONFLICT, "you've already submitted feedback for this match")
    return FeedbackOut(
        id=feedback.id,
        outcome=feedback.outcome,
        cohabitation_duration_days=feedback.cohabitation_duration_days,
        submitted_at=feedback.submitted_at,
    )


@router.get("/feedback/pending", response_model=list[PendingFeedbackOut])
def list_pending_feedback(
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> list[PendingFeedbackOut]:
    pending = FeedbackService(db).pending_for(user)
    others = {p.other_user_id: db.get(User, p.other_user_id) for p in pending}
    return [
        PendingFeedbackOut(
            match_id=p.match_id,
            other_user_id=p.other_user_id,
            other_user_name=(others[p.other_user_id].full_name if others[p.other_user_id] else ""),
            state=p.state,
        )
        for p in pending
    ]

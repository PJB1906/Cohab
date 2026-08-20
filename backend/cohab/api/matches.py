"""GET /matches, GET /matches/{id}/explanation — build plan §4 Phase 4.

The live API's `_notes` fallback (`attributes.py`) uses a plain neutral
comparator, never a live TF-IDF transform: with the profile-save path now
always populating `text_vector` (D-4.x), a live-transform fallback here would
be the one remaining place text ever gets encoded inside the match request
path. Keeping it neutral makes CLAUDE.md's "never encode in the request
path" rule absolute rather than "usually true".
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_active_weight_set, get_db, require_verified_user
from cohab.api.schemas import (
    ExplanationCard,
    ExpressInterestResponse,
    MatchExplanationResponse,
    MatchListingSummary,
    MatchListItem,
)
from cohab.models import User, WeightSet
from cohab.services.match_access import PairBlocked
from cohab.services.matches import (
    InvalidStateTransition,
    MatchesService,
    MatchNotFound,
    NotAParty,
)
from cohab.services.matching.text import NeutralTextSimilarity

router = APIRouter(prefix="/matches", tags=["matches"])


def _service(db: Session, weight_set: WeightSet) -> MatchesService:
    return MatchesService(db, weight_set, NeutralTextSimilarity())


@router.get("", response_model=list[MatchListItem])
def get_matches(
    # Default proposed — not specified in PRD/spec (matcher-reviewer finding).
    # Upper bound of 5000 sits above the "effectively unlimited" 3000 both
    # `recompute.py` (`RECOMPUTE_LIMIT`) and the test suite (`LARGE_LIMIT`)
    # already rely on, not a real usage cap.
    limit: int = Query(default=10, ge=1, le=5000),
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> list[MatchListItem]:
    entries = _service(db, weight_set).get_matches(user, limit=limit)
    return [
        MatchListItem(
            match_id=e.match_id,
            candidate_id=e.candidate.user_id,
            candidate_name=e.candidate.name,
            combined_score=e.combined_score,
            agreements=[c.text for c in e.explanation.agreements],
            divergence=e.explanation.divergence.text if e.explanation.divergence else None,
            seeker_type=e.candidate.seeker_type,
            city=e.candidate.city,
            budget_min=e.candidate.budget_min,
            budget_max=e.candidate.budget_max,
            avatar_url=e.candidate.avatar_url,
        )
        for e in entries
    ]


@router.get("/{match_id}/explanation", response_model=MatchExplanationResponse)
def get_explanation(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> MatchExplanationResponse:
    try:
        r = _service(db, weight_set).get_explanation(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this match is not available")

    return MatchExplanationResponse(
        match_id=r.match_id,
        candidate_id=r.candidate.user_id,
        candidate_name=r.candidate.name,
        combined_score=r.result.combined_score,
        score_towards_candidate=r.result.score_ab,
        score_from_candidate=r.result.score_ba,
        breakdown=r.result.breakdown,
        agreements=[
            ExplanationCard(attribute=c.attribute, kind=c.kind, text=c.text, score=c.score)
            for c in r.explanation.agreements
        ],
        divergence=(
            ExplanationCard(
                attribute=r.explanation.divergence.attribute,
                kind=r.explanation.divergence.kind,
                text=r.explanation.divergence.text,
                score=r.explanation.divergence.score,
            )
            if r.explanation.divergence
            else None
        ),
        state=r.state,
        you_expressed_interest=r.you_expressed_interest,
        candidate_course=r.candidate.course,
        candidate_avatar_url=r.candidate.avatar_url,
        listing=(
            MatchListingSummary(
                locality=r.listing.locality,
                rent_per_person=r.listing.rent_per_person,
                deposit=r.listing.deposit,
                room_type=r.listing.room_type,
                available_from=r.listing.available_from,
                amenities=list(r.listing.amenities or []),
                photos=list(r.listing.photos or []),
            )
            if r.listing is not None
            else None
        ),
    )


@router.post("/{match_id}/interest", response_model=ExpressInterestResponse)
def express_interest(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> ExpressInterestResponse:
    try:
        state = _service(db, weight_set).express_interest(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this match is not available")
    except InvalidStateTransition:
        raise HTTPException(status.HTTP_409_CONFLICT, "this match is settled and can't be reopened")
    return ExpressInterestResponse(state=state)


@router.post("/{match_id}/confirm-move-in", response_model=ExpressInterestResponse)
def confirm_move_in(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> ExpressInterestResponse:
    try:
        state = _service(db, weight_set).confirm_move_in(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this match is not available")
    except InvalidStateTransition:
        raise HTTPException(status.HTTP_409_CONFLICT, "move-in can only be confirmed after contact is shared")
    return ExpressInterestResponse(state=state)


@router.post("/{match_id}/reject", response_model=ExpressInterestResponse)
def reject(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> ExpressInterestResponse:
    try:
        state = _service(db, weight_set).reject(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this match is not available")
    except InvalidStateTransition:
        raise HTTPException(status.HTTP_409_CONFLICT, "this match can no longer be rejected")
    return ExpressInterestResponse(state=state)

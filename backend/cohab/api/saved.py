"""POST/DELETE/GET /saved — bookmark a match to compare later.

New scope, ported from the mobile mockup's "Saved" tab (not in
`docs/COHAB_PRD.md`/`docs/COHAB_MATCHING_SPEC.md` — see services/saved.py).
Thin per CLAUDE.md, same structure as `api/chat.py`: validate, call
`SavedService`, serialise.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_verified_user
from cohab.api.schemas import MatchListItem, SavedMatchOut
from cohab.models import User
from cohab.services.match_access import MatchNotFound, NotAParty
from cohab.services.saved import SavedMatchEntry, SavedService

router = APIRouter(prefix="/saved", tags=["saved"])


def _to_out(entry: SavedMatchEntry) -> SavedMatchOut:
    return SavedMatchOut(
        saved_at=entry.saved_at,
        match=MatchListItem(
            match_id=entry.match_id,
            candidate_id=entry.candidate.user_id,
            candidate_name=entry.candidate.name,
            combined_score=entry.combined_score,
            agreements=[c.text for c in entry.explanation.agreements],
            divergence=entry.explanation.divergence.text if entry.explanation.divergence else None,
            seeker_type=entry.candidate.seeker_type,
            city=entry.candidate.city,
            budget_min=entry.candidate.budget_min,
            budget_max=entry.candidate.budget_max,
            avatar_url=entry.candidate.avatar_url,
            state=entry.state,
            course=entry.candidate.course,
            move_in_date=entry.candidate.move_in_date,
            listing_room_type=entry.candidate.listing_room_type,
            listing_available_from=entry.candidate.listing_available_from,
        ),
    )


@router.post("/{match_id}", response_model=MatchListItem)
def save_match(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> MatchListItem:
    try:
        entry = SavedService(db).save(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    return _to_out(entry).match


@router.delete("/{match_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def unsave_match(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> None:
    SavedService(db).unsave(user, match_id)


@router.get("", response_model=list[SavedMatchOut])
def list_saved_matches(
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> list[SavedMatchOut]:
    entries = SavedService(db).list_saved(user)
    return [_to_out(e) for e in entries]

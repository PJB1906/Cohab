"""GET /listing, PUT /listing — build plan §4 Phase 4 (extended scope, see
docs/DECISIONS.md). Requires verified+active, unlike /profile: a listing only
matters once its owner is actually eligible to be matched."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_verified_user
from cohab.api.schemas import ListingOut, ListingUpsertRequest
from cohab.models import User
from cohab.services.listing import ListingService, NotHasPlace

router = APIRouter(prefix="/listing", tags=["listing"])


@router.get("", response_model=ListingOut)
def get_listing(user: User = Depends(require_verified_user), db: Session = Depends(get_db)) -> ListingOut:
    listing = ListingService(db).get(user)
    if listing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no listing saved yet")
    return listing


@router.put("", response_model=ListingOut)
def put_listing(
    body: ListingUpsertRequest,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> ListingOut:
    try:
        return ListingService(db).save(user, body)
    except NotHasPlace:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "only has_place accounts can create a listing")

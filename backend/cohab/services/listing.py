"""Listing CRUD — build plan §4 Phase 4 (in scope per this session's
decision: a `has_place` user can't pass Stage 1 without a listing row,
`Candidate.from_orm` reads it for the effective budget band)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.api.schemas import ListingUpsertRequest
from cohab.models import Listing, User


class ListingError(Exception):
    pass


class NotHasPlace(ListingError):
    """A needs_place user has nothing to list (PRD §5.1/§9 screen 3)."""


class ListingService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user: User) -> Listing | None:
        return self.session.scalar(select(Listing).where(Listing.user_id == user.id))

    def save(self, user: User, payload: ListingUpsertRequest) -> Listing:
        if user.seeker_type != "has_place":
            raise NotHasPlace(user.seeker_type)

        listing = self.get(user)
        if listing is None:
            listing = Listing(user_id=user.id)
            self.session.add(listing)

        listing.locality = payload.locality
        listing.rent_per_person = payload.rent_per_person
        listing.deposit = payload.deposit
        listing.room_type = payload.room_type
        listing.available_from = payload.available_from
        listing.amenities = payload.amenities
        listing.photos = payload.photos
        listing.current_housemates = payload.current_housemates

        self.session.commit()
        return listing

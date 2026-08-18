"""GET /profile, PUT /profile — build plan §4 Phase 4.

Requires login only (`get_current_user`), not verification: saving the
profile is *how* a user becomes eligible for matching, so it can't itself be
gated on being verified. Listing and matches, which only make sense once
verified, use `require_verified_user` instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.api.deps import get_current_user, get_db, get_text_encoder
from cohab.api.schemas import ProfileOut, ProfileUpsertRequest
from cohab.models import PreferenceProfile, User, UserAttributeWeight
from cohab.services.matching.text import TfidfSimilarity
from cohab.services.profile import ProfileService, UnknownImportantAttribute

router = APIRouter(prefix="/profile", tags=["profile"])


def _important_attributes(db: Session, user: User) -> list[str]:
    return list(
        db.scalars(
            select(UserAttributeWeight.attribute_name).where(
                UserAttributeWeight.user_id == user.id,
                UserAttributeWeight.is_selected_important.is_(True),
            )
        ).all()
    )


def _to_out(profile: PreferenceProfile, important_attributes: list[str]) -> ProfileOut:
    return ProfileOut(
        city=profile.city,
        budget_min=profile.budget_min,
        budget_max=profile.budget_max,
        move_in_date=profile.move_in_date,
        gender_preference=profile.gender_preference,
        severe_allergy=list(profile.severe_allergy or []),
        kitchen_allergens=list(profile.kitchen_allergens or []),
        has_pet=profile.has_pet,
        pet_tolerance=profile.pet_tolerance,
        smoking_dealbreaker=profile.smoking_dealbreaker,
        questionnaire=dict(profile.questionnaire or {}),
        important_attributes=important_attributes,
    )


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ProfileOut:
    profile = db.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no profile saved yet")
    return _to_out(profile, _important_attributes(db, user))


@router.put("", response_model=ProfileOut)
def put_profile(
    body: ProfileUpsertRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    text_encoder: TfidfSimilarity = Depends(get_text_encoder),
) -> ProfileOut:
    service = ProfileService(db, text_encoder)
    try:
        profile = service.save(user, body)
    except UnknownImportantAttribute as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown attribute name(s): {exc.args[0]}")
    return _to_out(profile, list(body.important_attributes))

"""PreferenceProfile CRUD, including the text-vector cache-on-save (CLAUDE.md,
spec §7) and the importance-weighting write (spec §3 screen 6, bundled here
rather than a separate endpoint — one small table write, not a distinct
workflow).
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cohab.api.schemas import ProfileUpsertRequest
from cohab.models import PreferenceProfile, User, UserAttributeWeight
from cohab.services.matching.attributes import ATTRIBUTES
from cohab.services.matching.text import TfidfSimilarity

TEXT_VECTOR_KIND = "tfidf"  # the only encoder Phase 4 wires up (D-4.x)


class ProfileError(Exception):
    pass


class UnknownImportantAttribute(ProfileError):
    pass


class ProfileService:
    def __init__(self, session: Session, text_encoder: TfidfSimilarity) -> None:
        self.session = session
        self.text_encoder = text_encoder

    def get(self, user: User) -> PreferenceProfile | None:
        return self.session.scalar(
            select(PreferenceProfile).where(PreferenceProfile.user_id == user.id)
        )

    def save(self, user: User, payload: ProfileUpsertRequest) -> PreferenceProfile:
        unknown = set(payload.important_attributes) - set(ATTRIBUTES)
        if unknown:
            raise UnknownImportantAttribute(sorted(unknown))

        profile = self.get(user)
        if profile is None:
            profile = PreferenceProfile(user_id=user.id)
            self.session.add(profile)

        profile.city = payload.city
        profile.budget_min = payload.budget_min
        profile.budget_max = payload.budget_max
        profile.move_in_date = payload.move_in_date
        profile.gender_preference = payload.gender_preference
        profile.severe_allergy = payload.severe_allergy
        profile.kitchen_allergens = payload.kitchen_allergens
        profile.has_pet = payload.has_pet
        profile.pet_tolerance = payload.pet_tolerance
        profile.smoking_dealbreaker = payload.smoking_dealbreaker
        profile.questionnaire = payload.questionnaire

        notes = payload.questionnaire.get("lifestyle_notes")
        vector = self.text_encoder.encode(notes)
        profile.text_vector = vector
        profile.text_vector_kind = TEXT_VECTOR_KIND if vector is not None else None

        self.session.execute(
            delete(UserAttributeWeight).where(UserAttributeWeight.user_id == user.id)
        )
        for name in payload.important_attributes:
            self.session.add(
                UserAttributeWeight(user_id=user.id, attribute_name=name, is_selected_important=True)
            )

        self.session.commit()
        return profile

"""GET/PUT /me/taste — what Cohab has learned from your decisions, and the
switch to turn it off (services/taste.py, D-14.22)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from cohab.api.deps import get_active_weight_set, get_db, require_verified_user
from cohab.models import User, UserTaste, WeightSet
from cohab.services import taste

router = APIRouter(prefix="/me/taste", tags=["taste"])


class TasteWeightOut(BaseModel):
    attribute: str
    label: str
    stated: float
    learned: float
    shift: float


class TasteInsightOut(BaseModel):
    attribute: str
    direction: str
    text: str


class TasteOut(BaseModel):
    enabled: bool
    active: bool
    decisions: int
    positives: int
    negatives: int
    needed: int  # more decisions before learning starts (0 once active)
    weights: list[TasteWeightOut]
    insights: list[TasteInsightOut]


class TasteToggleIn(BaseModel):
    enabled: bool


def _out(db: Session, user: User, weight_set: WeightSet) -> TasteOut:
    row = db.get(UserTaste, user.id)
    if row is None or not row.model:
        model = taste.refresh(db, user, weight_set.weights)
        db.commit()
        row = db.get(UserTaste, user.id)
    else:
        model = taste.TasteModel.from_json(row.model)
    needed = 0 if model.active else max(
        taste.MIN_DECISIONS - model.decisions,
        max(0, taste.MIN_EACH - model.positives) + max(0, taste.MIN_EACH - model.negatives),
    )
    shifts = model.shifts()
    weights = sorted(
        (
            TasteWeightOut(
                attribute=a,
                label=taste.ATTRIBUTE_LABELS.get(a, a.replace("_", " ")),
                stated=model.stated[a],
                learned=model.learned[a],
                shift=shifts[a],
            )
            for a in model.attributes
        ),
        key=lambda w: -w.learned,
    )
    return TasteOut(
        enabled=row.enabled,
        active=model.active,
        decisions=model.decisions,
        positives=model.positives,
        negatives=model.negatives,
        needed=needed,
        weights=weights,
        insights=[TasteInsightOut(**i) for i in taste.insights(model)],
    )


@router.get("", response_model=TasteOut)
def get_taste(
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> TasteOut:
    return _out(db, user, weight_set)


@router.put("", response_model=TasteOut)
def set_taste(
    body: TasteToggleIn,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> TasteOut:
    row = db.get(UserTaste, user.id)
    if row is None:
        taste.refresh(db, user, weight_set.weights)
        row = db.get(UserTaste, user.id)
    row.enabled = body.enabled
    db.commit()
    return _out(db, user, weight_set)

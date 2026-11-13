"""/study/* — Cohab Lab and roommate-pair study (Cohab v2 plan W2/W3).

Outside the product: no session cookie, no product account. The study token
travels in the `X-Study-Token` header (never a URL query string, which ends
up in logs and browser history). Admin routes reuse `require_moderator`.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_moderator
from cohab.core.ratelimit import limit_study_creation
from cohab.models import StudyPair, StudyPairMember, StudyRater, StudyResponse, StudyTrial, User
from cohab.services.study import instrument
from cohab.services.study.export import load_pairs, load_raters, to_json
from cohab.services.study.service import (
    InvalidInput,
    LabService,
    NotReady,
    PairService,
    StudyClosed,
    UnknownToken,
    study_enabled,
)

router = APIRouter(prefix="/study", tags=["study"])


def _errors(fn):
    try:
        return fn()
    except StudyClosed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "the study is closed")
    except UnknownToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown or withdrawn study token")
    except NotReady as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except InvalidInput as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"problems": exc.problems})


# --- schemas ------------------------------------------------------------------


class InstrumentOut(BaseModel):
    open: bool
    consent_version: str
    pair_consent_version: str
    rater_fields: list[str]
    card_fields: list[str]
    study_attributes: list[str]
    gameable_fields: list[str]
    outcome_items: dict[str, str]


class TokenOut(BaseModel):
    token: str


class CreateRaterIn(BaseModel):
    cohort: str = Field(default="main", max_length=40)


class ConsentIn(BaseModel):
    consent_version: str


class RaterProfileIn(BaseModel):
    answers: dict[str, str]
    important_attributes: list[str] = Field(default_factory=list, max_length=3)
    demographics: dict[str, str] = Field(default_factory=dict)


class ProgressOut(BaseModel):
    answered: int
    total: int
    consented: bool
    profile_done: bool
    completed: bool


class CardOut(BaseModel):
    id: str
    answers: dict[str, str]


class TrialOut(BaseModel):
    trial_id: uuid.UUID
    kind: str
    cards: list[CardOut]


class NextOut(BaseModel):
    trial: TrialOut | None
    progress: ProgressOut


class ResponseIn(BaseModel):
    choice: Literal["left", "right", "none"] | None = None
    ranking: list[str] | None = None
    confidence: int | None = Field(default=None, ge=1, le=5)
    would_message: Literal["left", "right", "both", "neither"] | None = None
    reason_text: str | None = Field(default=None, max_length=140)
    response_ms: int | None = None


class PairCreatedOut(BaseModel):
    token: str
    invite_token: str


class JoinIn(BaseModel):
    invite_token: str


class PairSubmitIn(BaseModel):
    consent_version: str
    answers: dict[str, str]
    important_attributes: list[str] = Field(default_factory=list, max_length=3)
    roommate_ratings: dict[str, str]
    outcomes: dict[str, int]
    months_together: float
    still_together: bool


class PairStatusOut(BaseModel):
    role: str
    submitted: bool
    roommate_joined: bool
    roommate_submitted: bool


class StudySummaryOut(BaseModel):
    open: bool
    raters_started: int
    raters_consented: int
    raters_completed: int
    responses: int
    pairs_created: int
    pairs_complete: int
    synthetic_raters: int


# --- public ---------------------------------------------------------------------


@router.get("/instrument", response_model=InstrumentOut)
def get_instrument() -> InstrumentOut:
    return InstrumentOut(
        open=study_enabled(),
        consent_version=instrument.CONSENT_VERSION,
        pair_consent_version=instrument.PAIR_CONSENT_VERSION,
        rater_fields=list(instrument.RATER_FIELDS),
        card_fields=list(instrument.CARD_FIELDS),
        study_attributes=list(instrument.STUDY_ATTRIBUTES),
        gameable_fields=list(instrument.GAMEABLE_FIELDS),
        outcome_items=dict(instrument.OUTCOME_ITEMS),
    )


@router.post("/lab/raters", response_model=TokenOut, status_code=201, dependencies=[Depends(limit_study_creation)])
def create_rater(body: CreateRaterIn | None = None, db: Session = Depends(get_db)) -> TokenOut:
    _, token = _errors(lambda: LabService(db).create_rater(body.cohort if body else "main"))
    return TokenOut(token=token)


@router.post("/lab/consent", response_model=ProgressOut)
def consent(body: ConsentIn, x_study_token: str = Header(...), db: Session = Depends(get_db)) -> ProgressOut:
    svc = LabService(db)
    _errors(lambda: svc.consent(x_study_token, body.consent_version))
    return ProgressOut(**svc.progress(svc.rater(x_study_token)).__dict__)


@router.put("/lab/profile", response_model=ProgressOut)
def save_profile(body: RaterProfileIn, x_study_token: str = Header(...), db: Session = Depends(get_db)) -> ProgressOut:
    svc = LabService(db)
    _errors(lambda: svc.save_profile(x_study_token, body.answers, body.important_attributes, body.demographics))
    return ProgressOut(**svc.progress(svc.rater(x_study_token)).__dict__)


@router.get("/lab/next", response_model=NextOut)
def next_trial(x_study_token: str = Header(...), db: Session = Depends(get_db)) -> NextOut:
    trial, progress = _errors(lambda: LabService(db).next_trial(x_study_token))
    return NextOut(
        trial=(
            TrialOut(trial_id=trial.id, kind=trial.kind, cards=[CardOut(**c) for c in trial.cards])
            if trial is not None
            else None
        ),
        progress=ProgressOut(**progress.__dict__),
    )


@router.post("/lab/trials/{trial_id}/response", response_model=ProgressOut)
def respond(
    trial_id: uuid.UUID, body: ResponseIn, x_study_token: str = Header(...), db: Session = Depends(get_db)
) -> ProgressOut:
    progress = _errors(lambda: LabService(db).respond(x_study_token, trial_id, **body.model_dump()))
    return ProgressOut(**progress.__dict__)


@router.delete("/lab/me", status_code=204, response_class=Response)
def withdraw(x_study_token: str = Header(...), db: Session = Depends(get_db)) -> Response:
    _errors(lambda: LabService(db).withdraw(x_study_token))
    return Response(status_code=204)


@router.post("/pairs", response_model=PairCreatedOut, status_code=201, dependencies=[Depends(limit_study_creation)])
def create_pair(db: Session = Depends(get_db)) -> PairCreatedOut:
    _, token, invite = _errors(lambda: PairService(db).create_pair())
    return PairCreatedOut(token=token, invite_token=invite)


@router.post("/pairs/join", response_model=TokenOut, status_code=201)
def join_pair(body: JoinIn, db: Session = Depends(get_db)) -> TokenOut:
    return TokenOut(token=_errors(lambda: PairService(db).join(body.invite_token)))


@router.put("/pairs/me", response_model=PairStatusOut)
def submit_pair(body: PairSubmitIn, x_study_token: str = Header(...), db: Session = Depends(get_db)) -> PairStatusOut:
    svc = PairService(db)
    _errors(
        lambda: svc.submit(
            x_study_token,
            consent_version=body.consent_version,
            answers=body.answers,
            important=body.important_attributes,
            roommate_ratings=body.roommate_ratings,
            outcomes=body.outcomes,
            months_together=body.months_together,
            still_together=body.still_together,
        )
    )
    return PairStatusOut(**svc.status(x_study_token))


@router.get("/pairs/me", response_model=PairStatusOut)
def pair_status(x_study_token: str = Header(...), db: Session = Depends(get_db)) -> PairStatusOut:
    return PairStatusOut(**_errors(lambda: PairService(db).status(x_study_token)))


# --- admin ------------------------------------------------------------------------


@router.get("/admin/summary", response_model=StudySummaryOut)
def admin_summary(_m: User = Depends(require_moderator), db: Session = Depends(get_db)) -> StudySummaryOut:
    count = lambda stmt: db.scalar(stmt) or 0  # noqa: E731
    real = StudyRater.is_synthetic.is_(False)
    complete_pairs = (
        select(StudyPairMember.pair_id)
        .where(StudyPairMember.submitted_at.is_not(None))
        .group_by(StudyPairMember.pair_id)
        .having(func.count() == 2)
        .subquery()
    )
    return StudySummaryOut(
        open=study_enabled(),
        raters_started=count(select(func.count()).select_from(StudyRater).where(real)),
        raters_consented=count(select(func.count()).select_from(StudyRater).where(real, StudyRater.consented_at.is_not(None))),
        raters_completed=count(select(func.count()).select_from(StudyRater).where(real, StudyRater.completed_at.is_not(None))),
        responses=count(
            select(func.count())
            .select_from(StudyResponse)
            .join(StudyTrial, StudyTrial.id == StudyResponse.trial_id)
            .join(StudyRater, StudyRater.id == StudyTrial.rater_id)
            .where(real)
        ),
        pairs_created=count(select(func.count()).select_from(StudyPair).where(StudyPair.is_synthetic.is_(False))),
        pairs_complete=count(
            select(func.count())
            .select_from(complete_pairs)
            .join(StudyPair, StudyPair.id == complete_pairs.c.pair_id)
            .where(StudyPair.is_synthetic.is_(False))
        ),
        synthetic_raters=count(select(func.count()).select_from(StudyRater).where(StudyRater.is_synthetic.is_(True))),
    )


@router.get("/admin/export")
def admin_export(
    include_synthetic: bool = False, _m: User = Depends(require_moderator), db: Session = Depends(get_db)
) -> dict:
    """De-identified study data for the analysis pipeline: answers and
    choices only, keyed by random study IDs."""
    return {
        "raters": to_json(load_raters(db, include_synthetic=include_synthetic)),
        "pairs": to_json(load_pairs(db, include_synthetic=include_synthetic)),
    }

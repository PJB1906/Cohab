"""Cohab Lab and roommate-pair study flows (Cohab v2 plan W2/W3).

Participants are anonymous: a random token is returned once and only its
SHA-256 is stored. No product account, email, name or phone number is ever
collected or shown, and nothing here reads a product table.
"""

from __future__ import annotations

import hashlib
import os
import random
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cohab.models import StudyPair, StudyPairMember, StudyRater, StudyResponse, StudyTrial
from cohab.services.study.design import plan_trials
from cohab.services.study.instrument import (
    CONSENT_VERSION,
    GAMEABLE_FIELDS,
    OPTIONS,
    OUTCOME_ITEMS,
    PAIR_CONSENT_VERSION,
    validate_important,
    validate_rater_answers,
)


class StudyError(Exception):
    pass


class StudyClosed(StudyError):
    pass


class UnknownToken(StudyError):
    pass


class NotReady(StudyError):
    """A step was attempted before the one it depends on."""


class InvalidInput(StudyError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def study_enabled() -> bool:
    """Feature flag. On unless STUDY_ENABLED is set to a false value, so a
    production deploy can close the study without a code change."""
    return os.environ.get("STUDY_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _require_open() -> None:
    if not study_enabled():
        raise StudyClosed


# --- Cohab Lab ---------------------------------------------------------------


@dataclass(frozen=True)
class Progress:
    answered: int
    total: int
    consented: bool
    profile_done: bool
    completed: bool


class LabService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_rater(self, cohort: str = "main", *, is_synthetic: bool = False) -> tuple[StudyRater, str]:
        _require_open()
        token = _new_token()
        rater = StudyRater(token_hash=hash_token(token), cohort=cohort[:40] or "main", is_synthetic=is_synthetic)
        self.session.add(rater)
        self.session.commit()
        return rater, token

    def rater(self, token: str) -> StudyRater:
        rater = self.session.scalar(
            select(StudyRater)
            .where(StudyRater.token_hash == hash_token(token))
            .options(selectinload(StudyRater.trials).selectinload(StudyTrial.response))
        )
        if rater is None or rater.withdrawn_at is not None:
            raise UnknownToken
        return rater

    def consent(self, token: str, version: str) -> None:
        _require_open()
        if version != CONSENT_VERSION:
            raise InvalidInput([f"consent version must be {CONSENT_VERSION}"])
        rater = self.rater(token)
        rater.consent_version = version
        rater.consented_at = rater.consented_at or _now()
        self.session.commit()

    def save_profile(self, token: str, answers: dict, important: list[str], demographics: dict | None = None) -> None:
        _require_open()
        rater = self.rater(token)
        if rater.consented_at is None:
            raise NotReady("consent first")
        if rater.started_trials_at is not None:
            raise NotReady("profile is locked once trials start")
        problems = validate_rater_answers(answers) + validate_important(important)
        if problems:
            raise InvalidInput(problems)
        rater.questionnaire = dict(answers)
        rater.important_attributes = list(important)
        rater.demographics = {k: str(v)[:40] for k, v in (demographics or {}).items() if k in DEMOGRAPHIC_KEYS}
        self.session.commit()

    def _ensure_trials(self, rater: StudyRater) -> None:
        if rater.trials:
            return
        if rater.questionnaire is None:
            raise NotReady("complete your own answers first")
        rater.design_seed = rater.design_seed or random.SystemRandom().randrange(2**31)
        for t in plan_trials(rater.questionnaire, rater.design_seed):
            self.session.add(
                StudyTrial(
                    rater_id=rater.id,
                    position=t.position,
                    kind=t.kind,
                    cards=t.cards,
                    varied_attributes=t.varied_attributes,
                    repeat_of=t.repeat_of,
                    expected_card=t.expected_card,
                )
            )
        rater.started_trials_at = _now()
        self.session.commit()
        self.session.refresh(rater)

    def next_trial(self, token: str) -> tuple[StudyTrial | None, Progress]:
        _require_open()
        rater = self.rater(token)
        if rater.consented_at is None:
            raise NotReady("consent first")
        self._ensure_trials(rater)
        pending = [t for t in rater.trials if t.response is None]
        trial = pending[0] if pending else None
        if trial is not None and trial.presented_at is None:
            trial.presented_at = _now()
            self.session.commit()
        return trial, self.progress(rater)

    def progress(self, rater: StudyRater) -> Progress:
        answered = sum(1 for t in rater.trials if t.response is not None)
        return Progress(
            answered=answered,
            total=len(rater.trials),
            consented=rater.consented_at is not None,
            profile_done=rater.questionnaire is not None,
            completed=rater.completed_at is not None,
        )

    def respond(
        self,
        token: str,
        trial_id: uuid.UUID,
        *,
        choice: str | None = None,
        ranking: list[str] | None = None,
        confidence: int | None = None,
        would_message: str | None = None,
        reason_text: str | None = None,
        response_ms: int | None = None,
    ) -> Progress:
        _require_open()
        rater = self.rater(token)
        trial = next((t for t in rater.trials if t.id == trial_id), None)
        if trial is None:
            raise UnknownToken
        if trial.response is not None:
            raise NotReady("already answered")
        pending = [t for t in rater.trials if t.response is None]
        if pending and pending[0].id != trial.id:
            raise NotReady("answer trials in order")

        problems: list[str] = []
        card_ids = [c["id"] for c in trial.cards]
        if trial.kind == "rank":
            if ranking is None or sorted(ranking) != sorted(card_ids):
                problems.append("ranking must list every card exactly once")
            choice = None
        else:
            if choice not in ("left", "right", "none"):
                problems.append("choice must be left, right or none")
            if confidence is None or not 1 <= confidence <= 5:
                problems.append("confidence must be 1-5")
            if would_message not in ("left", "right", "both", "neither"):
                problems.append("would_message must be left, right, both or neither")
            ranking = None
        if reason_text is not None and len(reason_text) > 140:
            problems.append("reason is at most 140 characters")
        if problems:
            raise InvalidInput(problems)

        self.session.add(
            StudyResponse(
                trial_id=trial.id,
                choice=choice,
                ranking=ranking,
                confidence=confidence,
                would_message=would_message,
                reason_text=(reason_text or None),
                response_ms=response_ms if response_ms is None or 0 <= response_ms < 3_600_000 else None,
                answered_at=_now(),
            )
        )
        self.session.flush()
        self.session.refresh(rater)
        if all(t.response is not None for t in rater.trials):
            rater.completed_at = _now()
        self.session.commit()
        return self.progress(rater)

    def withdraw(self, token: str) -> None:
        """Withdrawal deletes the rater's data, not just flags it."""
        rater = self.rater(token)
        self.session.delete(rater)
        self.session.commit()


DEMOGRAPHIC_KEYS = ("age_band", "gender", "living", "programme_level")


# --- Roommate pairs -------------------------------------------------------------


class PairService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_pair(self, cohort: str = "main", *, is_synthetic: bool = False) -> tuple[StudyPair, str, str]:
        """Returns (pair, member_a_token, invite_token). The first person keeps
        their token; the invite token goes to their roommate."""
        _require_open()
        invite = _new_token()
        token_a = _new_token()
        pair = StudyPair(invite_token_hash=hash_token(invite), cohort=cohort[:40] or "main", is_synthetic=is_synthetic)
        pair.members.append(StudyPairMember(role="a", token_hash=hash_token(token_a)))
        self.session.add(pair)
        self.session.commit()
        return pair, token_a, invite

    def join(self, invite_token: str) -> str:
        _require_open()
        pair = self.session.scalar(
            select(StudyPair)
            .where(StudyPair.invite_token_hash == hash_token(invite_token))
            .options(selectinload(StudyPair.members))
        )
        if pair is None:
            raise UnknownToken
        if any(m.role == "b" for m in pair.members):
            raise NotReady("this invite has already been used")
        token_b = _new_token()
        pair.members.append(StudyPairMember(role="b", token_hash=hash_token(token_b)))
        self.session.commit()
        return token_b

    def member(self, token: str) -> StudyPairMember:
        m = self.session.scalar(select(StudyPairMember).where(StudyPairMember.token_hash == hash_token(token)))
        if m is None:
            raise UnknownToken
        return m

    def submit(
        self,
        token: str,
        *,
        consent_version: str,
        answers: dict,
        important: list[str],
        roommate_ratings: dict,
        outcomes: dict,
        months_together: float,
        still_together: bool,
    ) -> StudyPairMember:
        _require_open()
        m = self.member(token)
        if m.submitted_at is not None:
            raise NotReady("already submitted")
        problems: list[str] = []
        if consent_version != PAIR_CONSENT_VERSION:
            problems.append(f"consent version must be {PAIR_CONSENT_VERSION}")
        problems += validate_rater_answers(answers) + validate_important(important)
        for f in GAMEABLE_FIELDS:
            if roommate_ratings.get(f) not in OPTIONS[f]:
                problems.append(f"roommate rating {f}: required")
        if set(roommate_ratings) - set(GAMEABLE_FIELDS):
            problems.append("unexpected roommate ratings")
        for item in OUTCOME_ITEMS:
            v = outcomes.get(item)
            if not isinstance(v, int) or not 1 <= v <= 5:
                problems.append(f"outcome {item}: 1-5 required")
        if set(outcomes) - set(OUTCOME_ITEMS):
            problems.append("unexpected outcome items")
        if not 0 < months_together <= 120:
            problems.append("months together must be between 0 and 120")
        if problems:
            raise InvalidInput(problems)
        now = _now()
        m.consent_version = consent_version
        m.consented_at = now
        m.questionnaire = dict(answers)
        m.important_attributes = list(important)
        m.roommate_ratings = dict(roommate_ratings)
        m.outcomes = dict(outcomes)
        m.months_together = float(months_together)
        m.still_together = bool(still_together)
        m.submitted_at = now
        self.session.commit()
        return m

    def status(self, token: str) -> dict:
        m = self.member(token)
        pair = self.session.get(StudyPair, m.pair_id)
        roles = {x.role: x for x in pair.members}
        return {
            "role": m.role,
            "submitted": m.submitted_at is not None,
            "roommate_joined": "b" in roles,
            "roommate_submitted": all(x.submitted_at is not None for x in roles.values()) and len(roles) == 2,
        }

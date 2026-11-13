"""Study data as plain records for analysis (no ORM objects leave here).

The analysis package (`cohab/analysis`) works on these records only, so the
same code runs on real data loaded from Postgres, on a JSON export, and on
simulated raters in tests and the power study.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cohab.models import StudyPair, StudyRater, StudyTrial


@dataclass
class TrialRecord:
    position: int
    kind: str
    cards: dict[str, dict[str, str]]  # card id -> answers
    order: list[str]  # card ids in display order (left first)
    varied: list[str] = field(default_factory=list)
    repeat_of: int | None = None
    expected: str | None = None
    chosen: str | None = None  # card id, or None for "no preference"
    ranking: list[str] | None = None
    confidence: int | None = None
    would_message: dict[str, bool] = field(default_factory=dict)
    response_ms: int | None = None


@dataclass
class RaterRecord:
    rater_id: str
    cohort: str
    is_synthetic: bool
    answers: dict[str, str]
    important: list[str]
    trials: list[TrialRecord]
    completed: bool


@dataclass
class PairMemberRecord:
    role: str
    answers: dict[str, str]
    important: list[str]
    roommate_ratings: dict[str, str]
    outcomes: dict[str, int]
    months_together: float
    still_together: bool


@dataclass
class PairRecord:
    pair_id: str
    is_synthetic: bool
    a: PairMemberRecord
    b: PairMemberRecord


def _would_message(value: str | None, order: list[str]) -> dict[str, bool]:
    if value is None or len(order) != 2:
        return {}
    left, right = order
    return {
        left: value in ("left", "both"),
        right: value in ("right", "both"),
    }


def trial_record(t: StudyTrial) -> TrialRecord:
    order = [c["id"] for c in t.cards]
    r = t.response
    chosen = None
    if r is not None and r.choice in ("left", "right"):
        chosen = order[0] if r.choice == "left" else order[1]
    return TrialRecord(
        position=t.position,
        kind=t.kind,
        cards={c["id"]: dict(c["answers"]) for c in t.cards},
        order=order,
        varied=list(t.varied_attributes or []),
        repeat_of=t.repeat_of,
        expected=t.expected_card,
        chosen=chosen,
        ranking=list(r.ranking) if r is not None and r.ranking else None,
        confidence=r.confidence if r is not None else None,
        would_message=_would_message(r.would_message if r is not None else None, order),
        response_ms=r.response_ms if r is not None else None,
    )


def load_raters(session: Session, *, include_synthetic: bool = False) -> list[RaterRecord]:
    stmt = select(StudyRater).options(selectinload(StudyRater.trials).selectinload(StudyTrial.response))
    if not include_synthetic:
        stmt = stmt.where(StudyRater.is_synthetic.is_(False))
    out = []
    for r in session.scalars(stmt).all():
        if r.questionnaire is None:
            continue
        trials = [trial_record(t) for t in r.trials if t.response is not None]
        out.append(
            RaterRecord(
                rater_id=str(r.id),
                cohort=r.cohort,
                is_synthetic=r.is_synthetic,
                answers=dict(r.questionnaire),
                important=list(r.important_attributes or []),
                trials=trials,
                completed=r.completed_at is not None,
            )
        )
    return out


def load_pairs(session: Session, *, include_synthetic: bool = False) -> list[PairRecord]:
    stmt = select(StudyPair).options(selectinload(StudyPair.members))
    if not include_synthetic:
        stmt = stmt.where(StudyPair.is_synthetic.is_(False))
    out = []
    for p in session.scalars(stmt).all():
        members = {m.role: m for m in p.members if m.submitted_at is not None}
        if set(members) != {"a", "b"}:
            continue
        recs = {
            role: PairMemberRecord(
                role=role,
                answers=dict(m.questionnaire),
                important=list(m.important_attributes or []),
                roommate_ratings=dict(m.roommate_ratings),
                outcomes={k: int(v) for k, v in m.outcomes.items()},
                months_together=float(m.months_together),
                still_together=bool(m.still_together),
            )
            for role, m in members.items()
        }
        out.append(PairRecord(str(p.id), p.is_synthetic, recs["a"], recs["b"]))
    return out


def to_json(records: list[Any]) -> list[dict]:
    return [asdict(r) for r in records]


def raters_from_json(data: list[dict]) -> list[RaterRecord]:
    return [
        RaterRecord(**{**d, "trials": [TrialRecord(**t) for t in d["trials"]]})
        for d in data
    ]


def pairs_from_json(data: list[dict]) -> list[PairRecord]:
    return [
        PairRecord(d["pair_id"], d["is_synthetic"], PairMemberRecord(**d["a"]), PairMemberRecord(**d["b"]))
        for d in data
    ]

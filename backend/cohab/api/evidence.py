"""/evidence/* — the evidence page and policy playground (Cohab v2 plan W6).

Moderator-only. The evidence page reads stored `analysis_run` rows; it never
computes anything at request time, so what it shows is exactly what
`make reproduce` produced, with its data-source tag.

The playground runs on a SYNTHETIC population generated in memory from the
seed distribution, never on real members: moving weights around and watching
someone's list reorder is a demo of the arithmetic, and real users' answers
have no business being in a demo.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.api.deps import get_active_weight_set, get_db, require_moderator
from cohab.models import AnalysisRun, User, WeightSet
from cohab.services.matching.population import synthetic_candidates
from cohab.services.matching.vectorised import (
    ALL_ATTRS,
    Population,
    attribute_matrices,
    eligible_mask,
    rank_for,
    score_population,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])

PLAYGROUND_N = 400
PLAYGROUND_TOP = 25


class AnalysisOut(BaseModel):
    kind: str
    data_source: str
    created_at: str
    provenance: dict
    payload: dict


@router.get("/summary", response_model=dict[str, AnalysisOut])
def summary(_m: User = Depends(require_moderator), db: Session = Depends(get_db)) -> dict[str, AnalysisOut]:
    rows = db.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at.desc())).all()
    latest: dict[str, AnalysisOut] = {}
    for r in rows:
        if r.kind not in latest:
            latest[r.kind] = AnalysisOut(
                kind=r.kind,
                data_source=r.data_source,
                created_at=r.created_at.isoformat(),
                provenance=r.provenance or {},
                payload=r.payload,
            )
    return latest


@lru_cache(maxsize=4)
def _world(seed: int):
    cands = synthetic_candidates(PLAYGROUND_N, seed=seed, all_verified=True)
    pop = Population.from_candidates(cands)
    am = attribute_matrices(pop)
    elig = eligible_mask(pop)
    return cands, pop, am, elig


def _default_subject(elig: np.ndarray) -> int:
    counts = elig.sum(axis=1)
    ok = np.flatnonzero(counts >= 15)
    return int(ok[0]) if ok.size else int(np.argmax(counts))


class PlaygroundCandidate(BaseModel):
    index: int
    label: str
    important: list[str]
    present: list[str]
    sim_to: dict[str, float]  # subject's view of the candidate (sim_a)
    sim_from: dict[str, float]  # candidate's view of the subject (sim_b)


class PlaygroundOut(BaseModel):
    seed: int
    subject: int
    subject_important: list[str]
    attributes: list[str]
    weights: dict[str, float]
    candidates: list[PlaygroundCandidate]
    server_top10: list[int]
    data_source: str = "synthetic"


@router.get("/playground", response_model=PlaygroundOut)
def playground(
    seed: int = Query(default=7, ge=0, le=10_000),
    subject: int | None = Query(default=None, ge=0, lt=PLAYGROUND_N),
    _m: User = Depends(require_moderator),
    weight_set: WeightSet = Depends(get_active_weight_set),
) -> PlaygroundOut:
    cands, pop, am, elig = _world(seed)
    i = subject if subject is not None else _default_subject(elig)
    weights = {k: float(v) for k, v in weight_set.weights.items()}
    sm = score_population(pop, weights, am)
    ranked = rank_for(i, sm, elig, pop.ids)
    shown = ranked[:PLAYGROUND_TOP]
    out = []
    for j in shown:
        present = [
            n for n in ALL_ATTRS if n in weights and (am.present[n] is None or (am.present[n][i] and am.present[n][j]))
        ]
        out.append(
            PlaygroundCandidate(
                index=j,
                label=f"Person {j:03d}",
                important=sorted(cands[j].important_attributes),
                present=present,
                sim_to={n: float(am.sim[n][i, j]) for n in present},
                sim_from={n: float(am.sim[n][j, i]) for n in present},
            )
        )
    return PlaygroundOut(
        seed=seed,
        subject=i,
        subject_important=sorted(cands[i].important_attributes),
        attributes=[n for n in ALL_ATTRS if n in weights],
        weights=weights,
        candidates=out,
        server_top10=shown[:10],
    )


class RankIn(BaseModel):
    seed: int = Field(default=7, ge=0, le=10_000)
    subject: int = Field(ge=0, lt=PLAYGROUND_N)
    weights: dict[str, float]


class RankOut(BaseModel):
    top10: list[int]
    scores: list[float]


@router.post("/playground/rank", response_model=RankOut)
def playground_rank(body: RankIn, _m: User = Depends(require_moderator)) -> RankOut:
    """Server-side ranking under arbitrary weights, so the page can check its
    own in-browser arithmetic against the real matcher."""
    if any(v < 0 for v in body.weights.values()) or sum(body.weights.values()) <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "weights must be non-negative with a positive sum")
    unknown = set(body.weights) - set(ALL_ATTRS)
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown attributes {sorted(unknown)}")
    total = sum(body.weights.values())
    weights = {k: v / total for k, v in body.weights.items()}
    cands, pop, am, elig = _world(body.seed)
    sm = score_population(pop, weights, am)
    top = rank_for(body.subject, sm, elig, pop.ids)[:10]
    return RankOut(top10=top, scores=[float(sm.combined[body.subject, j]) for j in top])

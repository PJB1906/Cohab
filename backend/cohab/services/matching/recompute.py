"""Periodic recompute job — build plan §4 Phase 8.

PRD §7.1's Stage B invalidation table lists "a new weight set is published →
rescore everything — expensive, run off-peak" as an event to handle. This
script is that handler, run manually
(`python -m cohab.services.matching.recompute`) rather than via a live
scheduler — the same "run it yourself" precedent report.py and tuning.py
already set, and consistent with CLAUDE.md's Redis/infra-deferral stance: no
scheduler dependency is introduced for a pilot that doesn't need one. It
doesn't move anything to Stage B — PRD §7.1's own migration trigger (p95
latency or pool size) hasn't been reached, so `GET /matches` still computes
on read; this only keeps `match_score` caught up between calls.

It also materialises `match_score` broadly enough for the analytics
dashboard (`services/analytics.py`) to query directly, rather than only
whatever pairs individual `GET /matches` calls happened to touch.

Drives the same `MatchesService.get_matches()` the live API uses, once per
verified/active subject, with a limit large enough to cover a pilot-scale
eligible pool in one pass — so it inherits `_upsert`'s immutability guard for
free: a still-"suggested" row is refreshed under the currently active
weight_set, a viewed-or-later row is left exactly as the user last saw it
(docs/DECISIONS.md D-4.6).

Fits its own `TfidfSimilarity` over the whole pool's `lifestyle_notes`, the
same offline precedent as report.py/tuning.py — the live API deliberately
never does this (D-4.4: `NeutralTextSimilarity`, so nothing encodes text
inside a request), but an offline batch job is exactly the carve-out that
precedent already allows.

Requires the DB up, migrated and seeded:
    docker compose up -d db
    alembic upgrade head
    python -m cohab.seed
    python -m cohab.services.matching.recompute
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cohab.db import SessionLocal
from cohab.models import User, WeightSet
from cohab.services.matches import MatchesService
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.text import TfidfSimilarity

# Large enough to cover a pilot-scale eligible pool in one pass — the same
# "effectively unlimited" convention tests/api/test_matches.py's LARGE_LIMIT
# already uses.
RECOMPUTE_LIMIT = 3000


class NoActiveWeightSet(Exception):
    pass


def _load_candidates(session: Session) -> list[Candidate]:
    stmt = select(User).options(
        selectinload(User.preference_profile),
        selectinload(User.attribute_weights),
        selectinload(User.listing),
    )
    candidates: list[Candidate] = []
    for user in session.scalars(stmt).all():
        if user.preference_profile is None:
            continue
        candidates.append(Candidate.from_orm(user, user.preference_profile, user.listing))
    return candidates


def recompute(session: Session) -> str:
    """Runs against a caller-supplied session so it can be driven both by the
    CLI entry point below (a real `SessionLocal()`) and directly by tests
    (the SAVEPOINT-backed `db_session` fixture) without duplicating the
    logic. Returns a one-line summary rather than printing, so a caller can
    decide what to do with it."""
    weight_set = session.scalar(select(WeightSet).where(WeightSet.is_active.is_(True)))
    if weight_set is None:
        raise NoActiveWeightSet

    pool = _load_candidates(session)
    text_similarity = TfidfSimilarity().fit([c.lifestyle_notes for c in pool])
    service = MatchesService(session, weight_set, text_similarity)

    subjects = [c for c in pool if c.verification_status == "verified" and c.account_status == "active"]
    touched = 0
    for candidate in subjects:
        user = session.get(User, candidate.user_id)
        entries = service.get_matches(user, limit=RECOMPUTE_LIMIT)
        touched += len(entries)

    return (
        f"recompute complete: {len(subjects)} subjects scored against "
        f"weight_set v{weight_set.version}, {touched} match_score rows touched"
    )


def main() -> None:
    session = SessionLocal()
    try:
        print(recompute(session))
    except NoActiveWeightSet:
        print("no active weight_set — nothing to recompute")
    finally:
        session.close()


if __name__ == "__main__":
    main()

"""The one place `match_score.state` changes (Cohab v2 plan W1 / deck slide 23).

Every lifecycle transition goes through `transition()`, which appends a
`match_state_event` row in the same transaction as the state change. Callers
never assign `row.state` directly any more, so the event chain cannot drift
from the state column: if the state changed, there is an event for it.

`log_exposures()` records one `match_exposure` row per candidate returned to a
viewer, with its 1-based rank, so a later analysis can reconstruct exactly what
each person was shown, in what order, under which weight set.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from cohab.models import MatchExposure, MatchScore, MatchStateEvent

# Deterministic ranking: every shown item had probability 1 of being shown at
# its position under the logging policy.
DETERMINISTIC_PROPENSITY = 1.0


def transition(
    session: Session,
    row: MatchScore,
    to_state: str,
    *,
    actor_id: uuid.UUID | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Set `row.state` and append the matching event. A no-op transition
    (same state) records nothing."""
    from_state = row.state
    if from_state == to_state:
        return
    row.state = to_state
    session.flush()  # row.id must exist for a freshly created MatchScore
    session.add(
        MatchStateEvent(
            match_score_id=row.id,
            from_state=from_state,
            to_state=to_state,
            actor_id=actor_id,
            event_metadata=metadata or {},
        )
    )


def record_creation(session: Session, match_ids: Iterable[uuid.UUID]) -> None:
    """The `null -> suggested` event for rows just inserted by a bulk upsert."""
    ids = list(match_ids)
    if not ids:
        return
    now = datetime.now(timezone.utc)
    session.execute(
        insert(MatchStateEvent),
        [
            {
                "id": uuid.uuid4(),
                "match_score_id": mid,
                "at": now,
                "from_state": None,
                "to_state": "suggested",
                "actor_id": None,
                "event_metadata": {},
            }
            for mid in ids
        ],
    )


@dataclass(frozen=True)
class Exposure:
    match_score_id: uuid.UUID
    rank_position: int
    combined_score: float


def policy_version(source: str, version: int) -> str:
    return f"{source}-v{version}"


def log_exposures(
    session: Session,
    *,
    viewer_id: uuid.UUID,
    exposures: list[Exposure],
    surface: str,
    weight_set_id: uuid.UUID,
    policy: str,
) -> None:
    if not exposures:
        return
    now = datetime.now(timezone.utc)
    session.execute(
        insert(MatchExposure),
        [
            {
                "id": uuid.uuid4(),
                "match_score_id": e.match_score_id,
                "viewer_id": viewer_id,
                "shown_at": now,
                "rank_position": e.rank_position,
                "surface": surface,
                "policy_version": policy,
                "propensity": DETERMINISTIC_PROPENSITY,
                "weight_set_id": weight_set_id,
                "combined_score": e.combined_score,
            }
            for e in exposures
        ],
    )
    session.execute(
        update(MatchScore)
        .where(MatchScore.id.in_([e.match_score_id for e in exposures]))
        .where(MatchScore.first_shown_at.is_(None))
        .values(first_shown_at=now)
    )

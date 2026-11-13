"""Match funnel from `match_state_event` (Cohab v2 plan W1, deck slide 23).

"Reached stage X" means the match's event chain contains X or any later
forward stage: a match that went straight to `mutual` passed through
`interested` even though only one row was written for the double click.
Durations are medians of (first time stage X was reached) minus (creation),
over matches whose chain has both events, in hours.

Aggregate only: no per-user rows ever leave this module (PRD §3.2).
"""

from __future__ import annotations

import statistics
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import MatchScore, MatchStateEvent
from cohab.models.matching import REJECTION_REASONS

FORWARD_STAGES = (
    "suggested",
    "viewed",
    "interested",
    "mutual",
    "chatting",
    "contact_shared",
    "cohabiting",
)
_RANK = {s: i for i, s in enumerate(FORWARD_STAGES)}


@dataclass(frozen=True)
class FunnelStage:
    stage: str
    reached: int
    conversion_from_previous: float | None
    median_hours_from_suggested: float | None


@dataclass(frozen=True)
class Funnel:
    total_matches: int
    stages: list[FunnelStage]
    rejected: int
    rejection_reasons: dict[str, int]


def funnel(session: Session) -> Funnel:
    events = session.execute(
        select(MatchStateEvent.match_score_id, MatchStateEvent.to_state, MatchStateEvent.at).order_by(
            MatchStateEvent.at
        )
    ).all()

    furthest: dict[uuid.UUID, int] = {}
    first_at: dict[uuid.UUID, dict[str, datetime]] = defaultdict(dict)
    for match_id, to_state, at in events:
        if to_state in _RANK:
            furthest[match_id] = max(furthest.get(match_id, -1), _RANK[to_state])
            first_at[match_id].setdefault(to_state, at)

    stages: list[FunnelStage] = []
    previous: int | None = None
    for stage in FORWARD_STAGES:
        reached = sum(1 for r in furthest.values() if r >= _RANK[stage])
        durations = [
            (stamps[stage] - stamps["suggested"]).total_seconds() / 3600
            for stamps in first_at.values()
            if stage in stamps and "suggested" in stamps
        ]
        stages.append(
            FunnelStage(
                stage=stage,
                reached=reached,
                conversion_from_previous=(reached / previous) if previous else None,
                median_hours_from_suggested=(
                    round(statistics.median(durations), 2) if durations and stage != "suggested" else None
                ),
            )
        )
        previous = reached

    reasons = Counter(
        r for (r,) in session.execute(
            select(MatchScore.rejection_reason).where(MatchScore.state == "rejected")
        ).all()
    )
    rejection_reasons = {reason: reasons.get(reason, 0) for reason in REJECTION_REASONS}
    rejection_reasons["unspecified"] = reasons.get(None, 0)

    return Funnel(
        total_matches=len(furthest),
        stages=stages,
        rejected=sum(reasons.values()),
        rejection_reasons=rejection_reasons,
    )

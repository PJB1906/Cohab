"""`weight_set` publish mechanism — build plan §4 Phase 8; CLAUDE.md's
invariant that weight sets are "immutable once published... refinement
creates a new version."

`publish()` is the *only* function anywhere in the codebase that sets a
`WeightSet.weights` column — nothing ever updates it on an existing row, so
immutability is structural, not a convention callers have to remember.

PRD §6.5 places tier-2 *fitted* weights (regularised logistic regression over
real outcomes) at v2/post-pilot, needing "a few hundred labelled outcomes" —
this phase is the first to collect any outcome data at all, so there is
nothing yet to fit against. This module only builds the versioning machinery;
no fitting logic lives here.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from cohab.models import WeightSet
from cohab.models.matching import WEIGHT_SET_SOURCES

WEIGHT_SUM_TOLERANCE = 0.01


class InvalidWeights(Exception):
    pass


def publish(session: Session, weights: dict[str, float], source: str) -> WeightSet:
    """Deactivate whatever is currently active and insert a new, immutable,
    active version. Never mutates an existing row."""
    if source not in WEIGHT_SET_SOURCES:
        raise InvalidWeights(f"unknown source {source!r}")

    total = sum(weights.values())
    if abs(total - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise InvalidWeights(f"weights must sum to ~1.0, got {total}")

    next_version = (session.scalar(select(func.max(WeightSet.version))) or 0) + 1
    # Plural on purpose: sweeps every active row, not just the one
    # `get_active_weight_set` would have returned, so a prior inconsistency
    # can't leave two rows simultaneously active after this call.
    session.execute(update(WeightSet).where(WeightSet.is_active.is_(True)).values(is_active=False))

    new_set = WeightSet(
        version=next_version,
        source=source,
        weights=weights,
        published_at=datetime.now(timezone.utc),
        is_active=True,
    )
    session.add(new_set)
    session.flush()
    return new_set

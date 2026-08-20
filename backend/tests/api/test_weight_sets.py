"""`weight_sets.publish` — build plan §4 Phase 8. DB-backed (queries/inserts
`WeightSet` rows directly), so this lives under tests/api/ alongside the
other DB-touching suites rather than tests/matching/'s framework-free tests."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cohab.models import WeightSet
from cohab.services.matching.weight_sets import InvalidWeights, publish

VALID_WEIGHTS = {"cleanliness_level": 0.5, "sleep_schedule": 0.5}


def test_publish_deactivates_previous_and_activates_new(db_session: Session, weight_set: WeightSet) -> None:
    assert weight_set.is_active is True
    # The shared dev DB this suite runs against (tests/api/conftest.py's own
    # convention) may already carry other WeightSet rows from a prior
    # `python -m cohab.seed` run, so the next version is "one past whatever
    # the max already is", not necessarily one past this fixture's own row.
    max_version_before = db_session.scalar(select(func.max(WeightSet.version)))

    new_set = publish(db_session, VALID_WEIGHTS, source="expert")

    db_session.refresh(weight_set)
    assert weight_set.is_active is False
    assert new_set.is_active is True
    assert new_set.version == max_version_before + 1
    assert new_set.weights == VALID_WEIGHTS
    assert new_set.published_at is not None


def test_publish_never_mutates_an_existing_rows_weights(db_session: Session, weight_set: WeightSet) -> None:
    original_weights = dict(weight_set.weights)
    publish(db_session, VALID_WEIGHTS, source="expert")

    db_session.refresh(weight_set)
    assert weight_set.weights == original_weights  # untouched


def test_publish_rejects_weights_not_summing_to_one(db_session: Session, weight_set: WeightSet) -> None:
    with pytest.raises(InvalidWeights):
        publish(db_session, {"cleanliness_level": 0.9}, source="expert")


def test_publish_rejects_unknown_source(db_session: Session, weight_set: WeightSet) -> None:
    with pytest.raises(InvalidWeights):
        publish(db_session, VALID_WEIGHTS, source="astrology")


def test_publish_only_one_row_active_at_a_time(db_session: Session, weight_set: WeightSet) -> None:
    publish(db_session, VALID_WEIGHTS, source="expert")
    active = db_session.scalars(select(WeightSet).where(WeightSet.is_active.is_(True))).all()
    assert len(active) == 1

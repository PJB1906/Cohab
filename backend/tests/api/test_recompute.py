"""`recompute.py` — build plan §4 Phase 8. Deliberately narrow: the
"happy path" walks every verified/active user in this suite's shared,
~1,500-row dev-seeded pool (see tests/api/test_matches.py
::test_publishing_a_new_weight_set_leaves_an_already_viewed_match_untouched's
own docstring for why that's not run here) and was instead verified once,
manually, against the live dev DB (docs/DECISIONS.md D-8.1: 1,392 subjects,
94,404 match_score rows touched, a previously-viewed row's score confirmed
byte-for-byte unchanged). This covers the one behaviour cheap enough to test
without that cost: the no-active-weight_set guard."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session
import pytest

from cohab.models import WeightSet
from cohab.services.matching.recompute import NoActiveWeightSet, recompute


def test_recompute_raises_when_no_active_weight_set(db_session: Session, weight_set: WeightSet) -> None:
    db_session.execute(update(WeightSet).where(WeightSet.is_active.is_(True)).values(is_active=False))
    db_session.commit()

    with pytest.raises(NoActiveWeightSet):
        recompute(db_session)

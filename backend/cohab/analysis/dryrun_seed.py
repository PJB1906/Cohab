"""Write a SYNTHETIC dry-run study into the real study tables.

Purpose: exercise the whole path (tables -> export -> analysis -> evidence
page) before a single real rater exists, the way a lab runs a protocol on
itself before recruiting. Every row is `is_synthetic=True`, cohort "dryrun";
analyses exclude them unless run with `--source dryrun`, and the evidence
page labels anything computed from them as a dry run.

    python -m cohab.analysis.dryrun_seed            # 40 raters, 30 pairs
    python -m cohab.services.study.delete_data --synthetic-only   # remove
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
from sqlalchemy.orm import Session

from cohab.analysis.simulate_raters import GroundTruth, simulate_pairs, simulate_raters
from cohab.analysis.weights import EXPERT, EXPERT_STUDY
from cohab.db import SessionLocal
from cohab.models import StudyPair, StudyPairMember, StudyRater, StudyResponse, StudyTrial
from cohab.services.study.instrument import CONSENT_VERSION, PAIR_CONSENT_VERSION
from cohab.services.study.service import hash_token

DRYRUN_SEED = 20261111


def dryrun_truth() -> GroundTruth:
    """Planted preferences for the dry run: a plausible vector that differs
    from the expert one, so the pipeline has something to find."""
    rng = np.random.default_rng(DRYRUN_SEED)
    return GroundTruth(weights=rng.dirichlet(EXPERT_STUDY * 12), scale=14, inattentive_share=0.08, label="dryrun")


def write_dryrun(session: Session, n_raters: int = 40, n_pairs: int = 30) -> dict:
    t0 = datetime.now(timezone.utc) - timedelta(days=3)
    raters = simulate_raters(n_raters, dryrun_truth(), seed=DRYRUN_SEED)
    for k, r in enumerate(raters):
        row = StudyRater(
            token_hash=hash_token(f"dryrun-{uuid.uuid4()}"),
            cohort="dryrun",
            consent_version=CONSENT_VERSION,
            consented_at=t0,
            questionnaire=r.answers,
            important_attributes=r.important,
            design_seed=k,
            started_trials_at=t0,
            completed_at=t0 + timedelta(minutes=20),
            is_synthetic=True,
        )
        session.add(row)
        session.flush()
        for t in r.trials:
            cards = [{"id": cid, "answers": t.cards[cid]} for cid in t.order]
            trial = StudyTrial(
                rater_id=row.id,
                position=t.position,
                kind=t.kind,
                cards=cards,
                varied_attributes=t.varied,
                repeat_of=t.repeat_of,
                expected_card=t.expected,
                presented_at=t0,
            )
            session.add(trial)
            session.flush()
            if t.kind == "rank":
                session.add(StudyResponse(trial_id=trial.id, ranking=t.ranking, answered_at=t0))
            else:
                choice = "none" if t.chosen is None else ("left" if t.chosen == t.order[0] else "right")
                wm = t.would_message
                left, right = wm.get(t.order[0]), wm.get(t.order[1])
                would = "both" if left and right else "left" if left else "right" if right else "neither"
                session.add(
                    StudyResponse(
                        trial_id=trial.id,
                        choice=choice,
                        confidence=t.confidence,
                        would_message=would,
                        response_ms=t.response_ms,
                        answered_at=t0,
                    )
                )
    pairs = simulate_pairs(n_pairs, EXPERT, signal=5.0, self_inflation=0.3, seed=DRYRUN_SEED)
    for p in pairs:
        row = StudyPair(invite_token_hash=hash_token(f"dryrun-{uuid.uuid4()}"), cohort="dryrun", is_synthetic=True)
        for m in (p.a, p.b):
            row.members.append(
                StudyPairMember(
                    role=m.role,
                    token_hash=hash_token(f"dryrun-{uuid.uuid4()}"),
                    consent_version=PAIR_CONSENT_VERSION,
                    consented_at=t0,
                    questionnaire=m.answers,
                    important_attributes=m.important,
                    roommate_ratings=m.roommate_ratings,
                    outcomes=m.outcomes,
                    months_together=m.months_together,
                    still_together=m.still_together,
                    submitted_at=t0,
                )
            )
        session.add(row)
    session.commit()
    return {"raters": n_raters, "pairs": n_pairs}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raters", type=int, default=40)
    ap.add_argument("--pairs", type=int, default=30)
    args = ap.parse_args()
    with SessionLocal() as session:
        print(f"wrote SYNTHETIC dry run: {write_dryrun(session, args.raters, args.pairs)}")


if __name__ == "__main__":
    main()

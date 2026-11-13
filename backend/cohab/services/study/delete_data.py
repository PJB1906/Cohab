"""Delete study data (Cohab v2 plan W2: "the study deletes cleanly").

    python -m cohab.services.study.delete_data --synthetic-only   # dry-run rows only
    python -m cohab.services.study.delete_data --all --yes         # everything

Removes `study_*` rows only (cascades handle trials, responses and pair
members). Product tables are never touched. `--all` requires `--yes`,
because real participants' data cannot be recovered afterwards.
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, func, select, true
from sqlalchemy.orm import Session

from cohab.db import SessionLocal
from cohab.models import StudyPair, StudyRater


def delete_study_data(session: Session, *, synthetic_only: bool) -> dict:
    rater_filter = StudyRater.is_synthetic.is_(True) if synthetic_only else true()
    pair_filter = StudyPair.is_synthetic.is_(True) if synthetic_only else true()
    counts = {
        "raters": session.scalar(select(func.count()).select_from(StudyRater).where(rater_filter)) or 0,
        "pairs": session.scalar(select(func.count()).select_from(StudyPair).where(pair_filter)) or 0,
    }
    session.execute(delete(StudyRater).where(rater_filter))
    session.execute(delete(StudyPair).where(pair_filter))
    session.commit()
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description="Delete Cohab study data")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--synthetic-only", action="store_true")
    group.add_argument("--all", action="store_true")
    ap.add_argument("--yes", action="store_true", help="confirm deleting real participants' data")
    args = ap.parse_args()
    if args.all and not args.yes:
        ap.error("--all deletes real participants' data permanently; add --yes to confirm")
    with SessionLocal() as session:
        print(f"deleted: {delete_study_data(session, synthetic_only=args.synthetic_only)}")


if __name__ == "__main__":
    main()

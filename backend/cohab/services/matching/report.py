"""Read the matcher's output over the crude seed — the Phase 2 checkpoint.

This is the checkpoint the whole build order exists to reach (COHAB_BUILD_PLAN.md
§4): run the matcher over real-ish volume and *read the top-10 for a few profiles
by hand*, looking for the design errors unit tests cannot catch. It also prints a
light Stage-1 filter-yield smell test (build plan §3). Proper tuning is Phase 3
(spec §11), not here.

Requires the DB up, migrated and seeded:
    docker compose up -d db
    alembic upgrade head
    python -m cohab.seed
    python -m cohab.services.matching.report
"""

from __future__ import annotations

import statistics
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from cohab.db import SessionLocal
from cohab.models import User, WeightSet
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher
from cohab.services.matching.text import TfidfSimilarity

SAMPLE_SUBJECTS = 3   # profiles to read the top-10 for by hand
TOP_K = 10
YIELD_SAMPLE = 40     # subjects to estimate the median eligible pool over


def _load_candidates(session) -> list[Candidate]:
    stmt = select(User).options(
        selectinload(User.preference_profile),
        selectinload(User.attribute_weights),
        selectinload(User.listing),
    )
    candidates: list[Candidate] = []
    for user in session.scalars(stmt).all():
        if user.preference_profile is None:
            continue
        candidates.append(
            Candidate.from_orm(user, user.preference_profile, user.listing)
        )
    return candidates


def _is_valid_subject(c: Candidate) -> bool:
    return c.verification_status == "verified" and c.account_status == "active"


def _print_yield(ranker: MatchRanker, subjects: list[Candidate], pool: list[Candidate]) -> None:
    counts: list[int] = []
    reason_tally: dict[str, int] = {}
    for subject in subjects:
        eligible, excluded = ranker.filter_with_reasons(subject, pool)
        counts.append(len(eligible))
        for ex in excluded:
            reason_tally[ex.reason] = reason_tally.get(ex.reason, 0) + 1

    median = statistics.median(counts)
    print("=" * 72)
    print(f"STAGE 1 FILTER YIELD  (over {len(subjects)} sample subjects, pool={len(pool)})")
    print(f"  eligible pool: min={min(counts)}  median={median:g}  max={max(counts)}")
    print("  exclusion reasons (most common first):")
    for reason, n in sorted(reason_tally.items(), key=lambda kv: kv[1], reverse=True):
        print(f"    {reason:<24} {n}")
    print()


def _print_top_matches(ranker: MatchRanker, subject: Candidate, pool: list[Candidate]) -> None:
    ranked = ranker.rank(subject, pool)
    print("=" * 72)
    print(f"SUBJECT  {subject.name}  ({subject.gender}, {subject.seeker_type}, "
          f"budget ₹{subject.budget_min}-{subject.budget_max})")
    print(f"  {len(ranked)} eligible candidates; top {min(TOP_K, len(ranked))}:")
    for i, m in enumerate(ranked[:TOP_K], start=1):
        r = m.result
        print(f"  {i:>2}. {m.candidate.name:<22} "
              f"combined={r.combined_score:.3f}  "
              f"S(a→b)={r.score_ab:.3f}  S(b→a)={r.score_ba:.3f}")
        for card in m.explanation.agreements:
            print(f"        + {card.text}")
        if m.explanation.divergence:
            print(f"        - {m.explanation.divergence.text}")
    print()


def main() -> None:
    # The templates and ₹ symbol are UTF-8; Windows consoles default to cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    session = SessionLocal()
    try:
        weight_set = session.scalars(
            select(WeightSet).where(WeightSet.is_active.is_(True))
        ).first()
        if weight_set is None:
            raise SystemExit("No active weight_set found — run `python -m cohab.seed` first.")

        pool = _load_candidates(session)
        if not pool:
            raise SystemExit("No candidates found — seed the database first.")

        # Fit TF-IDF over the pool's lifestyle notes once (spec §7: fit offline,
        # never in the request path).
        text_sim = TfidfSimilarity().fit([c.lifestyle_notes for c in pool])
        matcher = CompatibilityMatcher(weight_set.weights, weight_set.id, text_similarity=text_sim)
        ranker = MatchRanker(matcher)

        subjects = [c for c in sorted(pool, key=lambda c: c.user_id) if _is_valid_subject(c)]

        print(f"\nWeight set v{weight_set.version} ({weight_set.source}), {len(pool)} profiles.\n")
        _print_yield(ranker, subjects[:YIELD_SAMPLE], pool)
        for subject in subjects[:SAMPLE_SUBJECTS]:
            _print_top_matches(ranker, subject, pool)
    finally:
        session.close()


if __name__ == "__main__":
    main()

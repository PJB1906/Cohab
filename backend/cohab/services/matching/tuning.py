"""Phase 3 tuning report — COHAB_MATCHING_SPEC.md §11's tuning checklist.

`report.py` was the Phase 2 checkpoint (eyeball a few top-10s over the crude
seed); its own docstring defers "proper tuning" to here. This runs against
the Phase 3 realistic seed (`cohab/seed.py`) and prints, in spec §11's order:

1. Filter yield        4. Directional spread
2. Exclusion reasons    5. Top-10 eyeball (more subjects than report.py)
3. Score distribution   6. Ablation (the four attributes spec §11 names)

plus a 7th section the PRD calls a reportable result in its own right: a
TF-IDF vs `EmbeddingSimilarity` comparison over the same pool (PRD §7).

Sections 1-6 score with `TfidfSimilarity` (fast, no model download) so the
bulk of the report runs quickly; section 7 is the only place
`EmbeddingSimilarity` runs, over a bounded sample of pairs, since it makes a
real transformer forward pass per pair. If the model can't be loaded (not
installed, no network), section 7 reports that and the rest of the report is
unaffected.

No unit tests here, same precedent as report.py: this aggregates already-
tested primitives (`EligibilityFilter`, `CompatibilityMatcher`, `MatchRanker`)
rather than introducing new matching logic.

Requires the DB up, migrated and seeded with the Phase 3 generator:
    docker compose up -d db
    alembic upgrade head
    python -m cohab.seed
    python -m cohab.services.matching.tuning
"""

from __future__ import annotations

import random
import statistics
import sys

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from cohab.db import SessionLocal
from cohab.models import User, WeightSet
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher
from cohab.services.matching.text import EmbeddingSimilarity, TfidfSimilarity

# Sample sizes are nested slices of the same sorted subject list, largest
# first, so every section's subjects are a subset of the section above it.
YIELD_SAMPLE = 60
SCORE_SAMPLE = 40
EYEBALL_SAMPLE = 20   # spec §11 item 5's own number
ABLATION_SAMPLE = 15  # each subject costs 1 baseline + 4 ablated rank() calls
TOP_K = 10

# spec §11 item 6 names these four by name as the ones to scrutinise.
ABLATION_ATTRIBUTES = ["sharing_norm", "home_orientation", "sociability", "cost_split_preference"]

TEXT_COMPARISON_PAIRS = 150
RNG_SEED = 7  # local to this report; independent of seed.py's SEED

# spec §11 item 1 / PRD §2's two stated targets for the median eligible pool.
YIELD_TARGET_SPEC = 10
YIELD_TARGET_PRD = 15
# spec §11 item 3's failure signature for the score distribution.
BUNCHED_LOW, BUNCHED_HIGH = 0.70, 0.80
HEALTHY_LOW, HEALTHY_HIGH = 0.35, 0.90


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
        candidates.append(Candidate.from_orm(user, user.preference_profile, user.listing))
    return candidates


def _is_valid_subject(c: Candidate) -> bool:
    return c.verification_status == "verified" and c.account_status == "active"


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mean_x, mean_y = statistics.mean(xs), statistics.mean(ys)
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    denom = (var_x * var_y) ** 0.5
    return cov / denom if denom else float("nan")


# --- 1 & 2: filter yield, exclusion reasons ---------------------------------

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
    print(f"1-2. FILTER YIELD & EXCLUSION REASONS  (over {len(subjects)} subjects, pool={len(pool)})")
    print(f"  eligible pool: min={min(counts)}  median={median:g}  max={max(counts)}")
    flag = ""
    if median < YIELD_TARGET_SPEC:
        flag = f"  [BELOW spec §11's target of {YIELD_TARGET_SPEC}]"
    elif median < YIELD_TARGET_PRD:
        flag = f"  [meets spec §11's {YIELD_TARGET_SPEC} but below PRD §2's pilot target of {YIELD_TARGET_PRD}]"
    else:
        flag = f"  [meets both the spec §11 ({YIELD_TARGET_SPEC}) and PRD §2 ({YIELD_TARGET_PRD}) targets]"
    print(f" {flag}")
    print("  exclusion reasons (most common first):")
    for reason, n in sorted(reason_tally.items(), key=lambda kv: kv[1], reverse=True):
        print(f"    {reason:<24} {n}")
    print()


# --- 3 & 4: score distribution, directional spread --------------------------

def _collect_scores(
    matcher: CompatibilityMatcher, ranker: MatchRanker, subjects: list[Candidate], pool: list[Candidate]
) -> tuple[list[float], list[float]]:
    scores: list[float] = []
    spreads: list[float] = []
    for subject in subjects:
        eligible, _ = ranker.filter_with_reasons(subject, pool)
        for candidate in eligible:
            result = matcher.score(subject, candidate)
            scores.append(result.combined_score)
            spreads.append(abs(result.score_ab - result.score_ba))
    return scores, spreads


def _print_score_distribution(scores: list[float]) -> None:
    print("=" * 72)
    print(f"3. SCORE DISTRIBUTION  (over {len(scores)} eligible pairs)")
    if not scores:
        print("  no eligible pairs in the sample.\n")
        return
    quantiles = statistics.quantiles(scores, n=4) if len(scores) >= 4 else [min(scores), statistics.median(scores), max(scores)]
    bunched = sum(1 for s in scores if BUNCHED_LOW <= s <= BUNCHED_HIGH) / len(scores)
    healthy = sum(1 for s in scores if HEALTHY_LOW <= s <= HEALTHY_HIGH) / len(scores)
    print(f"  min={min(scores):.3f}  p25={quantiles[0]:.3f}  median={statistics.median(scores):.3f}  "
          f"p75={quantiles[-1] if len(quantiles) > 1 else quantiles[0]:.3f}  max={max(scores):.3f}  mean={statistics.mean(scores):.3f}")
    print(f"  within spec §11's healthy range [{HEALTHY_LOW}, {HEALTHY_HIGH}]: {healthy:.0%}")
    flag = "  [WARNING: looks bunched — weights/matrices may not be discriminating]" if bunched > 0.5 else ""
    print(f"  bunched in [{BUNCHED_LOW}, {BUNCHED_HIGH}]: {bunched:.0%}{flag}")
    print()


def _print_directional_spread(spreads: list[float]) -> None:
    print("=" * 72)
    print(f"4. DIRECTIONAL SPREAD  |S(a→b) − S(b→a)|  (over {len(spreads)} eligible pairs)")
    if not spreads:
        print("  no eligible pairs in the sample.\n")
        return
    near_zero = sum(1 for s in spreads if s < 0.02) / len(spreads)
    print(f"  min={min(spreads):.3f}  median={statistics.median(spreads):.3f}  "
          f"max={max(spreads):.3f}  mean={statistics.mean(spreads):.3f}")
    flag = "  [WARNING: importance weighting looks inert]" if near_zero > 0.8 else ""
    print(f"  pairs with spread < 0.02: {near_zero:.0%}{flag}")
    print()


# --- 5: top-10 eyeball -------------------------------------------------------

def _print_top_matches(ranker: MatchRanker, subject: Candidate, pool: list[Candidate]) -> None:
    ranked = ranker.rank(subject, pool)
    print(f"SUBJECT  {subject.name}  ({subject.gender}, {subject.seeker_type}, "
          f"budget ₹{subject.budget_min}-{subject.budget_max})")
    print(f"  {len(ranked)} eligible candidates; top {min(TOP_K, len(ranked))}:")
    for i, m in enumerate(ranked[:TOP_K], start=1):
        r = m.result
        print(f"  {i:>2}. {m.candidate.name:<22} "
              f"combined={r.combined_score:.3f}  S(a→b)={r.score_ab:.3f}  S(b→a)={r.score_ba:.3f}")
        for card in m.explanation.agreements:
            print(f"        + {card.text}")
        if m.explanation.divergence:
            print(f"        - {m.explanation.divergence.text}")


def _print_eyeball(ranker: MatchRanker, subjects: list[Candidate], pool: list[Candidate]) -> None:
    print("=" * 72)
    print(f"5. TOP-10 EYEBALL  (spec §11 item 5: read {len(subjects)} of these by hand)")
    for subject in subjects:
        _print_top_matches(ranker, subject, pool)
        print()


# --- 6: ablation --------------------------------------------------------------

def _print_ablation(
    base_ranker: MatchRanker,
    weight_set: WeightSet,
    text_sim: TfidfSimilarity,
    subjects: list[Candidate],
    pool: list[Candidate],
) -> None:
    print("=" * 72)
    print(f"6. ABLATION  (over {len(subjects)} subjects; top-{TOP_K} overlap, baseline vs weight zeroed)")

    baseline_top10: dict = {}
    for subject in subjects:
        ranked = base_ranker.rank(subject, pool)
        baseline_top10[subject.user_id] = [m.candidate.user_id for m in ranked[:TOP_K]]

    for attr in ABLATION_ATTRIBUTES:
        ablated_weights = dict(weight_set.weights)
        ablated_weights[attr] = 0.0
        ablated_matcher = CompatibilityMatcher(ablated_weights, weight_set.id, text_similarity=text_sim)
        ablated_ranker = MatchRanker(ablated_matcher)

        overlaps: list[int] = []
        rank1_changed = 0
        for subject in subjects:
            base = baseline_top10[subject.user_id]
            ablated = [m.candidate.user_id for m in ablated_ranker.rank(subject, pool)[:TOP_K]]
            overlaps.append(len(set(base) & set(ablated)))
            if base and ablated and base[0] != ablated[0]:
                rank1_changed += 1

        avg_overlap = statistics.mean(overlaps) if overlaps else float("nan")
        flag = "  [never moves the ranking — a candidate to drop]" if avg_overlap >= TOP_K - 0.5 and rank1_changed == 0 else ""
        print(f"  {attr:<24} avg top-{TOP_K} overlap {avg_overlap:.1f}/{TOP_K}   "
              f"#1 changed in {rank1_changed}/{len(subjects)}{flag}")
    print()


# --- 7: TF-IDF vs embedding comparison ---------------------------------------

def _print_text_comparison(pool: list[Candidate]) -> None:
    print("=" * 72)
    print("7. TF-IDF vs EMBEDDING COMPARISON  (PRD §7: \"a reportable result\")")

    with_notes = [c for c in pool if c.lifestyle_notes]
    max_pairs = len(with_notes) * (len(with_notes) - 1) // 2
    if max_pairs < 2:
        print("  not enough profiles with lifestyle_notes to compare.\n")
        return

    try:
        embed = EmbeddingSimilarity()
        embed.similarity(with_notes[0].lifestyle_notes, with_notes[0].lifestyle_notes)  # force the model to load
    except Exception as exc:  # model not installed / no network — report and move on
        print(f"  embedding model unavailable ({type(exc).__name__}: {exc}) — skipping this section.\n")
        return

    rng = random.Random(RNG_SEED)
    target = min(TEXT_COMPARISON_PAIRS, max_pairs)
    seen: set[tuple] = set()
    pairs = []
    while len(pairs) < target:
        a, b = rng.sample(with_notes, 2)
        key = tuple(sorted((a.user_id, b.user_id)))
        if key in seen:
            continue
        seen.add(key)
        pairs.append((a, b))

    tfidf = TfidfSimilarity().fit([c.lifestyle_notes for c in pool])
    tfidf_scores = [tfidf.similarity(a.lifestyle_notes, b.lifestyle_notes) for a, b in pairs]
    embed_scores = [embed.similarity(a.lifestyle_notes, b.lifestyle_notes) for a, b in pairs]

    corr = _pearson(tfidf_scores, embed_scores)
    mean_abs_diff = statistics.mean(abs(t - e) for t, e in zip(tfidf_scores, embed_scores))
    print(f"  pairs compared: {len(pairs)}")
    print(f"  Pearson r(tfidf, embedding): {corr:.3f}")
    print(f"  mean |tfidf - embedding|: {mean_abs_diff:.3f}")

    biggest = sorted(zip(pairs, tfidf_scores, embed_scores), key=lambda t: abs(t[1] - t[2]), reverse=True)[:3]
    print("  largest disagreements:")
    for (a, b), t_score, e_score in biggest:
        print(f"    tfidf={t_score:.2f} embed={e_score:.2f}  \"{a.lifestyle_notes}\" / \"{b.lifestyle_notes}\"")
    print()


def main() -> None:
    # The templates and ₹ symbol are UTF-8; Windows consoles default to cp1252.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    session = SessionLocal()
    try:
        weight_set = session.scalars(select(WeightSet).where(WeightSet.is_active.is_(True))).first()
        if weight_set is None:
            raise SystemExit("No active weight_set found — run `python -m cohab.seed` first.")

        pool = _load_candidates(session)
        if not pool:
            raise SystemExit("No candidates found — seed the database first.")

        text_sim = TfidfSimilarity().fit([c.lifestyle_notes for c in pool])
        matcher = CompatibilityMatcher(weight_set.weights, weight_set.id, text_similarity=text_sim)
        ranker = MatchRanker(matcher)

        subjects = sorted((c for c in pool if _is_valid_subject(c)), key=lambda c: c.user_id)

        print(f"\nWeight set v{weight_set.version} ({weight_set.source}), {len(pool)} profiles.\n")

        _print_yield(ranker, subjects[:YIELD_SAMPLE], pool)

        score_subjects = subjects[:SCORE_SAMPLE]
        scores, spreads = _collect_scores(matcher, ranker, score_subjects, pool)
        _print_score_distribution(scores)
        _print_directional_spread(spreads)

        _print_eyeball(ranker, subjects[:EYEBALL_SAMPLE], pool)
        _print_ablation(ranker, weight_set, text_sim, subjects[:ABLATION_SAMPLE], pool)
        _print_text_comparison(pool)
    finally:
        session.close()


if __name__ == "__main__":
    main()

"""Phase 9 — the evaluation chapter. COHAB_BUILD_PLAN.md §4 Phase 9; PRD §15
"Evaluation — v1": ranking metrics, ablation studies, distributional
analysis, and Kaplan-Meier survival analysis for the 90-day cohabitation
metric.

`report.py` was the Phase 2 checkpoint; `tuning.py` was the Phase 3 tuning
pass, its own numbers already cited in docs/DECISIONS.md's D-3.2 and left
untouched here (D-9.6 — this is a new, independent script, some
duplication against `tuning.py` accepted, matching the duplication
`tuning.py` already carries against `report.py`). This is the final,
publishable pass: larger samples, two saved charts, and the precision@k/
NDCG@10 recovery experiment `tuning.py` never attempted.

Five sections:
    1. Filter yield              4. Precision@k / NDCG@10 (recovery experiment)
    2. Score distribution        5. Survival analysis (Kaplan-Meier)
    3. Ablation (all attributes)

Every synthetic-data figure here validates the *implementation*, never the
underlying compatibility theory — PRD §6.6's circularity trap. Section 4 and
section 5 both say so again in their own output, not just here, since that's
the caveat most likely to be quoted out of context.

Does not recompute the Phase 3 TF-IDF-vs-embedding comparison (D-3.3) — an
already-settled finding, cited rather than duplicated.

Requires the DB up, migrated and seeded:
    docker compose up -d db
    alembic upgrade head
    python -m cohab.seed
    python -m cohab.services.matching.evaluation

Writes docs/evaluation/score_distribution.png and
docs/evaluation/survival_curve.png alongside the stdout report. See
docs/COHAB_EVALUATION.md for the narrated writeup and docs/DECISIONS.md's
"Phase 9" section (D-9.1 through D-9.6) for the design decisions behind
each section.
"""

from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — this is a report script, never a GUI process
import matplotlib.pyplot as plt
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cohab.db import SessionLocal
from cohab.models import User, WeightSet
from cohab.services.matching.attributes import ATTRIBUTES
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.eligibility import passes_hard_constraints
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.ranking_metrics import ndcg_at_k, precision_at_k
from cohab.services.matching.recovery import build_graded_pool, perturb_candidate
from cohab.services.matching.scoring import CompatibilityMatcher
from cohab.services.matching.survival import (
    KMPoint,
    kaplan_meier,
    load_cohabitation_observations,
)
from cohab.services.matching.text import TfidfSimilarity

OUTPUT_DIR = Path(__file__).resolve().parents[4] / "docs" / "evaluation"

YIELD_SAMPLE = 60
SCORE_SAMPLE = 40
ABLATION_SAMPLE = 15   # matches tuning.py's own sample size, now over 20 attributes not 4
RECOVERY_SUBJECTS = 20
RECOVERY_CANDIDATE_POOL = RECOVERY_SUBJECTS * 3  # headroom for _select_recovery_subjects' skips
TOP_K = 10
RNG_SEED = 9  # local to this report; independent of seed.py's SEED and tuning.py's 7

YIELD_TARGET_SPEC = 10   # spec §11 item 1
YIELD_TARGET_PRD = 15    # PRD §2
BUNCHED_LOW, BUNCHED_HIGH = 0.70, 0.80   # spec §11 item 3's failure signature
HEALTHY_LOW, HEALTHY_HIGH = 0.35, 0.90   # spec §11 item 3's healthy range

# Relevance grade >= this is "relevant" for precision@k (grades 3-4 of 0-4 =
# the top two of five, <=25% of attributes deviated). recovery.py sizes each
# subject's pool so >=10 candidates clear this bar — a perfect precision@10
# is achievable, not capped by construction.
RELEVANT_GRADE_THRESHOLD = 3


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


def _rank_transform(values: list[float]) -> list[float]:
    """Average rank for ties — the standard Spearman treatment."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _pearson(_rank_transform(xs), _rank_transform(ys))


# --- 1: filter yield ---------------------------------------------------------

def _print_yield(ranker: MatchRanker, subjects: list[Candidate], pool: list[Candidate]) -> None:
    print("=" * 72)
    print(f"1. FILTER YIELD  (over {len(subjects)} subjects, pool={len(pool)})")
    if not subjects:
        print("  no verified/active subjects in the pool — seed the database first.\n")
        return

    counts: list[int] = []
    reason_tally: dict[str, int] = {}
    for subject in subjects:
        eligible, excluded = ranker.filter_with_reasons(subject, pool)
        counts.append(len(eligible))
        for ex in excluded:
            reason_tally[ex.reason] = reason_tally.get(ex.reason, 0) + 1

    median = statistics.median(counts)
    print(f"  eligible pool: min={min(counts)}  median={median:g}  max={max(counts)}")
    if median < YIELD_TARGET_SPEC:
        flag = f"[BELOW spec §11's target of {YIELD_TARGET_SPEC}]"
    elif median < YIELD_TARGET_PRD:
        flag = f"[meets spec §11's {YIELD_TARGET_SPEC} but below PRD §2's {YIELD_TARGET_PRD}]"
    else:
        flag = f"[meets both spec §11 ({YIELD_TARGET_SPEC}) and PRD §2 ({YIELD_TARGET_PRD})]"
    print(f"  {flag}")
    print("  exclusion reasons (most common first):")
    for reason, n in sorted(reason_tally.items(), key=lambda kv: kv[1], reverse=True):
        print(f"    {reason:<24} {n}")
    print()


# --- 2: score distribution ----------------------------------------------------

def _collect_scores(matcher: CompatibilityMatcher, ranker: MatchRanker, subjects: list[Candidate], pool: list[Candidate]) -> list[float]:
    scores: list[float] = []
    for subject in subjects:
        eligible, _ = ranker.filter_with_reasons(subject, pool)
        for candidate in eligible:
            scores.append(matcher.score(subject, candidate).combined_score)
    return scores


def _save_score_distribution_chart(scores: list[float], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(scores, bins=20, range=(0, 1), color="#4C72B0", edgecolor="white")
    ax.axvspan(HEALTHY_LOW, HEALTHY_HIGH, color="#55A868", alpha=0.10,
               label=f"healthy range [{HEALTHY_LOW}, {HEALTHY_HIGH}] (spec §11)")
    ax.set_xlabel("combined_score")
    ax.set_ylabel("eligible pairs")
    ax.set_title(f"Score distribution over {len(scores)} eligible pairs")
    ax.legend(loc="upper left")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _print_score_distribution(scores: list[float]) -> None:
    print("=" * 72)
    print(f"2. SCORE DISTRIBUTION  (over {len(scores)} eligible pairs)")
    if not scores:
        print("  no eligible pairs in the sample.\n")
        return
    bunched = sum(1 for s in scores if BUNCHED_LOW <= s <= BUNCHED_HIGH) / len(scores)
    healthy = sum(1 for s in scores if HEALTHY_LOW <= s <= HEALTHY_HIGH) / len(scores)
    if len(scores) >= 4:
        p25, _, p75 = statistics.quantiles(scores, n=4)
        quantile_str = f"p25={p25:.3f}  median={statistics.median(scores):.3f}  p75={p75:.3f}  "
    else:
        # Too few points for real quartiles — say so rather than print min/max
        # under a "p25"/"p75" label that would misrepresent them as quartiles.
        quantile_str = f"median={statistics.median(scores):.3f}  (too few points for p25/p75)  "
    print(f"  min={min(scores):.3f}  {quantile_str}max={max(scores):.3f}  mean={statistics.mean(scores):.3f}")
    print(f"  within healthy range [{HEALTHY_LOW}, {HEALTHY_HIGH}]: {healthy:.0%}")
    flag = "  [bunched — weights/matrices may not be discriminating]" if bunched > 0.5 else ""
    print(f"  bunched in [{BUNCHED_LOW}, {BUNCHED_HIGH}]: {bunched:.0%}{flag}")

    chart_path = OUTPUT_DIR / "score_distribution.png"
    _save_score_distribution_chart(scores, chart_path)
    print(f"  chart -> {chart_path}")
    print()


# --- 3: ablation over the full attribute registry -----------------------------

def _print_ablation(
    base_ranker: MatchRanker,
    weight_set: WeightSet,
    text_sim: TfidfSimilarity,
    subjects: list[Candidate],
    pool: list[Candidate],
) -> None:
    print("=" * 72)
    print(f"3. ABLATION  (over {len(subjects)} subjects, all {len(ATTRIBUTES)} scored attributes) — THE TABLE")

    baseline_scores: dict = {}     # subject.user_id -> {candidate.user_id: combined_score}
    baseline_top10: dict = {}
    for subject in subjects:
        ranked = base_ranker.rank(subject, pool)
        baseline_scores[subject.user_id] = {m.candidate.user_id: m.result.combined_score for m in ranked}
        baseline_top10[subject.user_id] = [m.candidate.user_id for m in ranked[:TOP_K]]

    for attr in ATTRIBUTES:  # registry order = spec §8 weight table order
        weight = weight_set.weights.get(attr, 0.0)
        ablated_weights = dict(weight_set.weights)
        ablated_weights[attr] = 0.0
        ablated_ranker = MatchRanker(CompatibilityMatcher(ablated_weights, weight_set.id, text_similarity=text_sim))

        overlaps: list[int] = []
        rank1_changed = 0
        deltas: list[float] = []
        base_vals: list[float] = []
        ablated_vals: list[float] = []

        for subject in subjects:
            base_top10 = baseline_top10[subject.user_id]
            base_scores = baseline_scores[subject.user_id]
            ablated_ranked = ablated_ranker.rank(subject, pool)
            ablated_top10 = [m.candidate.user_id for m in ablated_ranked[:TOP_K]]

            overlaps.append(len(set(base_top10) & set(ablated_top10)))
            if base_top10 and ablated_top10 and base_top10[0] != ablated_top10[0]:
                rank1_changed += 1

            for m in ablated_ranked:
                base_score = base_scores.get(m.candidate.user_id)
                if base_score is None:
                    continue  # defensive — ablating a weight never changes Stage-1 eligibility
                deltas.append(abs(base_score - m.result.combined_score))
                base_vals.append(base_score)
                ablated_vals.append(m.result.combined_score)

        mean_delta = statistics.mean(deltas) if deltas else float("nan")
        avg_overlap = statistics.mean(overlaps) if overlaps else float("nan")
        corr = _spearman(base_vals, ablated_vals) if len(base_vals) >= 2 else float("nan")
        never_moves = avg_overlap >= TOP_K - 0.5 and rank1_changed == 0
        flag = "  [never moves the ranking]" if never_moves else ""

        print(f"  {attr:<24} weight={weight:.3f}  mean|Δscore|={mean_delta:.4f}  "
              f"top10 overlap={avg_overlap:.1f}/{TOP_K}  #1 changed={rank1_changed}/{len(subjects)}  "
              f"spearman={corr:.3f}{flag}")
    print()


# --- 4: precision@k / NDCG@10 — recovery experiment ---------------------------

def _select_recovery_subjects(
    candidates: list[Candidate], rng: random.Random, n: int
) -> tuple[list[Candidate], int]:
    """The first `n` candidates whose own profile clears Stage 1 against the
    *best-case* candidate `recovery.py` ever constructs for them
    (`perturb_candidate(subject, fraction=0.0, ...)` — grade 4, nothing
    deviated).

    `perturb_candidate` already neutralises every field its own docstring
    lists as capable of a Stage-1 self-conflict (gender, seeker_type, pets,
    allergies, smoking dealbreaker, verification/account status), so this
    should never actually skip anyone today — confirmed by running the full
    evaluation against the seeded dev DB. It stays as a safety net rather
    than being deleted: every one of those seven fields was found the same
    way (running this live, not by a unit test), so a *future* Stage-1
    check in `eligibility.py` that `recovery.py` hasn't caught up with yet
    is exactly the failure mode this guards against — turning a silently
    biased 0 recovery score into a visible, counted skip instead. See
    docs/DECISIONS.md's Phase 9 section, D-9.2.
    """
    selected: list[Candidate] = []
    skipped = 0
    for subject in candidates:
        if len(selected) >= n:
            break
        best_case = perturb_candidate(subject, fraction=0.0, rng=rng)
        passes, _reason = passes_hard_constraints(subject, best_case)
        if passes:
            selected.append(subject)
        else:
            skipped += 1
    return selected, skipped


def _print_recovery_experiment(
    weight_set: WeightSet, text_sim: TfidfSimilarity, candidate_subjects: list[Candidate], n: int
) -> None:
    print("=" * 72)
    print(f"4. PRECISION@K / NDCG@10 — RECOVERY EXPERIMENT  (over {n} subjects)")
    print("  Construction: each subject gets 30 synthetic candidates across 5 grades")
    print("  (0/25/50/75/100% of 17 attributes deviated to their matrix-defined least-")
    print("  compatible value, spec §4/§5/§6 — recovery.py, docs/DECISIONS.md D-9.1).")
    print("  This validates that the implementation recovers a KNOWN, PLANTED ordering.")
    print("  It is NOT evidence about real roommate compatibility — a synthetic-data")
    print("  performance figure must never be reported as that (PRD §6.6).")

    rng = random.Random(RNG_SEED)
    matcher = CompatibilityMatcher(weight_set.weights, weight_set.id, text_similarity=text_sim)
    ranker = MatchRanker(matcher)

    subjects, skipped = _select_recovery_subjects(candidate_subjects, rng, n)
    if skipped:
        print(f"  skipped {skipped} candidate subject(s): recovery.py's Stage-1")
        print("  neutralisation didn't cover a field this subject's own profile")
        print("  relies on — see docs/DECISIONS.md's Phase 9 section, D-9.2.")
    if not subjects:
        print("  no subjects available for the recovery experiment.\n")
        return

    precisions_5: list[float] = []
    precisions_10: list[float] = []
    ndcgs_10: list[float] = []

    for subject in subjects:
        graded_pool = build_graded_pool(subject, rng)
        grade_by_id = {c.user_id: grade for c, grade in graded_pool}
        candidates = [c for c, _grade in graded_pool]

        ranked_ids = [m.candidate.user_id for m in ranker.rank(subject, candidates)]
        relevant_ids = {cid for cid, grade in grade_by_id.items() if grade >= RELEVANT_GRADE_THRESHOLD}
        ranked_relevances = [grade_by_id[cid] for cid in ranked_ids]

        precisions_5.append(precision_at_k(ranked_ids, relevant_ids, k=5))
        precisions_10.append(precision_at_k(ranked_ids, relevant_ids, k=10))
        ndcgs_10.append(ndcg_at_k(ranked_relevances, k=10))

    print(f"  precision@5:  {statistics.mean(precisions_5):.3f}")
    print(f"  precision@10: {statistics.mean(precisions_10):.3f}")
    print(f"  NDCG@10:      {statistics.mean(ndcgs_10):.3f}")
    print()


# --- 5: survival analysis ------------------------------------------------------

def _save_survival_chart(points: list[KMPoint], n: int, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    if points:
        times = [0] + [p.time for p in points]
        survival = [1.0] + [p.survival for p in points]
        ax.step(times, survival, where="post", color="#C44E52", linewidth=2)
    else:
        ax.text(0.5, 0.5, f"N={n} — insufficient pilot data for a curve\n(PRD line 53)",
                ha="center", va="center", transform=ax.transAxes)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("days since cohabiting_since")
    ax.set_ylabel("survival probability")
    ax.set_title(f"90-day cohabitation survival (Kaplan-Meier), N={n}")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _print_survival(session: Session) -> None:
    print("=" * 72)
    print("5. SURVIVAL ANALYSIS — 90-day cohabitation (PRD line 53's primary outcome)")

    observations = load_cohabitation_observations(session)
    n = len(observations)
    n_events = sum(1 for o in observations if o.event)
    print(f"  observations: {n}  (events/moved_out={n_events}, censored={n - n_events})")

    chart_path = OUTPUT_DIR / "survival_curve.png"
    if n < 3:
        print("  Too few pilot observations for a meaningful curve — expected at this")
        print("  stage (PRD line 53: this metric 'will not be measurable inside the")
        print("  project timeline; the instrumentation is built anyway'). No synthetic")
        print("  data substituted for real pilot outcomes (docs/DECISIONS.md D-9.4).")
        _save_survival_chart([], n, chart_path)
        print(f"  chart -> {chart_path}")
        print()
        return

    points = kaplan_meier(observations)
    for p in points:
        print(f"  t={p.time:>4}d  at_risk={p.at_risk:>3}  events={p.events}  S(t)={p.survival:.3f}")
    _save_survival_chart(points, n, chart_path)
    print(f"  chart -> {chart_path}")
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

        print(f"\nPhase 9 evaluation — weight set v{weight_set.version} ({weight_set.source}), {len(pool)} profiles.\n")

        _print_yield(ranker, subjects[:YIELD_SAMPLE], pool)

        scores = _collect_scores(matcher, ranker, subjects[:SCORE_SAMPLE], pool)
        _print_score_distribution(scores)

        _print_ablation(ranker, weight_set, text_sim, subjects[:ABLATION_SAMPLE], pool)

        _print_recovery_experiment(
            weight_set, text_sim, subjects[:RECOVERY_CANDIDATE_POOL], RECOVERY_SUBJECTS
        )

        _print_survival(session)

        print(f"Charts written under {OUTPUT_DIR}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

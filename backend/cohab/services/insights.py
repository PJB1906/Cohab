"""Match-screen insights (Cohab v2 plan W6 showcase items 3 and 4).

1. Pool insights — "why am I seeing so few people?" Stage 1 already records
   why every candidate was excluded; this counts those reasons for the
   viewer and tests one-step relaxations (raise the budget ceiling, open
   the gender preference) by re-running Stage 1, so each suggestion's
   number is exact, not estimated. Counts only: no excluded person is
   named or described.
2. Tie hint — whether the top three are effectively tied, judged by
   re-scoring them under plausible alternative weight vectors
   (`analysis.stability.top3_tie_hint`, D-14.9).
3. Confidence tier — a calibrated "would message" probability, only when a
   calibration model is active, always with its version and data source.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.analysis.stability import dirichlet_prior_samples, top3_tie_hint
from cohab.models import CalibrationModel, User, WeightSet, WeightSetUncertainty
from cohab.services.matches import _load_candidate, _load_pool, _settled_pairs_for
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.eligibility import EligibilityFilter, Reason, passes_hard_constraints
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher, blend, harmonic_mean
from cohab.services.matching.text import NeutralTextSimilarity
from cohab.services.safety import blocked_pairs_for
from cohab.services.study.instrument import STUDY_ATTRIBUTES

BUDGET_STEPS = (1000, 2000, 3000)
PRIOR_SAMPLES = 40
PRIOR_CONCENTRATION = 200.0
TOP_N_FOR_TIE = 10
PROB_FLOOR, PROB_CEIL = 0.03, 0.97  # D-14.10

# Proposed thresholds on the calibrated would-message probability (D-14.10).
TIERS = ((0.60, "strong"), (0.35, "good"), (0.0, "possible"))

REASON_LABELS = {
    Reason.NOT_VERIFIED_OR_ACTIVE: "Not verified or not active yet",
    Reason.BOTH_HAVE_PLACE: "Also has a place (two place-owners can't pair)",
    Reason.DIFFERENT_CITY: "Looking in a different city",
    Reason.BUDGET_NO_OVERLAP: "Budget ranges don't overlap",
    Reason.MOVE_IN_TOO_FAR: "Move-in dates more than 30 days apart",
    Reason.GENDER_PREFERENCE: "Gender preference (yours or theirs)",
    Reason.SEVERE_ALLERGY: "Allergy conflict",
    Reason.PET_CONFLICT: "Pet conflict",
    Reason.SMOKING_DEALBREAKER: "Indoor smoking deal-breaker",
    Reason.BLOCKED: "Blocked",
    Reason.ALREADY_DECIDED: "Already decided (rejected or moved in)",
}


@dataclass(frozen=True)
class Suggestion:
    kind: str
    label: str
    adds: int


def _excluded_only_by(subject: Candidate, pool: Sequence[Candidate], flt: EligibilityFilter, reason: str) -> list[Candidate]:
    out = []
    for c in pool:
        if c.user_id == subject.user_id:
            continue
        ok, why = passes_hard_constraints(subject, c, flt.blocked_pairs, flt.settled_pairs)
        if not ok and why == reason:
            out.append(c)
    return out


def _count_eligible(subject: Candidate, pool: Sequence[Candidate], flt: EligibilityFilter) -> int:
    return sum(
        1
        for c in pool
        if c.user_id != subject.user_id and passes_hard_constraints(subject, c, flt.blocked_pairs, flt.settled_pairs)[0]
    )


def pool_insights(subject: Candidate, pool: Sequence[Candidate], flt: EligibilityFilter) -> dict[str, Any]:
    eligible, excluded = flt.filter(subject, pool)
    counts: dict[str, int] = {}
    for ex in excluded:
        counts[ex.reason] = counts.get(ex.reason, 0) + 1
    # Never show reasons that reveal account state or other people's actions.
    hidden = {Reason.NOT_VERIFIED_OR_ACTIVE, Reason.BLOCKED, Reason.ALREADY_DECIDED}
    reasons = [
        {"reason": r, "label": REASON_LABELS.get(r, r), "count": n}
        for r, n in sorted(counts.items(), key=lambda kv: -kv[1])
        if r not in hidden
    ]

    base = len(eligible)
    suggestions: list[Suggestion] = []
    budget_blocked = _excluded_only_by(subject, pool, flt, Reason.BUDGET_NO_OVERLAP)
    if subject.seeker_type == "needs_place" and budget_blocked:
        for step in BUDGET_STEPS:
            relaxed = dataclasses.replace(subject, budget_max=subject.budget_max + step)
            adds = _count_eligible(relaxed, pool, flt) - base
            if adds > 0:
                suggestions.append(Suggestion("budget", f"Raise your maximum budget by ₹{step:,}", adds))
                break
    if subject.gender_preference != "any":
        relaxed = dataclasses.replace(subject, gender_preference="any")
        adds = _count_eligible(relaxed, pool, flt) - base
        if adds > 0:
            suggestions.append(Suggestion("gender_preference", "Open your roommate gender preference to anyone", adds))
    return {
        "eligible": base,
        "considered": len(pool),
        "excluded_by_reason": reasons,
        "suggestions": [dataclasses.asdict(s) for s in suggestions],
    }


def weight_samples(session: Session, weight_set: WeightSet) -> tuple[list[dict], str]:
    row = session.scalar(select(WeightSetUncertainty).where(WeightSetUncertainty.weight_set_id == weight_set.id))
    if row is not None and row.samples:
        return list(row.samples), row.method
    return (
        dirichlet_prior_samples(weight_set.weights, PRIOR_SAMPLES, PRIOR_CONCENTRATION, seed=weight_set.version),
        "dirichlet_prior",
    )


def _rescore(a: Candidate, b: Candidate, breakdown: Mapping[str, Mapping[str, float]], weights: Mapping[str, float]) -> float:
    present = [n for n in breakdown if n in weights]
    wa = blend(dict(weights), a.important_attributes)
    wb = blend(dict(weights), b.important_attributes)
    ta = sum(wa[n] for n in present) or 1.0
    tb = sum(wb[n] for n in present) or 1.0
    s_ab = sum(wa[n] / ta * breakdown[n]["sim_a"] for n in present)
    s_ba = sum(wb[n] / tb * breakdown[n]["sim_b"] for n in present)
    return harmonic_mean(s_ab, s_ba)


def tie_hint(subject: Candidate, ranked, samples: Sequence[Mapping[str, float]]) -> dict[str, Any]:
    top = ranked[:TOP_N_FOR_TIE]
    if len(top) < 3:
        return {"tied": False, "set_overlap": None, "order_change": None}
    per_sample = [
        np.array([_rescore(subject, m.candidate, m.result.breakdown, s) for m in top]) for s in samples
    ]
    return top3_tie_hint(per_sample)


# --- calibration ---------------------------------------------------------------


def active_calibration(session: Session, weight_set: WeightSet) -> CalibrationModel | None:
    return session.scalar(
        select(CalibrationModel).where(
            CalibrationModel.is_active.is_(True), CalibrationModel.weight_set_id == weight_set.id
        )
    )


def study_score_towards(breakdown: Mapping[str, Mapping[str, float]], side: str = "a") -> float | None:
    """S(subject -> candidate) restricted to the study attributes and
    renormalised: the quantity the calibration map was fitted on."""
    w_key, s_key = f"w_{side}", f"sim_{side}"
    items = [(v[w_key], v[s_key]) for k, v in breakdown.items() if k in STUDY_ATTRIBUTES]
    total = sum(w for w, _ in items)
    if total <= 0:
        return None
    return sum(w * s for w, s in items) / total


def tier_for(probability: float) -> str:
    for threshold, name in TIERS:
        if probability >= threshold:
            return name
    return "possible"


def calibrate(cal: CalibrationModel | None, breakdown: Mapping[str, Mapping[str, float]], side: str = "a") -> dict | None:
    if cal is None:
        return None
    s = study_score_towards(breakdown, side)
    if s is None:
        return None
    # Isotonic maps saturate at 0 and 1 where data runs out; no calibration
    # supports certainty, so the displayed probability is kept off the ends.
    p = float(np.clip(np.interp(s, cal.knots["x"], cal.knots["y"]), PROB_FLOOR, PROB_CEIL))
    return {
        "would_message_probability": p,
        "confidence_tier": tier_for(p),
        "calibration_version": cal.version,
        "calibration_source": cal.data_source,
    }


# --- assembled -------------------------------------------------------------------


def match_insights(session: Session, user: User, weight_set: WeightSet) -> dict[str, Any]:
    subject = _load_candidate(session, user.id)
    if subject is None:
        return {"pool": None, "tie_hint": None, "calibration": None}
    pool = _load_pool(session, user.id)
    flt = EligibilityFilter(blocked_pairs_for(session, user.id), _settled_pairs_for(session, user.id))
    ranker = MatchRanker(CompatibilityMatcher(weight_set.weights, weight_set.id, NeutralTextSimilarity()))
    ranker.filter = flt
    ranked = ranker.rank(subject, pool)
    samples, method = weight_samples(session, weight_set)
    hint = tie_hint(subject, ranked, samples)
    hint["method"] = method
    hint["top3_candidate_ids"] = [str(m.candidate.user_id) for m in ranked[:3]]
    cal = active_calibration(session, weight_set)
    return {
        "pool": pool_insights(subject, pool, flt),
        "tie_hint": hint,
        "calibration": (
            {"active": True, "version": cal.version, "data_source": cal.data_source, "target": cal.target}
            if cal
            else {"active": False}
        ),
    }

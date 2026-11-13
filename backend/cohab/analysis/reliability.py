"""Data quality: pre-registered exclusions, test-retest reliability, and the
noise ceiling (Cohab v2 plan W2/W4; docs/COHAB_HUMAN_STUDY.md §5).

Exclusion rules are fixed here, in code, before any real data exists:
1. Failed two or more of the three attention checks.
2. Median response time on pair trials under 1,500 ms (not reading the cards).
3. Fewer than 20 answered pair trials (abandoned early).
4. Chose "no preference" on more than half the pair trials.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from cohab.services.study.export import RaterRecord

MAX_ATTENTION_FAILS = 1
MIN_MEDIAN_MS = 1500
MIN_PAIR_TRIALS = 20
MAX_NONE_SHARE = 0.5


@dataclass
class Exclusion:
    rater_id: str
    reasons: list[str]


def exclusion_reasons(r: RaterRecord) -> list[str]:
    reasons = []
    attention = [t for t in r.trials if t.kind == "attention"]
    fails = sum(1 for t in attention if t.chosen != t.expected)
    if fails > MAX_ATTENTION_FAILS:
        reasons.append("attention")
    pairs = [t for t in r.trials if t.kind == "pair"]
    times = [t.response_ms for t in pairs if t.response_ms is not None]
    if times and float(np.median(times)) < MIN_MEDIAN_MS:
        reasons.append("too_fast")
    if len(pairs) < MIN_PAIR_TRIALS:
        reasons.append("incomplete")
    if pairs and sum(1 for t in pairs if t.chosen is None) / len(pairs) > MAX_NONE_SHARE:
        reasons.append("no_preference")
    return reasons


def apply_exclusions(raters: list[RaterRecord]) -> tuple[list[RaterRecord], list[Exclusion]]:
    kept, excluded = [], []
    for r in raters:
        reasons = exclusion_reasons(r)
        if reasons:
            excluded.append(Exclusion(r.rater_id, reasons))
        else:
            kept.append(r)
    return kept, excluded


def repeat_pairs(raters: list[RaterRecord]) -> list[tuple[str, str, str]]:
    """(rater_id, first choice, repeat choice) as card ids, both non-None."""
    out = []
    for r in raters:
        by_pos = {t.position: t for t in r.trials}
        for t in r.trials:
            if t.kind == "repeat" and t.repeat_of in by_pos:
                a, b = by_pos[t.repeat_of].chosen, t.chosen
                if a is not None and b is not None:
                    out.append((r.rater_id, a, b))
    return out


def cohens_kappa(first: list[str], second: list[str]) -> float:
    """Cohen's kappa for two binary codings of the same items (card A vs B)."""
    n = len(first)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in zip(first, second) if a == b) / n
    p1 = sum(1 for a in first if a == "A") / n
    p2 = sum(1 for b in second if b == "A") / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def noise_ceiling(agreement: float) -> float:
    """If each choice independently matches a rater's stable preference with
    probability q, two presentations agree with probability q^2 + (1-q)^2.
    Solving for q gives the best accuracy any model of stable preferences can
    reach on these raters."""
    if agreement <= 0.5:
        return 0.5
    return (1 + math.sqrt(2 * agreement - 1)) / 2


def reliability_summary(raters: list[RaterRecord], n_boot: int = 2000, seed: int = 0) -> dict:
    reps = repeat_pairs(raters)
    if not reps:
        return {"n_repeats": 0}
    first = [a for _, a, _ in reps]
    second = [b for _, _, b in reps]
    agree = sum(1 for a, b in zip(first, second) if a == b) / len(reps)

    # Bootstrap over raters, not over repeat pairs (pairs within a rater
    # are not independent).
    by_rater: dict[str, list[tuple[str, str]]] = {}
    for rid, a, b in reps:
        by_rater.setdefault(rid, []).append((a, b))
    ids = list(by_rater)
    rng = np.random.default_rng(seed)
    boot_agree, boot_kappa = [], []
    for _ in range(n_boot):
        sample = [p for rid in rng.choice(ids, size=len(ids), replace=True) for p in by_rater[rid]]
        f, s = [a for a, _ in sample], [b for _, b in sample]
        boot_agree.append(sum(1 for a, b in sample if a == b) / len(sample))
        boot_kappa.append(cohens_kappa(f, s))
    lo, hi = np.percentile(boot_agree, [2.5, 97.5])
    klo, khi = np.nanpercentile(boot_kappa, [2.5, 97.5])
    return {
        "n_repeats": len(reps),
        "agreement": agree,
        "agreement_ci": [float(lo), float(hi)],
        "kappa": cohens_kappa(first, second),
        "kappa_ci": [float(klo), float(khi)],
        "noise_ceiling_accuracy": noise_ceiling(agree),
        "noise_ceiling_ci": [noise_ceiling(float(lo)), noise_ceiling(float(hi))],
    }

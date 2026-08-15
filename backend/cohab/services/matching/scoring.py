"""Stage 2 — directional compatibility scoring (COHAB_MATCHING_SPEC.md §9).

Computes S(a→b) under A's weights and S(b→a) under B's, combines them with the
harmonic mean so a match that suits only one party cannot hide (spec §6.3), and
returns the full per-attribute breakdown plus the `weight_set_id` the score was
computed under (immutability guarantee, spec §6.5 / CLAUDE.md).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from cohab.services.matching.attributes import ATTRIBUTES, ScoringContext
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.text import NeutralTextSimilarity, TextSimilarity

IMPORTANCE_MULTIPLIER = 1.5  # spec §9: selected attributes ×1.5


@dataclass
class MatchResult:
    """One scored pair. `a` is the subject, `b` the candidate; `score_ab` is
    S(a→b) under A's weights. `combined_score` is order-independent."""

    subject_id: uuid.UUID
    candidate_id: uuid.UUID
    score_ab: float
    score_ba: float
    combined_score: float
    weight_set_id: uuid.UUID
    breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)


def harmonic_mean(x: float, y: float) -> float:
    """spec §9: 2xy / (x + y), with a guard so 0 + 0 does not divide by zero."""
    if x + y == 0:
        return 0.0
    return 2 * x * y / (x + y)


def blend(defaults: dict[str, float], important: frozenset[str] | set[str]) -> dict[str, float]:
    """spec §9/§3: boost each selected attribute to 1.5× its default weight, then
    scale the remainder down so the vector still sums to 1.

    The property this preserves: a selected attribute's final weight is exactly
    1.5× its default; only the unselected remainder absorbs the renormalisation.
    """
    boosted = {
        name: (weight * IMPORTANCE_MULTIPLIER if name in important else weight)
        for name, weight in defaults.items()
    }
    selected_sum = sum(w for n, w in boosted.items() if n in important)
    rest_sum = sum(w for n, w in boosted.items() if n not in important)

    # Degenerate cases (no remainder, or the boost alone already exceeds 1):
    # fall back to a plain renormalisation of the whole vector.
    if rest_sum <= 0 or selected_sum >= 1:
        total = sum(boosted.values()) or 1.0
        return {n: w / total for n, w in boosted.items()}

    scale = (1 - selected_sum) / rest_sum
    return {
        name: (weight if name in important else weight * scale)
        for name, weight in boosted.items()
    }


def _renormalise(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    if total == 0:
        return {name: 0.0 for name in weights}
    return {name: w / total for name, w in weights.items()}


class CompatibilityMatcher:
    def __init__(
        self,
        default_weights: dict[str, float],
        weight_set_id: uuid.UUID,
        text_similarity: TextSimilarity | None = None,
    ) -> None:
        self.default_weights = default_weights
        self.weight_set_id = weight_set_id
        self.ctx = ScoringContext(text_similarity=text_similarity or NeutralTextSimilarity())

    def score(self, a: Candidate, b: Candidate) -> MatchResult:
        # Attributes that are both weighted and answered by both parties (spec §8).
        present = [
            attr
            for name, attr in ATTRIBUTES.items()
            if name in self.default_weights and attr.is_present(a, b)
        ]

        # Blend in each party's importance choices (spec §9), then restrict to the
        # present attributes and renormalise each vector to 1 (spec §8, §9).
        w_a_full = blend(self.default_weights, a.important_attributes)
        w_b_full = blend(self.default_weights, b.important_attributes)
        w_a = _renormalise({attr.name: w_a_full[attr.name] for attr in present})
        w_b = _renormalise({attr.name: w_b_full[attr.name] for attr in present})

        breakdown: dict[str, dict[str, Any]] = {}
        score_ab = 0.0
        score_ba = 0.0
        for attr in present:
            sim_a, sim_b = attr.score(a, b, self.ctx)
            score_ab += w_a[attr.name] * sim_a
            score_ba += w_b[attr.name] * sim_b
            breakdown[attr.name] = {
                "type": attr.type,
                "sim_a": sim_a,
                "sim_b": sim_b,
                "w_a": w_a[attr.name],
                "w_b": w_b[attr.name],
            }

        return MatchResult(
            subject_id=a.user_id,
            candidate_id=b.user_id,
            score_ab=score_ab,
            score_ba=score_ba,
            combined_score=harmonic_mean(score_ab, score_ba),
            weight_set_id=self.weight_set_id,
            breakdown=breakdown,
        )

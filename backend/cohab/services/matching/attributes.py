"""The attribute registry — the one place the weight vector's grouped keys are
resolved to questionnaire fields, types and scorers.

The weight vector (spec §8, `weight_set.weights`) is keyed by *attribute* names
like `noise`, `guests`, `smoking`, `nonveg_cooking`, `budget_proximity` — which
do NOT map one-to-one onto the 24 questionnaire fields. Each `Attribute` here
records its type (spec §1), the field(s) it reads, whether it can be dropped when
unanswered (spec §8), and a directional `score(a, b) -> (sim_a, sim_b)`
following the procedure in spec §9. Explanation copy (spec §10) is selected by
`name` directly — see `explanations.py`'s `AGREEMENT_RENDERERS`/
`DIVERGENCE_RENDERERS` — not by a separate template key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.matrices import (
    ORDINAL_ORDERS,
    PAYMENT_RELIABILITY,
    SIMILARITY_MATRICES,
    TOLERANCE_MATRICES,
    budget_similarity,
    jaccard_similarity,
    ordinal_similarity,
    vector_cosine_similarity,
)
from cohab.services.matching.text import NeutralTextSimilarity, TextSimilarity


@dataclass
class ScoringContext:
    """Per-run collaborators for scorers that need more than the two candidates."""

    text_similarity: TextSimilarity = NeutralTextSimilarity()


# A scorer returns the directional pair (sim_a, sim_b) for one attribute.
Scorer = Callable[[Candidate, Candidate, ScoringContext], tuple[float, float]]


@dataclass(frozen=True)
class Attribute:
    name: str  # weight-vector key (spec §8)
    type: str  # 'similarity' | 'tolerance' | 'absolute' | 'continuous' | 'semantic'
    fields: tuple[str, ...]  # questionnaire fields read (for the presence check)
    score: Scorer
    # Droppable attributes are removed from the weight vectors when unanswered by
    # either party (spec §8). budget_proximity/interests/lifestyle_notes are never
    # dropped: they are always defined, or carry their own empty-handling
    # (interests floor 0.3 §4, notes neutral 0.5 §7).
    droppable: bool = True

    def is_present(self, a: Candidate, b: Candidate) -> bool:
        if not self.droppable:
            return True
        return all(
            a.answer(f) is not None and b.answer(f) is not None for f in self.fields
        )


# --- Scorer factories ------------------------------------------------------

def _similarity_matrix(matrix_name: str, field: str) -> Scorer:
    matrix = SIMILARITY_MATRICES[matrix_name]

    def score(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
        s = matrix[a.answer(field)][b.answer(field)]
        return s, s  # symmetric

    return score


def _ordinal(field: str) -> Scorer:
    order = ORDINAL_ORDERS[field]

    def score(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
        s = ordinal_similarity(order, a.answer(field), b.answer(field))
        return s, s

    return score


def _tolerance(matrix_name: str, pref_field: str, behav_field: str) -> Scorer:
    """rows = A's preference, cols = B's behaviour (spec §5).

    sim_a = how well B's behaviour suits A; sim_b = the reverse.
    """
    matrix = TOLERANCE_MATRICES[matrix_name]

    def score(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
        sim_a = matrix[a.answer(pref_field)][b.answer(behav_field)]
        sim_b = matrix[b.answer(pref_field)][a.answer(behav_field)]
        return sim_a, sim_b

    return score


def _absolute(field: str) -> Scorer:
    """spec §6: score depends only on the *other* person's value."""

    def score(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
        return PAYMENT_RELIABILITY[b.answer(field)], PAYMENT_RELIABILITY[a.answer(field)]

    return score


def _budget(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
    s = budget_similarity(a.budget_midpoint, b.budget_midpoint)
    return s, s


def _interests(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
    s = jaccard_similarity(a.answer("interests"), b.answer("interests"))
    return s, s


def _notes(a: Candidate, b: Candidate, ctx: ScoringContext) -> tuple[float, float]:
    # Prefer the cached vectors written at profile save (CLAUDE.md, spec §7 —
    # "never encode inside the match request path") when both sides carry one
    # of the same kind. Falls back to the live text-similarity collaborator —
    # a raw-text transform — for a pool member saved before this cache
    # existed, or for the offline report.py/tuning.py callers that never
    # populate it at all.
    if (
        a.text_vector is not None
        and b.text_vector is not None
        and a.text_vector_kind is not None
        and a.text_vector_kind == b.text_vector_kind
    ):
        s = vector_cosine_similarity(a.text_vector, b.text_vector)
    else:
        s = ctx.text_similarity.similarity(a.lifestyle_notes, b.lifestyle_notes)
    return s, s


# --- Registry (canonical order = spec §8 weight table) ---------------------

_ATTRIBUTE_LIST: list[Attribute] = [
    # Tier 1
    Attribute("cleanliness_level", "similarity", ("cleanliness_level",),
              _similarity_matrix("cleanliness_level", "cleanliness_level")),
    Attribute("chore_approach", "similarity", ("chore_approach",),
              _similarity_matrix("chore_approach", "chore_approach")),
    Attribute("sharing_norm", "tolerance", ("sharing_norm",),
              _tolerance("sharing", "sharing_norm", "sharing_norm")),
    Attribute("sleep_schedule", "similarity", ("sleep_schedule",),
              _similarity_matrix("sleep_schedule", "sleep_schedule")),
    Attribute("noise", "tolerance", ("noise_preference", "noise_behaviour"),
              _tolerance("noise", "noise_preference", "noise_behaviour")),
    Attribute("guests", "tolerance", ("guest_tolerance", "guest_frequency"),
              _tolerance("guests", "guest_tolerance", "guest_frequency")),
    Attribute("payment_reliability", "absolute", ("payment_reliability",),
              _absolute("payment_reliability")),
    Attribute("cost_split_preference", "similarity", ("cost_split_preference",),
              _similarity_matrix("cost_split_preference", "cost_split_preference")),
    Attribute("communication_style", "similarity", ("communication_style",),
              _similarity_matrix("communication_style", "communication_style")),
    Attribute("budget_proximity", "continuous", (), _budget, droppable=False),
    Attribute("diet", "similarity", ("diet",),
              _similarity_matrix("diet", "diet")),
    Attribute("nonveg_cooking", "tolerance", ("nonveg_cooking_tolerance", "diet"),
              _tolerance("nonveg_cooking", "nonveg_cooking_tolerance", "diet")),
    Attribute("smoking", "tolerance", ("smoking_tolerance", "smoking_behaviour"),
              _tolerance("smoking", "smoking_tolerance", "smoking_behaviour")),
    Attribute("alcohol", "tolerance", ("alcohol_tolerance", "alcohol_behaviour"),
              _tolerance("alcohol", "alcohol_tolerance", "alcohol_behaviour")),
    # Tier 2
    Attribute("life_stage", "similarity", ("life_stage",),
              _similarity_matrix("life_stage", "life_stage")),
    Attribute("daytime_presence", "similarity", ("daytime_presence",),
              _ordinal("daytime_presence")),
    Attribute("home_orientation", "similarity", ("home_orientation",),
              _ordinal("home_orientation")),
    Attribute("sociability", "similarity", ("sociability",),
              _similarity_matrix("sociability", "sociability")),
    # Tier 3
    Attribute("interests", "similarity", ("interests",), _interests, droppable=False),
    Attribute("lifestyle_notes", "semantic", ("lifestyle_notes",), _notes, droppable=False),
]

ATTRIBUTES: dict[str, Attribute] = {a.name: a for a in _ATTRIBUTE_LIST}

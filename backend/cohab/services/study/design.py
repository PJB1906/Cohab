"""Trial design for Cohab Lab: a choice-based conjoint (Cohab v2 plan W2).

Why designed pairs instead of pairs sampled from the seeded pool (the v1
deck's plan): seeded profiles have correlated attributes, so 20 weights would
be confounded; and a rater comparing two cards that differ on everything
attends to three or four attributes, which shrinks the rest to zero for
reasons that have nothing to do with preference. Here the two cards of a
trial are identical except on N_VARIED fields, chosen so every field is
varied about equally often for each rater.

Pure functions of (rater answers, seed): no database, fully reproducible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from cohab.services.study.features import card_vector
from cohab.services.study.instrument import (
    CARD_FIELDS,
    MIN_REPEAT_GAP,
    N_ATTENTION,
    N_PAIR_TRIALS,
    N_RANK,
    N_REPEATS,
    N_VARIED,
    OPTIONS,
    POPULATION_WEIGHTS,
    RANK_CARDS,
)
from cohab.services.study.features import attribute_score  # noqa: F401  (re-export for callers)


@dataclass
class PlannedTrial:
    position: int
    kind: str
    cards: list[dict]
    varied_attributes: list[str] = field(default_factory=list)
    repeat_of: int | None = None
    expected_card: str | None = None


def _sample_field(rng: random.Random, f: str) -> str:
    return rng.choices(OPTIONS[f], weights=POPULATION_WEIGHTS.get(f), k=1)[0]


def _base_profile(rng: random.Random) -> dict[str, str]:
    return {f: _sample_field(rng, f) for f in CARD_FIELDS}


def _balanced_fields(rng: random.Random, usage: dict[str, int], k: int) -> list[str]:
    """k distinct fields, preferring the least-used so far (ties random)."""
    order = sorted(CARD_FIELDS, key=lambda f: (usage[f], rng.random()))
    chosen = order[:k]
    for f in chosen:
        usage[f] += 1
    return chosen


def _pair_trial(rng: random.Random, usage: dict[str, int]) -> tuple[list[dict], list[str]]:
    base = _base_profile(rng)
    left, right = dict(base), dict(base)
    varied = _balanced_fields(rng, usage, N_VARIED)
    for f in varied:
        a, b = rng.sample(OPTIONS[f], 2)
        left[f], right[f] = a, b
    cards = [{"id": "A", "answers": left}, {"id": "B", "answers": right}]
    rng.shuffle(cards)  # left/right randomised against position bias
    return cards, sorted(varied)


def _extreme_card(rater: dict[str, str], best: bool) -> dict[str, str]:
    """Per field, the option giving the rater the highest (or lowest)
    directional score: an obviously good or obviously bad roommate."""
    card: dict[str, str] = {}
    for f in CARD_FIELDS:
        scored = []
        for v in OPTIONS[f]:
            probe = {g: OPTIONS[g][0] for g in CARD_FIELDS}
            probe[f] = v
            scored.append((float(card_vector(rater, probe).sum()), v))
        scored.sort(reverse=best)
        card[f] = scored[0][1]
    return card


def plan_trials(rater_answers: dict[str, str], seed: int) -> list[PlannedTrial]:
    rng = random.Random(seed)
    usage = {f: 0 for f in CARD_FIELDS}

    pairs = []
    for _ in range(N_PAIR_TRIALS):
        cards, varied = _pair_trial(rng, usage)
        pairs.append(("pair", cards, varied, None, None))

    good = _extreme_card(rater_answers, best=True)
    bad = _extreme_card(rater_answers, best=False)
    attention = []
    for _ in range(N_ATTENTION):
        cards = [{"id": "A", "answers": dict(good)}, {"id": "B", "answers": dict(bad)}]
        rng.shuffle(cards)
        attention.append(("attention", cards, [], None, "A"))

    # Interleave: attention checks spread through the pair trials.
    sequence: list[tuple] = list(pairs)
    slots = sorted(rng.sample(range(4, len(sequence)), N_ATTENTION))
    for offset, (slot, trial) in enumerate(zip(slots, attention)):
        sequence.insert(slot + offset, trial)

    # Repeats: copies of earlier pair trials with the cards swapped, at least
    # MIN_REPEAT_GAP positions later, appended across the second half.
    candidates = [t for i, t in enumerate(sequence) if t[0] == "pair" and i < len(sequence) - MIN_REPEAT_GAP]
    for original in rng.sample(candidates, N_REPEATS):
        _, cards, varied, _, _ = original
        orig_index = next(i for i, t in enumerate(sequence) if t is original)
        slot = rng.randint(orig_index + MIN_REPEAT_GAP + 1, len(sequence))
        swapped = [dict(cards[1]), dict(cards[0])]
        sequence.insert(slot, ("repeat", swapped, varied, None, None))

    # Repeat-of must point at the final position of its original.
    final: list[PlannedTrial] = []
    for pos, (kind, cards, varied, repeat_of, expected) in enumerate(sequence):
        final.append(PlannedTrial(pos, kind, cards, list(varied), repeat_of, expected))
    _fix_repeat_targets(final)

    for _ in range(N_RANK):
        cards = [{"id": chr(ord("A") + k), "answers": _base_profile(rng)} for k in range(RANK_CARDS)]
        final.append(PlannedTrial(len(final), "rank", cards))
    return final


def _fix_repeat_targets(trials: list[PlannedTrial]) -> None:
    """Point each repeat at the pair trial with the same cards (swapped)."""
    def key(cards: list[dict]) -> tuple:
        return tuple(sorted((c["id"], tuple(sorted(c["answers"].items()))) for c in cards))

    by_key = {key(t.cards): t.position for t in trials if t.kind == "pair"}
    for t in trials:
        if t.kind == "repeat":
            t.repeat_of = by_key[key(t.cards)]
            assert t.repeat_of < t.position

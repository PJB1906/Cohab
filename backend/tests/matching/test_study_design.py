"""Cohab Lab trial design (Cohab v2 plan W2): conjoint properties."""

from __future__ import annotations

import random
from collections import Counter

import numpy as np
import pytest

from cohab.seed import DEFAULT_WEIGHTS
from cohab.services.study.design import plan_trials
from cohab.services.study.features import card_vector, weighted_score
from cohab.services.study.instrument import (
    CARD_FIELDS,
    N_ATTENTION,
    N_PAIR_TRIALS,
    N_RANK,
    N_REPEATS,
    N_VARIED,
    OPTIONS,
    RATER_FIELDS,
    STUDY_ATTRIBUTES,
    validate_rater_answers,
)


def rater(seed: int = 0) -> dict[str, str]:
    rng = random.Random(seed)
    return {f: rng.choice(OPTIONS[f]) for f in RATER_FIELDS}


@pytest.fixture(params=[1, 2, 3])
def rater_and_plan(request):
    r = rater(request.param)
    return r, plan_trials(r, seed=request.param * 101)


@pytest.fixture()
def plan(rater_and_plan):
    return rater_and_plan[1]


def test_counts_and_positions(plan) -> None:
    kinds = Counter(t.kind for t in plan)
    assert kinds == {"pair": N_PAIR_TRIALS, "repeat": N_REPEATS, "attention": N_ATTENTION, "rank": N_RANK}
    assert [t.position for t in plan] == list(range(len(plan)))
    assert plan[-1].kind == "rank"


def test_pair_cards_differ_only_on_varied_fields(plan) -> None:
    for t in plan:
        if t.kind != "pair":
            continue
        left, right = (c["answers"] for c in t.cards)
        differing = sorted(f for f in CARD_FIELDS if left[f] != right[f])
        assert differing == sorted(t.varied_attributes)
        assert len(differing) == N_VARIED
        assert {c["id"] for c in t.cards} == {"A", "B"}


def test_fields_are_varied_about_equally(plan) -> None:
    usage = Counter(f for t in plan if t.kind == "pair" for f in t.varied_attributes)
    assert set(usage) == set(CARD_FIELDS)
    assert max(usage.values()) - min(usage.values()) <= 1


def test_left_right_is_randomised_across_trials() -> None:
    lefts = Counter(t.cards[0]["id"] for s in range(20) for t in plan_trials(rater(s), s) if t.kind == "pair")
    assert 0.4 < lefts["A"] / sum(lefts.values()) < 0.6


def test_repeats_swap_an_earlier_pair_with_a_gap(plan) -> None:
    by_pos = {t.position: t for t in plan}
    for t in plan:
        if t.kind != "repeat":
            continue
        orig = by_pos[t.repeat_of]
        assert orig.kind == "pair"
        assert t.position - orig.position > 6
        assert [c["id"] for c in t.cards] == [c["id"] for c in reversed(orig.cards)]
        assert {c["id"]: c["answers"] for c in t.cards} == {c["id"]: c["answers"] for c in orig.cards}


def test_attention_checks_are_unambiguous(rater_and_plan) -> None:
    r, plan = rater_and_plan
    for t in plan:
        if t.kind != "attention":
            continue
        cards = {c["id"]: c["answers"] for c in t.cards}
        good = weighted_score(r, cards[t.expected_card], DEFAULT_WEIGHTS)
        bad = weighted_score(r, cards["B" if t.expected_card == "A" else "A"], DEFAULT_WEIGHTS)
        assert good - bad > 0.4


def test_plan_is_deterministic_for_a_seed() -> None:
    a, b = plan_trials(rater(4), 9), plan_trials(rater(4), 9)
    assert [(t.kind, t.cards) for t in a] == [(t.kind, t.cards) for t in b]


def test_card_vector_matches_matrices() -> None:
    r = rater(2)
    card = {f: OPTIONS[f][0] for f in CARD_FIELDS}
    v = card_vector(r, card)
    assert v.shape == (len(STUDY_ATTRIBUTES),)
    assert np.all((0 <= v) & (v <= 1))
    # payment_reliability is absolute: depends only on the card's answer.
    i = STUDY_ATTRIBUTES.index("payment_reliability")
    assert v[i] == 1.0  # card answered "early"


def test_validate_rater_answers() -> None:
    assert validate_rater_answers(rater(0)) == []
    bad = rater(0) | {"sleep_schedule": "noon"}
    assert any("sleep_schedule" in p for p in validate_rater_answers(bad))
    missing = {k: v for k, v in rater(0).items() if k != "diet"}
    assert any("diet" in p for p in validate_rater_answers(missing))

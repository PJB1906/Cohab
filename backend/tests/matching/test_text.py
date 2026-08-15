"""TfidfSimilarity — COHAB_MATCHING_SPEC.md §7."""

import pytest

from cohab.services.matching.text import (
    NeutralTextSimilarity,
    TextSimilarity,
    TfidfSimilarity,
)

CORPUS = [
    "Working on my thesis and keeping a quiet predictable routine.",
    "Love cooking and having friends over on weekends, pretty social.",
    "Quiet person who mostly keeps to themselves and reads a lot.",
    None,  # empty notes are ignored during fit
]


def _fitted() -> TfidfSimilarity:
    return TfidfSimilarity().fit(CORPUS)


def test_identical_text_scores_near_one() -> None:
    sim = _fitted()
    assert sim.similarity(CORPUS[0], CORPUS[0]) == pytest.approx(1.0)


def test_disjoint_text_scores_low() -> None:
    sim = _fitted()
    score = sim.similarity(CORPUS[0], CORPUS[1])
    assert score < 0.3


def test_related_text_scores_higher_than_disjoint() -> None:
    sim = _fitted()
    related = sim.similarity(CORPUS[0], CORPUS[2])  # both "quiet routine"
    disjoint = sim.similarity(CORPUS[1], CORPUS[2])
    assert related > disjoint


def test_empty_text_scores_neutral() -> None:
    sim = _fitted()
    assert sim.similarity(None, CORPUS[0]) == 0.5
    assert sim.similarity(CORPUS[0], "   ") == 0.5
    assert sim.similarity("", "") == 0.5


def test_unfitted_raises_when_both_nonempty() -> None:
    sim = TfidfSimilarity()
    with pytest.raises(RuntimeError):
        sim.similarity("some text", "other text")


def test_empty_corpus_leaves_only_neutral_path() -> None:
    sim = TfidfSimilarity().fit([None, "", "  "])
    # No fitted vocabulary; the only reachable path is the neutral one.
    assert sim.similarity(None, "x") == 0.5


def test_neutral_similarity_and_protocol() -> None:
    neutral = NeutralTextSimilarity()
    assert neutral.similarity("a", "b") == 0.5
    assert isinstance(neutral, TextSimilarity)
    assert isinstance(_fitted(), TextSimilarity)

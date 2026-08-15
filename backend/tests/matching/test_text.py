"""TfidfSimilarity and EmbeddingSimilarity — COHAB_MATCHING_SPEC.md §7."""

import pytest

from cohab.services.matching.text import (
    EmbeddingSimilarity,
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


# --- EmbeddingSimilarity -----------------------------------------------
# A fake encoder is injected so these tests never load the real
# all-MiniLM-L6-v2 model (no network dependency, no torch import at test
# time) — only the cosine/neutral/clamping behaviour is under test here.

QUIET_ROUTINE = "quiet routine"
QUIET_READING = "quiet reading"
COOKING_FRIENDS = "cooking friends"
OPPOSITE_OF_QUIET = "opposite of quiet routine"

_FAKE_VECTORS = {
    QUIET_ROUTINE: [1.0, 0.0],
    QUIET_READING: [0.9, 0.1],       # close to QUIET_ROUTINE's direction
    COOKING_FRIENDS: [0.0, 1.0],     # orthogonal to QUIET_ROUTINE
    OPPOSITE_OF_QUIET: [-1.0, 0.0],  # anti-parallel to QUIET_ROUTINE
}


class _FakeEncoder:
    def encode(self, texts: list[str]) -> list[list[float]]:
        return [_FAKE_VECTORS[t] for t in texts]


def _embedding() -> EmbeddingSimilarity:
    return EmbeddingSimilarity(model=_FakeEncoder())


def test_embedding_identical_text_scores_near_one() -> None:
    sim = _embedding()
    assert sim.similarity(QUIET_ROUTINE, QUIET_ROUTINE) == pytest.approx(1.0)


def test_embedding_orthogonal_text_scores_near_zero() -> None:
    sim = _embedding()
    assert sim.similarity(QUIET_ROUTINE, COOKING_FRIENDS) == pytest.approx(0.0)


def test_embedding_related_text_scores_higher_than_disjoint() -> None:
    sim = _embedding()
    related = sim.similarity(QUIET_ROUTINE, QUIET_READING)
    disjoint = sim.similarity(QUIET_ROUTINE, COOKING_FRIENDS)
    assert related > disjoint


def test_embedding_negative_cosine_clamps_to_zero() -> None:
    # Unlike TF-IDF's non-negative vectors, embedding cosine can go negative;
    # the protocol promises [0, 1], so anti-parallel vectors clamp to 0
    # rather than passing a negative score through.
    sim = _embedding()
    assert sim.similarity(QUIET_ROUTINE, OPPOSITE_OF_QUIET) == pytest.approx(0.0)


def test_embedding_empty_text_scores_neutral_without_a_model() -> None:
    # No model injected at all — proves the empty-text path never touches
    # the encoder (and so never lazily loads the real model).
    sim = EmbeddingSimilarity()
    assert sim.similarity(None, QUIET_ROUTINE) == 0.5
    assert sim.similarity(QUIET_ROUTINE, "   ") == 0.5
    assert sim.similarity("", "") == 0.5


def test_embedding_protocol() -> None:
    assert isinstance(_embedding(), TextSimilarity)

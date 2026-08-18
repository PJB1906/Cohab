"""The `_notes` scorer's cached-vector path — Phase 4, D-3.4/D-4.x.

`_notes` prefers cosine over the two candidates' cached `text_vector`s
(populated at profile save) over re-transforming raw `lifestyle_notes`
through the live `TextSimilarity` collaborator, per CLAUDE.md's "never encode
inside the match request path."
"""

from cohab.services.matching.attributes import ATTRIBUTES
from cohab.services.matching.matrices import vector_cosine_similarity
from cohab.services.matching.scoring import ScoringContext
from cohab.services.matching.text import NeutralTextSimilarity, TextSimilarity
from tests.matching.fixtures import make_candidate

NOTES_ATTR = ATTRIBUTES["lifestyle_notes"]


class _ExplodingTextSimilarity:
    """Raises if ever called — proves the cached path never falls through to
    a live text-similarity transform when a cache is present."""

    def similarity(self, a, b) -> float:
        raise AssertionError("similarity() should not be called when both sides are cached")


def test_uses_cached_vectors_when_both_present() -> None:
    a = make_candidate(1, text_vector=[1.0, 0.0], text_vector_kind="tfidf")
    b = make_candidate(2, text_vector=[1.0, 0.0], text_vector_kind="tfidf")
    ctx = ScoringContext(text_similarity=_ExplodingTextSimilarity())

    sim_a, sim_b = NOTES_ATTR.score(a, b, ctx)

    expected = vector_cosine_similarity([1.0, 0.0], [1.0, 0.0])
    assert sim_a == sim_b == expected == 1.0


def test_falls_back_to_raw_text_when_one_side_uncached() -> None:
    a = make_candidate(1, text_vector=[1.0, 0.0], text_vector_kind="tfidf",
                        answers={"lifestyle_notes": "quiet and tidy"})
    b = make_candidate(2, text_vector=None, text_vector_kind=None,
                        answers={"lifestyle_notes": "quiet and tidy"})
    ctx = ScoringContext(text_similarity=NeutralTextSimilarity())

    sim_a, sim_b = NOTES_ATTR.score(a, b, ctx)

    assert sim_a == sim_b == 0.5  # NeutralTextSimilarity's constant


def test_falls_back_when_vector_kinds_differ() -> None:
    a = make_candidate(1, text_vector=[1.0, 0.0], text_vector_kind="tfidf")
    b = make_candidate(2, text_vector=[1.0, 0.0], text_vector_kind="embedding")
    ctx = ScoringContext(text_similarity=NeutralTextSimilarity())

    sim_a, sim_b = NOTES_ATTR.score(a, b, ctx)

    assert sim_a == sim_b == 0.5


def test_protocol_still_satisfied() -> None:
    assert isinstance(NeutralTextSimilarity(), TextSimilarity)

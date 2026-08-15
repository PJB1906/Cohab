"""Text similarity behind an interface — COHAB_MATCHING_SPEC.md §7, CLAUDE.md.

`TfidfSimilarity` ships in Phase 2 (build plan §2). `EmbeddingSimilarity`
(all-MiniLM-L6-v2) is deferred to Phase 3, swapped in behind the same protocol.

The vectorizer is fit over a corpus **once** (offline, e.g. in report.py or, in
production, when profiles are saved). Cosine similarity is then a cheap lookup —
the spec forbids encoding inside the match request path. An empty note on either
side scores a neutral 0.5 rather than a mismatch (spec §7).
"""

from __future__ import annotations

from typing import Protocol, Sequence, runtime_checkable

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from cohab.services.matching.matrices import TEXT_NEUTRAL


@runtime_checkable
class TextSimilarity(Protocol):
    """Compares two free-text lifestyle notes, returning a score in [0, 1]."""

    def similarity(self, a: str | None, b: str | None) -> float: ...


class NeutralTextSimilarity:
    """Always returns the neutral score. The default when no text model is wired
    (e.g. pure scoring unit tests, or a pool with no cached vectors)."""

    def similarity(self, a: str | None, b: str | None) -> float:
        return TEXT_NEUTRAL


def _is_empty(text: str | None) -> bool:
    return not text or not text.strip()


class TfidfSimilarity:
    """Cosine over TF-IDF vectors of `lifestyle_notes` (spec §7)."""

    def __init__(self) -> None:
        self._vectorizer: TfidfVectorizer | None = None

    def fit(self, corpus: Sequence[str | None]) -> "TfidfSimilarity":
        """Fit the vectorizer on the non-empty notes in the pool."""
        docs = [t for t in corpus if not _is_empty(t)]
        if docs:
            self._vectorizer = TfidfVectorizer()
            self._vectorizer.fit(docs)
        else:
            self._vectorizer = None  # nothing to compare against
        return self

    def similarity(self, a: str | None, b: str | None) -> float:
        # spec §7: neutral when either side is empty.
        if _is_empty(a) or _is_empty(b):
            return TEXT_NEUTRAL
        if self._vectorizer is None:
            raise RuntimeError("TfidfSimilarity.fit() must be called before similarity()")
        vecs = self._vectorizer.transform([a, b])
        score = float(cosine_similarity(vecs[0], vecs[1])[0, 0])
        # TF-IDF vectors are non-negative, so cosine is already in [0, 1]; clamp
        # defensively against floating-point drift.
        return max(0.0, min(1.0, score))

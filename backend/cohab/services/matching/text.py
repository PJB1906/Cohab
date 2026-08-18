"""Text similarity behind an interface — COHAB_MATCHING_SPEC.md §7, CLAUDE.md.

`TfidfSimilarity` shipped in Phase 2 (build plan §2). `EmbeddingSimilarity`
(all-MiniLM-L6-v2, spec §7 / PRD §15) is Phase 3's swap-in behind the same
protocol, compared against TF-IDF rather than replacing it (PRD §7: "both are
in v1... the comparison between them becomes a reportable result").

TF-IDF's vectorizer is fit over a corpus **once** (offline, e.g. in report.py
or, in production, when profiles are saved); the embedding model needs no
fitting — it's pretrained transfer learning, used as-is (PRD §15). Cosine
similarity is then a cheap lookup either way — the spec forbids encoding
inside the match request path. An empty note on either side scores a neutral
0.5 rather than a mismatch (spec §7).
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
            # Nothing was fit — a fresh, near-empty database (e.g. the first
            # few registrations of a pilot) rather than a caller error. Degrade
            # to neutral instead of raising; there is no vocabulary to compare
            # against yet.
            return TEXT_NEUTRAL
        vecs = self._vectorizer.transform([a, b])
        score = float(cosine_similarity(vecs[0], vecs[1])[0, 0])
        # TF-IDF vectors are non-negative, so cosine is already in [0, 1]; clamp
        # defensively against floating-point drift.
        return max(0.0, min(1.0, score))

    def encode(self, text: str | None) -> list[float] | None:
        """Transform-only (no fit) — the cache-at-save path (CLAUDE.md, spec
        §7). None when there's no text or nothing was ever fit; the caller
        stores that as "no cached vector" rather than a zero vector."""
        if _is_empty(text) or self._vectorizer is None:
            return None
        return self._vectorizer.transform([text]).toarray()[0].tolist()


class EmbeddingSimilarity:
    """Cosine over dense sentence embeddings of `lifestyle_notes` (spec §7,
    PRD §15): `all-MiniLM-L6-v2`, 384-d, transfer learning — used as
    published, no fine-tuning or corpus fitting needed.

    The model is loaded lazily (only on first real `similarity()` call) so
    importing this module never pulls in torch, and an already-loaded model
    can be injected — tests use this to avoid a network/model download.
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self, model: object | None = None) -> None:
        self._model = model

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.MODEL_NAME)
        return self._model

    def similarity(self, a: str | None, b: str | None) -> float:
        # spec §7: neutral when either side is empty.
        if _is_empty(a) or _is_empty(b):
            return TEXT_NEUTRAL
        vec_a, vec_b = self._get_model().encode([a, b])
        score = float(cosine_similarity([vec_a], [vec_b])[0, 0])
        # Unlike TF-IDF, embedding cosine can be negative; the protocol
        # promises a score in [0, 1], so clamp rather than pass a negative
        # value through as a "worse than opposite" similarity.
        return max(0.0, min(1.0, score))

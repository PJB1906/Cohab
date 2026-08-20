"""Ranking metrics — precision@k and NDCG@10 (PRD §15 "Evaluation — v1").

Pure functions over an already-ranked list of ids/relevances; no DB, no
`Candidate` dependency. The only caller in this codebase is Phase 9's
recovery experiment (`recovery.py`, driven by `evaluation.py`): PRD §6.6
forbids treating a synthetic-data performance figure computed against real
interaction outcomes ("pursued") as evidence the matching works, so there is
no other legitimate source of "relevance" to score against — see
docs/DECISIONS.md's Phase 9 section, D-9.1.
"""

from __future__ import annotations

import math
from typing import Hashable, Sequence


def precision_at_k(ranked_ids: Sequence[Hashable], relevant_ids: set, k: int) -> float:
    """Fraction of the top-k ranked ids that are in `relevant_ids`.

    Divides by the number of ids actually available in the top slice (never
    more than `k`), so a ranking shorter than `k` isn't penalised for the
    ranker's incompleteness rather than its ordering.
    """
    if k <= 0:
        return 0.0
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for i in top_k if i in relevant_ids)
    return hits / len(top_k)


def ndcg_at_k(ranked_relevances: Sequence[float], k: int) -> float:
    """Normalised discounted cumulative gain.

    `ranked_relevances` is the full set of relevance grades, already ordered
    the way the ranking under test placed them. IDCG re-sorts that same
    multiset of grades descending — the best ordering achievable for exactly
    these items — so NDCG never exceeds 1.0.
    """
    if k <= 0:
        return 0.0
    top_k = list(ranked_relevances[:k])
    if not top_k:
        return 0.0

    def _dcg(relevances: list[float]) -> float:
        return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))

    dcg = _dcg(top_k)
    idcg = _dcg(sorted(ranked_relevances, reverse=True)[:k])
    if idcg == 0:
        return 0.0
    return dcg / idcg

"""Directional per-attribute scores from a rater to a card.

The study's features are exactly the matcher's own per-attribute scores
S_k(rater -> card), read off the same tables `vectorised.py` builds from
`matrices.py`. Nothing here defines a new similarity.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from cohab.services.matching.vectorised import TABLE_ATTRS
from cohab.services.study.instrument import STUDY_ATTRIBUTES

_INDEX = {
    name: (
        {v: i for i, v in enumerate(TABLE_ATTRS[name].rows)},
        {v: i for i, v in enumerate(TABLE_ATTRS[name].cols)},
    )
    for name in STUDY_ATTRIBUTES
}


def attribute_score(name: str, rater: Mapping[str, str], card: Mapping[str, str]) -> float:
    spec = TABLE_ATTRS[name]
    rows, cols = _INDEX[name]
    return float(spec.table[rows[rater[spec.pref_field]], cols[card[spec.behav_field]]])


def card_vector(rater: Mapping[str, str], card: Mapping[str, str]) -> np.ndarray:
    """17-vector of S_k(rater -> card), in STUDY_ATTRIBUTES order."""
    return np.array([attribute_score(n, rater, card) for n in STUDY_ATTRIBUTES])


def weighted_score(rater: Mapping[str, str], card: Mapping[str, str], weights: Mapping[str, float]) -> float:
    """S(rater -> card) under `weights` restricted to the study attributes and
    renormalised, i.e. what the matcher would compute with budget, interests
    and notes held equal."""
    w = np.array([weights.get(n, 0.0) for n in STUDY_ATTRIBUTES])
    total = w.sum()
    if total <= 0:
        return 0.0
    return float(card_vector(rater, card) @ (w / total))

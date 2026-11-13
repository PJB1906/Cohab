"""Moving between the 17 study attributes and a full 20-attribute weight set."""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from cohab.seed import DEFAULT_WEIGHTS
from cohab.services.study.instrument import HELD_OUT_ATTRIBUTES, STUDY_ATTRIBUTES

EXPERT = dict(DEFAULT_WEIGHTS)


def study_vector(weights: Mapping[str, float]) -> np.ndarray:
    """The 17 study-attribute weights, renormalised to sum to 1."""
    w = np.array([weights.get(n, 0.0) for n in STUDY_ATTRIBUTES], dtype=np.float64)
    return w / w.sum()


EXPERT_STUDY = study_vector(EXPERT)
HELD_OUT_MASS = sum(EXPERT[h] for h in HELD_OUT_ATTRIBUTES)


def full_weight_set(study_weights: Sequence[float], held_out_from: Mapping[str, float] = EXPERT) -> dict[str, float]:
    """A complete, publishable weight dict: the learned 17 scaled to fill
    (1 - held-out mass), and budget / interests / notes kept at their
    expert values, which the study cannot inform (docs/DECISIONS.md D-14.6)."""
    w = np.asarray(study_weights, dtype=np.float64)
    w = w / w.sum()
    held = {h: float(held_out_from[h]) for h in HELD_OUT_ATTRIBUTES}
    scale = 1.0 - sum(held.values())
    out = {n: float(scale * w[k]) for k, n in enumerate(STUDY_ATTRIBUTES)}
    out.update(held)
    # Absorb float rounding so the set passes weight_sets.publish's sum check.
    drift = 1.0 - sum(out.values())
    out[STUDY_ATTRIBUTES[int(np.argmax(w))]] += drift
    return out

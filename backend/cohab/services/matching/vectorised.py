"""Vectorised Stage 1 + Stage 2 over a whole population (Cohab v2 plan W5).

`CompatibilityMatcher.score()` is the reference implementation: one pair at a
time, readable, and the thing the spec is checked against. It is far too slow
for the v2 analyses, which score every pair of 1,000-agent populations
hundreds of times (simulation, bootstrap rank stability, power analysis).

This module computes the same numbers for all N x N pairs at once. Each
categorical attribute becomes an integer-coded answer per person and a small
lookup table, so `S_k[i, j] = table[pref_code[i], behav_code[j]]` is one NumPy
fancy-index. Per-pair renormalisation over present attributes (spec §8) is
done by accumulating a numerator and denominator per attribute.

Nothing here is a second definition of the matcher: every table is built from
`matrices.py`, and `tests/matching/test_vectorised.py` checks the output is
equal to the reference matcher, pair by pair, on generated populations.

Conventions: index i is the subject (A), j the candidate (B).
`score[i, j]` is S(i -> j) under i's weights; `combined = HM(score, score.T)`.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.eligibility import Reason
from cohab.services.matching.matrices import (
    BUDGET_SPREAD,
    INTERESTS_EMPTY_FLOOR,
    MOVE_IN_TOLERANCE_DAYS,
    ORDINAL_ORDERS,
    PAYMENT_RELIABILITY,
    SIMILARITY_MATRICES,
    TEXT_NEUTRAL,
    TOLERANCE_MATRICES,
    ordinal_similarity,
)
from cohab.services.matching.scoring import IMPORTANCE_MULTIPLIER

# ---------------------------------------------------------------------------
# Attribute table specs, mirroring attributes._ATTRIBUTE_LIST exactly.
# (name, pref_field, behav_field, rows, cols, table)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TableAttr:
    name: str
    pref_field: str
    behav_field: str
    rows: tuple[str, ...]
    cols: tuple[str, ...]
    table: np.ndarray  # shape (len(rows), len(cols))
    fields: tuple[str, ...]  # presence check, as attributes.Attribute.fields


def _matrix_table(m: Mapping[str, Mapping[str, float]]) -> tuple[tuple[str, ...], tuple[str, ...], np.ndarray]:
    rows = tuple(m.keys())
    cols = tuple(next(iter(m.values())).keys())
    t = np.array([[m[r][c] for c in cols] for r in rows], dtype=np.float64)
    return rows, cols, t


def _sim(name: str, matrix: str | None = None) -> TableAttr:
    rows, cols, t = _matrix_table(SIMILARITY_MATRICES[matrix or name])
    return TableAttr(name, name, name, rows, cols, t, (name,))


def _ord(name: str) -> TableAttr:
    order = ORDINAL_ORDERS[name]
    t = np.array([[ordinal_similarity(order, a, b) for b in order] for a in order])
    return TableAttr(name, name, name, order, order, t, (name,))


def _tol(name: str, matrix: str, pref: str, behav: str) -> TableAttr:
    rows, cols, t = _matrix_table(TOLERANCE_MATRICES[matrix])
    fields = (pref, behav) if pref != behav else (pref,)
    return TableAttr(name, pref, behav, rows, cols, t, fields)


def _absolute(name: str) -> TableAttr:
    keys = tuple(PAYMENT_RELIABILITY.keys())
    t = np.array([[PAYMENT_RELIABILITY[c] for c in keys] for _ in keys])
    return TableAttr(name, name, name, keys, keys, t, (name,))


TABLE_ATTRS: dict[str, TableAttr] = {
    a.name: a
    for a in [
        _sim("cleanliness_level"),
        _sim("chore_approach"),
        _tol("sharing_norm", "sharing", "sharing_norm", "sharing_norm"),
        _sim("sleep_schedule"),
        _tol("noise", "noise", "noise_preference", "noise_behaviour"),
        _tol("guests", "guests", "guest_tolerance", "guest_frequency"),
        _absolute("payment_reliability"),
        _sim("cost_split_preference"),
        _sim("communication_style"),
        _sim("diet"),
        _tol("nonveg_cooking", "nonveg_cooking", "nonveg_cooking_tolerance", "diet"),
        _tol("smoking", "smoking", "smoking_tolerance", "smoking_behaviour"),
        _tol("alcohol", "alcohol", "alcohol_tolerance", "alcohol_behaviour"),
        _sim("life_stage"),
        _ord("daytime_presence"),
        _ord("home_orientation"),
        _sim("sociability"),
    ]
}
SPECIAL_ATTRS = ("budget_proximity", "interests", "lifestyle_notes")
ALL_ATTRS: tuple[str, ...] = (
    "cleanliness_level", "chore_approach", "sharing_norm", "sleep_schedule", "noise", "guests",
    "payment_reliability", "cost_split_preference", "communication_style", "budget_proximity",
    "diet", "nonveg_cooking", "smoking", "alcohol", "life_stage", "daytime_presence",
    "home_orientation", "sociability", "interests", "lifestyle_notes",
)  # canonical order = attributes._ATTRIBUTE_LIST

# Stage 1 reason codes in evaluation order (eligibility.passes_hard_constraints).
REASON_ORDER: tuple[str, ...] = (
    Reason.NOT_VERIFIED_OR_ACTIVE,
    Reason.BOTH_HAVE_PLACE,
    Reason.DIFFERENT_CITY,
    Reason.BUDGET_NO_OVERLAP,
    Reason.MOVE_IN_TOO_FAR,
    Reason.GENDER_PREFERENCE,
    Reason.SEVERE_ALLERGY,
    Reason.PET_CONFLICT,
    Reason.SMOKING_DEALBREAKER,
    Reason.BLOCKED,
    Reason.ALREADY_DECIDED,
)
ELIGIBLE = -1
SELF = -2


def _codes(values: Sequence[str | None], vocab: Sequence[str], field_name: str) -> np.ndarray:
    index = {v: i for i, v in enumerate(vocab)}
    out = np.full(len(values), -1, dtype=np.int64)
    for k, v in enumerate(values):
        if v is None:
            continue
        if v not in index:
            raise KeyError(f"{field_name}: unknown answer {v!r}")
        out[k] = index[v]
    return out


def _bitmask(sets: Sequence[Iterable[str]]) -> np.ndarray:
    vocab: dict[str, int] = {}
    out = np.zeros(len(sets), dtype=np.int64)
    for k, s in enumerate(sets):
        for item in s:
            bit = vocab.setdefault(item, len(vocab))
            if bit >= 63:
                raise ValueError("more than 63 distinct allergens")
            out[k] |= 1 << bit
    return out


@dataclass
class Population:
    """Column-oriented view of a list of Candidates."""

    ids: list[uuid.UUID]
    answers: dict[str, list]  # questionnaire key -> per-person answer (or None)
    budget_min: np.ndarray
    budget_max: np.ndarray
    interests: np.ndarray  # N x T bool
    has_interests: np.ndarray  # N bool
    text: np.ndarray | None  # N x D, unit-normalised rows; None => neutral for all
    has_text: np.ndarray  # N bool
    important: list[frozenset[str]]
    # Stage 1
    verified_active: np.ndarray
    has_place: np.ndarray
    city: np.ndarray
    move_in_days: np.ndarray
    gender: np.ndarray
    gender_pref: np.ndarray
    severe_allergy: np.ndarray
    kitchen_allergens: np.ndarray
    has_pet: np.ndarray
    no_pets: np.ndarray
    smokes_indoors: np.ndarray
    smoking_dealbreaker: np.ndarray
    blocked_pairs: set[frozenset[uuid.UUID]] = field(default_factory=set)
    settled_pairs: set[frozenset[uuid.UUID]] = field(default_factory=set)

    @property
    def n(self) -> int:
        return len(self.ids)

    @classmethod
    def from_candidates(
        cls,
        candidates: Sequence[Candidate],
        *,
        use_text_vectors: bool = True,
        blocked_pairs: Iterable[frozenset[uuid.UUID]] = (),
        settled_pairs: Iterable[frozenset[uuid.UUID]] = (),
    ) -> "Population":
        keys = sorted({k for c in candidates for k in c.questionnaire})
        answers = {k: [c.questionnaire.get(k) for c in candidates] for k in keys}
        tags = sorted({t for c in candidates for t in (c.questionnaire.get("interests") or [])})
        tag_ix = {t: i for i, t in enumerate(tags)}
        interests = np.zeros((len(candidates), max(len(tags), 1)), dtype=bool)
        for i, c in enumerate(candidates):
            for t in c.questionnaire.get("interests") or []:
                interests[i, tag_ix[t]] = True

        text = None
        has_text = np.zeros(len(candidates), dtype=bool)
        if use_text_vectors:
            kinds = {c.text_vector_kind for c in candidates if c.text_vector is not None}
            lengths = {len(c.text_vector) for c in candidates if c.text_vector is not None}
            if len(kinds) == 1 and len(lengths) == 1:
                d = lengths.pop()
                text = np.zeros((len(candidates), d))
                for i, c in enumerate(candidates):
                    if c.text_vector is not None:
                        v = np.asarray(c.text_vector, dtype=np.float64)
                        norm = np.linalg.norm(v)
                        if norm > 0:
                            text[i] = v / norm
                            has_text[i] = True
        epoch = min(c.move_in_date for c in candidates).toordinal() if candidates else 0
        return cls(
            ids=[c.user_id for c in candidates],
            answers=answers,
            budget_min=np.array([c.budget_min for c in candidates], dtype=np.float64),
            budget_max=np.array([c.budget_max for c in candidates], dtype=np.float64),
            interests=interests,
            has_interests=interests.any(axis=1),
            text=text,
            has_text=has_text,
            important=[frozenset(c.important_attributes) for c in candidates],
            verified_active=np.array(
                [c.verification_status == "verified" and c.account_status == "active" for c in candidates]
            ),
            has_place=np.array([c.seeker_type == "has_place" for c in candidates]),
            city=np.array([c.city for c in candidates], dtype=object),
            move_in_days=np.array([c.move_in_date.toordinal() - epoch for c in candidates]),
            gender=np.array([c.gender for c in candidates], dtype=object),
            gender_pref=np.array([c.gender_preference for c in candidates], dtype=object),
            severe_allergy=_bitmask([c.severe_allergy for c in candidates] + [c.kitchen_allergens for c in candidates])[
                : len(candidates)
            ],
            kitchen_allergens=_bitmask([c.severe_allergy for c in candidates] + [c.kitchen_allergens for c in candidates])[
                len(candidates) :
            ],
            has_pet=np.array([c.has_pet for c in candidates]),
            no_pets=np.array([c.pet_tolerance == "cannot_live_with_pets" for c in candidates]),
            smokes_indoors=np.array([c.questionnaire.get("smoking_behaviour") == "indoors" for c in candidates]),
            smoking_dealbreaker=np.array([c.smoking_dealbreaker for c in candidates]),
            blocked_pairs=set(blocked_pairs),
            settled_pairs=set(settled_pairs),
        )

    def answer_codes(self, field_name: str, vocab: Sequence[str]) -> np.ndarray:
        return _codes(self.answers.get(field_name, [None] * self.n), vocab, field_name)


# ---------------------------------------------------------------------------
# Stage 2
# ---------------------------------------------------------------------------


@dataclass
class AttributeMatrices:
    """Per-attribute directional similarity and presence for all pairs.

    `sim[name][i, j]` is what i experiences of j (sim_a with a=i, b=j);
    `present[name]` is None for never-dropped attributes, else an N-vector
    (presence is "both answered", so the pair mask is outer(p, p))."""

    names: tuple[str, ...]
    sim: dict[str, np.ndarray]
    present: dict[str, np.ndarray | None]


def attribute_matrices(pop: Population, names: Iterable[str] = ALL_ATTRS) -> AttributeMatrices:
    names = tuple(names)
    sim: dict[str, np.ndarray] = {}
    present: dict[str, np.ndarray | None] = {}
    for name in names:
        if name in TABLE_ATTRS:
            spec = TABLE_ATTRS[name]
            pref = pop.answer_codes(spec.pref_field, spec.rows)
            behav = pop.answer_codes(spec.behav_field, spec.cols)
            p = np.ones(pop.n, dtype=bool)
            for f in spec.fields:
                vocab = spec.rows if f == spec.pref_field else spec.cols
                p &= pop.answer_codes(f, vocab) >= 0
            # Missing codes index row/col -1; masked out by presence below.
            sim[name] = spec.table[pref[:, None], behav[None, :]]
            present[name] = p
        elif name == "budget_proximity":
            mid = (pop.budget_min + pop.budget_max) / 2
            sim[name] = np.maximum(0.0, 1.0 - np.abs(mid[:, None] - mid[None, :]) / BUDGET_SPREAD)
            present[name] = None
        elif name == "interests":
            x = pop.interests.astype(np.float64)
            inter = x @ x.T
            counts = x.sum(axis=1)
            union = counts[:, None] + counts[None, :] - inter
            with np.errstate(invalid="ignore", divide="ignore"):
                j = np.where(union > 0, inter / union, 0.0)
            both = pop.has_interests[:, None] & pop.has_interests[None, :]
            sim[name] = np.where(both, j, INTERESTS_EMPTY_FLOOR)
            present[name] = None
        elif name == "lifestyle_notes":
            if pop.text is None:
                sim[name] = np.full((pop.n, pop.n), TEXT_NEUTRAL)
            else:
                cos = np.clip(pop.text @ pop.text.T, 0.0, 1.0)
                both = pop.has_text[:, None] & pop.has_text[None, :]
                sim[name] = np.where(both, cos, TEXT_NEUTRAL)
            present[name] = None
        else:
            raise KeyError(name)
    return AttributeMatrices(names, sim, present)


def blended_weights(pop: Population, default_weights: Mapping[str, float], names: Sequence[str]) -> np.ndarray:
    """N x K matrix: each person's blended (spec §9) weight per attribute in
    `names`, *before* per-pair restriction to present attributes. Mirrors
    `scoring.blend` exactly, including its degenerate-case fallback."""
    base = np.array([default_weights.get(n, 0.0) for n in names], dtype=np.float64)
    out = np.tile(base, (pop.n, 1))
    for i, imp in enumerate(pop.important):
        if not imp:
            continue
        sel = np.array([n in imp for n in names])
        boosted = np.where(sel, base * IMPORTANCE_MULTIPLIER, base)
        selected_sum = boosted[sel].sum()
        rest_sum = boosted[~sel].sum()
        if rest_sum <= 0 or selected_sum >= 1:
            total = boosted.sum() or 1.0
            out[i] = boosted / total
        else:
            out[i] = np.where(sel, boosted, boosted * (1 - selected_sum) / rest_sum)
    return out


@dataclass
class ScoreMatrices:
    score: np.ndarray  # S(i -> j)
    combined: np.ndarray  # harmonic mean, symmetric

    def harmonic(self) -> np.ndarray:
        return self.combined


def directional_scores(
    am: AttributeMatrices,
    weights: np.ndarray,
) -> np.ndarray:
    """S[i, j] = sum_k w_ik P_kij s_kij / sum_k w_ik P_kij, where `weights` is
    N x K (per subject) or K (shared). Attributes with zero weight are
    skipped, matching the reference matcher (it only iterates weighted
    attributes)."""
    names = am.names
    n = next(iter(am.sim.values())).shape[0]
    w = np.broadcast_to(np.atleast_2d(weights), (n, len(names)))
    num = np.zeros((n, n))
    den = np.zeros((n, n))
    for k, name in enumerate(names):
        wk = w[:, k]
        if not np.any(wk):
            continue
        p = am.present[name]
        if p is None:
            contrib_w = np.broadcast_to(wk[:, None], (n, n))
        else:
            contrib_w = wk[:, None] * (p[:, None] & p[None, :])
        num += contrib_w * am.sim[name]
        den += contrib_w
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, 0.0)


def harmonic(score: np.ndarray) -> np.ndarray:
    s, t = score, score.T
    total = s + t
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(total > 0, 2 * s * t / total, 0.0)


def score_population(
    pop: Population,
    default_weights: Mapping[str, float],
    am: AttributeMatrices | None = None,
) -> ScoreMatrices:
    names = tuple(n for n in ALL_ATTRS if n in default_weights)
    am = am or attribute_matrices(pop, names)
    w = blended_weights(pop, default_weights, am.names)
    s = directional_scores(am, w)
    return ScoreMatrices(score=s, combined=harmonic(s))


# ---------------------------------------------------------------------------
# Stage 1
# ---------------------------------------------------------------------------


def eligibility_reasons(pop: Population, tolerance_days: int = MOVE_IN_TOLERANCE_DAYS) -> np.ndarray:
    """N x N int matrix: ELIGIBLE, SELF, or the index into REASON_ORDER of
    the first failing hard constraint, in `passes_hard_constraints` order."""
    n = pop.n
    checks = [
        np.broadcast_to(~pop.verified_active[None, :], (n, n)),
        pop.has_place[:, None] & pop.has_place[None, :],
        pop.city[:, None] != pop.city[None, :],
        (pop.budget_max[:, None] < pop.budget_min[None, :]) | (pop.budget_max[None, :] < pop.budget_min[:, None]),
        np.abs(pop.move_in_days[:, None] - pop.move_in_days[None, :]) > tolerance_days,
        ~(
            ((pop.gender_pref[:, None] == "any") | (pop.gender_pref[:, None] == pop.gender[None, :]))
            & ((pop.gender_pref[None, :] == "any") | (pop.gender_pref[None, :] == pop.gender[:, None]))
        ),
        ((pop.severe_allergy[:, None] & pop.kitchen_allergens[None, :]) != 0)
        | ((pop.severe_allergy[None, :] & pop.kitchen_allergens[:, None]) != 0),
        (pop.has_pet[None, :] & pop.no_pets[:, None]) | (pop.has_pet[:, None] & pop.no_pets[None, :]),
        (pop.smokes_indoors[None, :] & pop.smoking_dealbreaker[:, None])
        | (pop.smokes_indoors[:, None] & pop.smoking_dealbreaker[None, :]),
    ]
    index = {uid: i for i, uid in enumerate(pop.ids)}
    for pairs in (pop.blocked_pairs, pop.settled_pairs):
        m = np.zeros((n, n), dtype=bool)
        for pair in pairs:
            a, b = tuple(pair)
            if a in index and b in index:
                m[index[a], index[b]] = m[index[b], index[a]] = True
        checks.append(m)

    reasons = np.full((n, n), ELIGIBLE, dtype=np.int64)
    for code in range(len(checks) - 1, -1, -1):  # last-to-first so the first failure wins
        reasons[checks[code]] = code
    np.fill_diagonal(reasons, SELF)
    return reasons


def eligible_mask(pop: Population, tolerance_days: int = MOVE_IN_TOLERANCE_DAYS) -> np.ndarray:
    return eligibility_reasons(pop, tolerance_days) == ELIGIBLE


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_for(
    i: int,
    sm: ScoreMatrices,
    eligible: np.ndarray,
    ids: Sequence[uuid.UUID],
    k: int | None = None,
) -> list[int]:
    """Indices of i's eligible candidates in MatchRanker order: combined desc,
    then the higher of the smaller directional score, then user_id asc."""
    cand = np.flatnonzero(eligible[i])
    if cand.size == 0:
        return []
    lesser = np.minimum(sm.score[i, cand], sm.score[cand, i])
    order = sorted(
        range(cand.size),
        key=lambda t: (-sm.combined[i, cand[t]], -lesser[t], ids[cand[t]]),
    )
    out = [int(cand[t]) for t in order]
    return out[:k] if k is not None else out


def top_k_fast(i: int, combined: np.ndarray, eligible: np.ndarray, k: int) -> np.ndarray:
    """Top-k by combined score only (no tie-break), for simulation inner loops
    where exact tie order is irrelevant and speed matters."""
    row = np.where(eligible[i], combined[i], -np.inf)
    m = int(eligible[i].sum())
    k = min(k, m)
    if k <= 0:
        return np.array([], dtype=np.int64)
    idx = np.argpartition(-row, k - 1)[:k]
    return idx[np.argsort(-row[idx], kind="stable")]

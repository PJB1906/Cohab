"""Taste learning: each member's ranking adapts to their own decisions.

The matcher scores S(you -> them) with weights you *stated* (the platform
expert weights, boosted on your "top 3"). What people say they want and what
they actually pick differ; this module learns the difference from the
decisions the v2 event log already records.

Model (per member, refit after every decision):

    P(you express interest in c) = sigmoid(b + sum_k beta_k * s_k(you -> c))

- s_k(you -> c) is the matcher's own per-attribute score, read from the
  match row's stored breakdown, i.e. exactly what you were shown.
- beta_k >= 0, so no attribute can ever reward a conflict.
- A Gaussian prior centres beta on TAU * your stated weights. With few
  decisions the fit *is* your stated weights; each decision moves it a
  little. MAP estimate by L-BFGS-B: a few milliseconds for 20 features.

Your learned weights are beta / sum(beta). They change only the order of
your own list: the score each card shows is still the platform's stored,
explainable score, the other person's side of the match is untouched, and no
weight set is modified (weight sets stay immutable, CLAUDE.md). Every list
served with learned weights is logged under its own policy name, so the
effect can be measured later.

Decisions: "interested" (or "mutual", when the other person had already
said yes) by you = positive; "rejected" by you before a chat opened =
negative. Rejections after chatting are about the conversation, not the
profile, so they are not used.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.services.matching.scoring import blend

TAU = 10.0  # logit scale of the prior; matches the study's fitted scale order
# Higher = slower to move away from stated weights. Chosen by simulation
# (analysis/taste_sim.py, D-14.22): at 8, top-10 overlap with a member's true
# ideal rises 0.53 -> 0.67 by ~45 decisions while only 2-5% end up worse.
PRIOR_STRENGTH = 8.0
MIN_DECISIONS = 6
MIN_EACH = 2
SHIFT_NOTE_ABS = 0.02  # a shift is worth a sentence only if both
SHIFT_NOTE_REL = 0.25  # absolute and relative change are this large
PRE_CHAT_STATES = ("suggested", "viewed", "interested", "mutual")


@dataclass(frozen=True)
class Decision:
    sims: Mapping[str, float]  # attribute -> your directional score of them
    liked: bool


@dataclass
class TasteModel:
    attributes: list[str]
    stated: dict[str, float]
    learned: dict[str, float]
    positives: int
    negatives: int
    active: bool
    fitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def decisions(self) -> int:
        return self.positives + self.negatives

    def shifts(self) -> dict[str, float]:
        return {a: self.learned[a] - self.stated[a] for a in self.attributes}

    def to_json(self) -> dict:
        return {
            "attributes": self.attributes,
            "stated": self.stated,
            "learned": self.learned,
            "positives": self.positives,
            "negatives": self.negatives,
            "active": self.active,
            "fitted_at": self.fitted_at,
        }

    @classmethod
    def from_json(cls, d: dict) -> "TasteModel":
        return cls(
            attributes=list(d["attributes"]),
            stated=dict(d["stated"]),
            learned=dict(d["learned"]),
            positives=int(d["positives"]),
            negatives=int(d["negatives"]),
            active=bool(d["active"]),
            fitted_at=d.get("fitted_at", ""),
        )


def stated_weights(platform: Mapping[str, float], important: frozenset[str] | set[str]) -> dict[str, float]:
    """The weights the matcher already uses for you (spec §9 blend)."""
    w = blend(dict(platform), important)
    total = sum(w.values()) or 1.0
    return {k: v / total for k, v in w.items()}


def fit_taste(decisions: Sequence[Decision], stated: Mapping[str, float]) -> TasteModel:
    attrs = [a for a in stated if stated[a] > 0]
    w0 = np.array([stated[a] for a in attrs], dtype=np.float64)
    w0 = w0 / w0.sum()
    pos = sum(1 for d in decisions if d.liked)
    neg = len(decisions) - pos
    active = len(decisions) >= MIN_DECISIONS and pos >= MIN_EACH and neg >= MIN_EACH

    if not decisions:
        return TasteModel(attrs, dict(zip(attrs, map(float, w0))), dict(zip(attrs, map(float, w0))), 0, 0, False)

    # Missing attributes (dropped because one side left them unanswered)
    # take the column mean, so they contribute nothing to differences.
    X = np.full((len(decisions), len(attrs)), np.nan)
    for i, d in enumerate(decisions):
        for j, a in enumerate(attrs):
            v = d.sims.get(a)
            if v is not None:
                X[i, j] = float(v)
    seen = (~np.isnan(X)).sum(axis=0)
    col_sum = np.where(np.isnan(X), 0.0, X).sum(axis=0)
    # An attribute no decision has a value for falls back to 0.5.
    col_mean = np.where(seen > 0, col_sum / np.maximum(seen, 1), 0.5)
    X = np.where(np.isnan(X), col_mean, X)
    y = np.array([1.0 if d.liked else 0.0 for d in decisions])

    beta0 = TAU * w0
    # Intercept starts where the prior predicts the observed like-rate.
    base = float(np.clip(y.mean(), 0.05, 0.95))
    b0 = float(np.log(base / (1 - base)) - (X @ beta0).mean())
    # Penalty sum_k (beta_k - beta0_k)^2 / (TAU^2 w0_k): in weight units this is
    # PRIOR_STRENGTH * sum_k dw_k^2 / w0_k, so a small stated weight is held
    # more tightly than a large one (variance proportional to the weight, as
    # under a Dirichlet prior).
    lam = PRIOR_STRENGTH / TAU**2
    k = len(attrs)

    def obj(theta: np.ndarray) -> tuple[float, np.ndarray]:
        beta, b = theta[:k], theta[k]
        z = X @ beta + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))
        r = p - y
        diff = beta - beta0
        f = float(np.sum(np.logaddexp(0, z) - y * z)) + lam * float(diff @ (diff * (1 / np.maximum(w0, 1e-3))))
        g_beta = X.T @ r + 2 * lam * diff / np.maximum(w0, 1e-3)
        g_b = float(r.sum())
        # Weak prior on the intercept keeps one-class data from running away.
        f += 0.01 * (b - b0) ** 2
        g_b += 0.02 * (b - b0)
        return f, np.concatenate([g_beta, [g_b]])

    res = minimize(obj, np.concatenate([beta0, [b0]]), jac=True, method="L-BFGS-B", bounds=[(0.0, None)] * k + [(None, None)])
    beta = res.x[:k]
    w = beta / beta.sum() if beta.sum() > 0 else w0
    learned = dict(zip(attrs, map(float, w)))
    return TasteModel(attrs, dict(zip(attrs, map(float, w0))), learned, pos, neg, active)


def personal_score(model: TasteModel, sims: Mapping[str, float]) -> float:
    """S(you -> them) under your learned weights, renormalised over the
    attributes present for this pair (spec §8, same rule as the matcher)."""
    num = den = 0.0
    for a, w in model.learned.items():
        v = sims.get(a)
        if v is not None:
            num += w * v
            den += w
    return num / den if den > 0 else 0.0


ATTRIBUTE_LABELS = {
    "cleanliness_level": "tidiness", "chore_approach": "chores", "sharing_norm": "sharing things",
    "sleep_schedule": "sleep schedule", "noise": "noise", "guests": "guests",
    "payment_reliability": "paying on time", "cost_split_preference": "splitting costs",
    "communication_style": "communication", "budget_proximity": "budget", "diet": "diet",
    "nonveg_cooking": "non-veg cooking", "smoking": "smoking", "alcohol": "alcohol",
    "life_stage": "life stage", "daytime_presence": "daytime routine", "home_orientation": "time at home",
    "sociability": "sociability", "interests": "shared interests", "lifestyle_notes": "how you describe yourselves",
}


def insights(model: TasteModel, limit: int = 2) -> list[dict]:
    """Plain sentences about the largest shifts, from fixed templates (the
    same rule as match explanations: no generated prose)."""
    if not model.active:
        return []
    notable = []
    for a, s in model.shifts().items():
        base = model.stated[a]
        if abs(s) >= SHIFT_NOTE_ABS and abs(s) >= SHIFT_NOTE_REL * max(base, 1e-6):
            notable.append((abs(s), a, s))
    notable.sort(reverse=True)
    out = []
    for _, a, s in notable[:limit]:
        label = ATTRIBUTE_LABELS.get(a, a.replace("_", " "))
        text = (
            f"You keep choosing people who fit you on {label}, more than your answers said."
            if s > 0
            else f"In practice {label} seems to matter less to you than you said."
        )
        out.append({"attribute": a, "direction": "up" if s > 0 else "down", "text": text})
    return out


# --- database side ---------------------------------------------------------------


def load_decisions(session: Session, user_id: uuid.UUID) -> list[Decision]:
    from cohab.models import MatchScore, MatchStateEvent

    rows = session.execute(
        select(MatchStateEvent.to_state, MatchStateEvent.from_state, MatchScore)
        .join(MatchScore, MatchScore.id == MatchStateEvent.match_score_id)
        .where(MatchStateEvent.actor_id == user_id)
        .where(MatchStateEvent.to_state.in_(("interested", "mutual", "rejected")))
        .order_by(MatchStateEvent.at)
    ).all()
    seen: dict[uuid.UUID, Decision] = {}
    for to_state, from_state, ms in rows:
        if to_state == "rejected" and from_state not in PRE_CHAT_STATES:
            continue
        side = "sim_a" if ms.user_id_a == user_id else "sim_b"
        sims = {a: v[side] for a, v in (ms.breakdown or {}).items() if isinstance(v, dict) and side in v}
        if not sims:
            continue
        # The latest decision about a person wins (interest, then a pass).
        seen[ms.id] = Decision(sims=sims, liked=to_state != "rejected")
    return list(seen.values())


def refresh(session: Session, user, platform_weights: Mapping[str, float]) -> TasteModel:
    """Refit and store this member's model. Called after each decision."""
    from cohab.models import UserTaste

    important = frozenset(w.attribute_name for w in user.attribute_weights if w.is_selected_important)
    model = fit_taste(load_decisions(session, user.id), stated_weights(platform_weights, important))
    row = session.get(UserTaste, user.id)
    if row is None:
        row = UserTaste(user_id=user.id, enabled=True)
        session.add(row)
    row.model = model.to_json()
    row.decisions = model.decisions
    row.updated_at = datetime.now(timezone.utc)
    session.flush()
    return model


def active_model(session: Session, user_id: uuid.UUID) -> TasteModel | None:
    """The model to rank with, or None (not enough decisions, or switched off)."""
    from cohab.models import UserTaste

    row = session.get(UserTaste, user_id)
    if row is None or not row.enabled or not row.model:
        return None
    model = TasteModel.from_json(row.model)
    return model if model.active else None

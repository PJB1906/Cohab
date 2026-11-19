"""Taste learning core (services/taste.py) and its simulation."""

from __future__ import annotations

import numpy as np
import pytest

from cohab.analysis import taste_sim
from cohab.analysis.weights import EXPERT
from cohab.services.taste import (
    MIN_DECISIONS,
    Decision,
    TasteModel,
    fit_taste,
    insights,
    personal_score,
    stated_weights,
)

ATTRS = ["cleanliness_level", "sleep_schedule", "guests", "budget_proximity"]
STATED = {"cleanliness_level": 0.25, "sleep_schedule": 0.25, "guests": 0.25, "budget_proximity": 0.25}


def _decisions(rng, n, true_w, scale=25.0):
    out = []
    for _ in range(n):
        sims = {a: float(rng.uniform(0.1, 1.0)) for a in ATTRS}
        u = sum(true_w[a] * sims[a] for a in ATTRS)
        out.append(Decision(sims=sims, liked=bool(rng.random() < 1 / (1 + np.exp(-scale * (u - 0.55))))))
    return out


def test_no_decisions_returns_stated_and_inactive() -> None:
    m = fit_taste([], STATED)
    assert not m.active and m.decisions == 0
    assert m.learned == pytest.approx(STATED)
    assert insights(m) == []


def test_needs_enough_of_both_kinds_to_activate() -> None:
    yes = [Decision({"cleanliness_level": 0.9}, True)] * (MIN_DECISIONS + 2)
    assert not fit_taste(yes, STATED).active  # all positives: nothing to learn from
    mixed = yes[:4] + [Decision({"cleanliness_level": 0.2}, False)] * 2
    assert fit_taste(mixed, STATED).active


def test_learns_toward_the_true_weights() -> None:
    rng = np.random.default_rng(1)
    truth = {"cleanliness_level": 0.7, "sleep_schedule": 0.1, "guests": 0.1, "budget_proximity": 0.1}
    m = fit_taste(_decisions(rng, 120, truth), STATED)
    assert m.active
    assert all(v >= 0 for v in m.learned.values())
    assert sum(m.learned.values()) == pytest.approx(1.0)
    assert m.learned["cleanliness_level"] > STATED["cleanliness_level"] + 0.05
    assert max(m.shifts(), key=m.shifts().get) == "cleanliness_level"
    notes = insights(m)
    assert notes and notes[0]["attribute"] == "cleanliness_level" and notes[0]["direction"] == "up"
    assert "tidiness" in notes[0]["text"]


def test_more_data_moves_further_from_the_prior() -> None:
    truth = {"cleanliness_level": 0.7, "sleep_schedule": 0.1, "guests": 0.1, "budget_proximity": 0.1}
    few = fit_taste(_decisions(np.random.default_rng(2), 10, truth), STATED)
    many = fit_taste(_decisions(np.random.default_rng(2), 200, truth), STATED)
    dist = lambda m: abs(m.learned["cleanliness_level"] - STATED["cleanliness_level"])  # noqa: E731
    assert dist(many) > dist(few)


def test_personal_score_renormalises_over_present_attributes() -> None:
    m = TasteModel(ATTRS, STATED, {"cleanliness_level": 0.5, "sleep_schedule": 0.5, "guests": 0, "budget_proximity": 0}, 3, 3, True)
    assert personal_score(m, {"cleanliness_level": 1.0}) == pytest.approx(1.0)
    assert personal_score(m, {"cleanliness_level": 1.0, "sleep_schedule": 0.0}) == pytest.approx(0.5)
    assert personal_score(m, {}) == 0.0


def test_stated_weights_match_the_matcher_blend() -> None:
    w = stated_weights(EXPERT, {"cleanliness_level"})
    assert sum(w.values()) == pytest.approx(1.0)
    assert w["cleanliness_level"] == pytest.approx(EXPERT["cleanliness_level"] * 1.5, rel=1e-6)


def test_round_trips_through_json() -> None:
    m = fit_taste(_decisions(np.random.default_rng(3), 30, STATED), STATED)
    again = TasteModel.from_json(m.to_json())
    assert again.learned == m.learned and again.active == m.active


def test_simulation_shows_learning_beats_stated_after_enough_decisions() -> None:
    res = taste_sim.run(n_members=25, rounds=8, pool=300, seed=4)
    first, last = res["rows"][0], res["rows"][-1]
    assert first["learned_ndcg"]["mean"] == pytest.approx(first["stated_ndcg"]["mean"])  # identical before data
    assert last["learned_top10_overlap"]["mean"] > last["stated_top10_overlap"]["mean"]
    assert last["share_worse_than_stated"] < 0.25

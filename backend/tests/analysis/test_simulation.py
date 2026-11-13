"""W5: Irving, policy simulation, power study, fairness audit, transfer test."""

from __future__ import annotations

import csv
import random

import numpy as np
import pytest

from cohab.analysis import fairness, power, transfer
from cohab.analysis.irving import is_stable, stable_roommates
from cohab.analysis.simulation import WorldConfig, compare_policies, gini, misreporting_sweep, run_world
from cohab.services.matching.population import synthetic_candidates


def _all_matchings(people, acc):
    if not people:
        yield {}
        return
    i, rest = people[0], people[1:]
    yield from _all_matchings(rest, acc)
    for j in rest:
        if j in acc[i] and i in acc[j]:
            for m in _all_matchings([x for x in rest if x != j], acc):
                yield {**m, i: j, j: i}


def test_irving_agrees_with_brute_force() -> None:
    for trial in range(250):
        rng = random.Random(trial)
        n = rng.choice([4, 5, 6, 7])
        prefs = []
        for i in range(n):
            others = [j for j in range(n) if j != i]
            rng.shuffle(others)
            prefs.append(others[: rng.randint(1, n - 1)] if trial % 2 else others)
        acc = [set(p) for p in prefs]
        exists = any(is_stable(prefs, m) for m in _all_matchings(list(range(n)), acc))
        res = stable_roommates(prefs)
        assert (res is not None) == exists, trial
        if res is not None:
            assert is_stable(prefs, res)


def test_irving_known_unsolvable_instance() -> None:
    # Classic 4-person instance with no stable matching (Gale & Shapley 1962).
    prefs = [[1, 2, 3], [2, 0, 3], [0, 1, 3], [0, 1, 2]]
    assert stable_roommates(prefs) is None


def test_gini() -> None:
    assert gini(np.ones(10)) == pytest.approx(0)
    assert gini(np.array([0, 0, 0, 10])) == pytest.approx(0.75)


@pytest.fixture(scope="module")
def world():
    return run_world(WorldConfig(n_agents=300, study_raters=30), seed=3)


def test_world_policy_ordering(world) -> None:
    p = world["policies"]
    assert p["oracle"]["top10_overlap_with_oracle"] == pytest.approx(1.0)
    assert p["oracle"]["regret"] == pytest.approx(0.0)
    # Using the questionnaire must beat showing random eligible people.
    assert p["expert"]["welfare_per_agent"] > p["random"]["welfare_per_agent"]
    assert p["expert"]["top10_overlap_with_oracle"] > p["random"]["top10_overlap_with_oracle"]
    assert 0 <= p["expert"]["exposure_gini"] <= 1


def test_world_is_reproducible_from_seed(world) -> None:
    again = run_world(WorldConfig(n_agents=300, study_raters=30), seed=3)
    assert again == world


def test_compare_policies_reports_intervals() -> None:
    res = compare_policies(WorldConfig(n_agents=200, study_raters=25), runs=3)
    cell = res["table"]["expert"]["welfare_per_agent"]
    assert cell["n"] == 3 and cell["ci95"][0] <= cell["mean"] <= cell["ci95"][1]
    assert "Hidden true compatibility" in res["assumptions"]


def test_misreporting_hurts_or_is_neutral() -> None:
    rows = misreporting_sweep([0.0, 0.6], runs=2, n_agents=250)
    assert rows[1]["expert_overlap_with_oracle"]["mean"] <= rows[0]["expert_overlap_with_oracle"]["mean"] + 0.02


def test_power_one_rep_and_minimum() -> None:
    sc = power.scenarios(0)[0]
    rep = power.one_rep(sc.truth, 30, seed=1)
    assert set(rep) >= {"learned_better", "delta_log_loss", "weight_corr_truth"}
    curve = power.power_curve([20, 40], reps=2, keys=["linear"])
    assert len(curve["scenarios"]) == 1 and len(curve["scenarios"][0]["rows"]) == 2
    assert power.minimum_raters(curve, "linear", power=0.0) == 20


def test_fairness_audit() -> None:
    cands = synthetic_candidates(250, seed=4, all_verified=True)
    res = fairness.audit(cands)
    gender = res["groupings"]["gender"]["table"]
    assert sum(r["n"] for r in gender) == 250
    assert all(r["pass_rate_ratio"] > 0 for r in gender)
    # Lifting the gender-preference constraint can only grow pools.
    for row in res["counterfactual_no_gender_preference"]:
        assert row["median_pool_after"] >= row["median_pool_before"]
    assert "gender_preference" in res["groupings"]["gender"]["constraint_marginal_pool_gain"]


def _write_speed_dating(path, n_people=60, seed=0):
    """A file in the real dataset's column format with a planted structure:
    decisions follow stated weights x ratings."""
    rng = np.random.default_rng(seed)
    stated = rng.dirichlet(np.ones(6) * 2, size=n_people) * 100
    rows = []
    for i in range(n_people):
        for j in range(n_people):
            if i == j or (i < n_people // 2) == (j < n_people // 2) or rng.random() > 0.35:
                continue
            r_ij = rng.integers(1, 11, 6)
            r_ji = rng.integers(1, 11, 6)
            s_ij = stated[i] @ r_ij / 1000
            s_ji = stated[j] @ r_ji / 1000
            dec = int(rng.random() < 1 / (1 + np.exp(-12 * (s_ij - 0.55))))
            dec_o = int(rng.random() < 1 / (1 + np.exp(-12 * (s_ji - 0.55))))
            rows.append((i, j, r_ij, r_ji, dec, dec_o))
    # Make the file symmetric: both directions of each date.
    seen = {(i, j): (rij, rji, d, do) for i, j, rij, rji, d, do in rows}
    with open(path, "w", newline="", encoding="latin-1") as fh:
        w = csv.writer(fh)
        w.writerow(transfer.REQUIRED)
        for (i, j), (rij, rji, d, do) in seen.items():
            for a, b, ra, rb, da, db in ((i, j, rij, rji, d, do), (j, i, rji, rij, do, d)):
                w.writerow(
                    [a + 1, b + 1, 1, da, db, int(da and db)]
                    + list(stated[a]) + list(stated[b]) + list(ra) + list(rb)
                )
    return path


def test_transfer_on_file_in_dataset_format(tmp_path) -> None:
    path = _write_speed_dating(tmp_path / "speed_dating.csv")
    res = transfer.run(path, n_boot=100)
    assert res["status"] == "ok"
    aucs = res["reciprocal"]["auc"]
    assert aucs["harmonic"]["auc"] > 0.6 and aucs["arithmetic"]["auc"] > 0.6
    svr = res["stated_vs_revealed"]
    assert svr["stated"]["auc"] > 0.6
    assert set(svr["mean_stated_weights"]) == set(transfer.ATTRS)


def test_transfer_reports_missing_file(tmp_path) -> None:
    assert transfer.run(tmp_path / "nope.csv")["status"] == "not_available"


def test_transfer_rejects_wrong_format(tmp_path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n", encoding="latin-1")
    with pytest.raises(ValueError):
        transfer.load(bad)


def test_auc() -> None:
    assert transfer.auc(np.array([0.1, 0.2, 0.8, 0.9]), np.array([0, 0, 1, 1])) == 1.0
    assert transfer.auc(np.array([1, 1, 1, 1.0]), np.array([0, 1, 0, 1])) == 0.5

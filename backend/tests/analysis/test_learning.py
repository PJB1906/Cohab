"""W4 analysis pipeline, checked by recovery on SYNTHETIC raters.

These tests establish that the methods work (they get back what was
planted). They say nothing about real people, by construction."""

from __future__ import annotations

import numpy as np
import pytest

from cohab.analysis import calibration, fitting, reliability
from cohab.analysis.pair_analysis import analyse_pairs
from cohab.analysis.simulate_raters import GroundTruth, simulate_pairs, simulate_raters
from cohab.analysis.stability import dirichlet_prior_samples, rank_stability, top3_tie_hint
from cohab.analysis.weights import EXPERT, EXPERT_STUDY, full_weight_set
from cohab.services.matching.population import synthetic_candidates
from cohab.services.matching.vectorised import Population
from cohab.services.matching.weight_sets import WEIGHT_SUM_TOLERANCE
from cohab.services.study.instrument import HELD_OUT_ATTRIBUTES, STUDY_ATTRIBUTES


@pytest.fixture(scope="module")
def planted():
    rng = np.random.default_rng(3)
    return rng.dirichlet(np.ones(len(STUDY_ATTRIBUTES)) * 1.5)


@pytest.fixture(scope="module")
def raters(planted):
    return simulate_raters(60, GroundTruth(weights=planted, scale=14), seed=11)


@pytest.fixture(scope="module")
def data(raters):
    return fitting.build_choice_data(raters)


def test_choice_data_shape(data, raters) -> None:
    assert data.X.shape[1] == len(STUDY_ATTRIBUTES)
    assert len(data.y) + data.n_none == sum(1 for r in raters for t in r.trials if t.kind == "pair")
    # Designed pairs: at most N_VARIED card fields differ, so most features are 0.
    assert np.mean(data.X == 0) > 0.5


def test_fit_recovers_planted_weights_better_than_expert(data, planted) -> None:
    fit = fitting.fit_weights(data, lam=0.3)
    assert np.all(fit.beta >= 0)
    assert fit.weights.sum() == pytest.approx(1.0)
    r_learned = np.corrcoef(fit.weights, planted)[0, 1]
    r_expert = np.corrcoef(EXPERT_STUDY, planted)[0, 1]
    assert r_learned > 0.7
    assert r_learned > r_expert + 0.3


def test_heavy_shrinkage_returns_the_expert_prior(data) -> None:
    fit = fitting.fit_weights(data, lam=1e6)
    assert np.allclose(fit.weights, EXPERT_STUDY, atol=2e-3)


def test_lambda_selection_prefers_shrinkage_when_truth_is_expert() -> None:
    r = simulate_raters(40, GroundTruth(weights=EXPERT_STUDY, scale=14), seed=5)
    d = fitting.build_choice_data(r)
    assert fitting.choose_lambda(d) >= 30


def test_cv_ladder_and_primary_comparison(data) -> None:
    cv = fitting.cross_validate(data, k=5, seed=0)
    s = fitting.summarise_cv(cv, n_boot=300)
    sc = s["scorers"]
    assert sc["random"]["accuracy"] == pytest.approx(0.5)
    assert sc["learned"]["accuracy"] > sc["random"]["accuracy"]
    assert sc["learned"]["log_loss"] < sc["random"]["log_loss"]
    lo, hi = s["learned_minus_expert_log_loss"]["ci"]
    assert lo <= s["learned_minus_expert_log_loss"]["estimate"] <= hi
    # Planted weights differ from expert, so learned must not lose to it.
    assert s["learned_minus_expert_accuracy"]["estimate"] > -0.01
    # Every rater appears in exactly one test fold.
    assert len(cv.per_rater["learned"]) == len(np.unique(data.rater))


def test_bootstrap_weights_bracket_point_estimate(data) -> None:
    fit = fitting.fit_weights(data, lam=1.0)
    boot = fitting.bootstrap_weights(data, lam=1.0, n_boot=60, seed=1)
    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
    inside = np.mean((fit.weights >= lo - 1e-9) & (fit.weights <= hi + 1e-9))
    assert inside >= 0.9
    assert np.allclose(boot.sum(axis=1), 1.0)


def test_importance_multiplier_is_estimated() -> None:
    truth = GroundTruth(weights=EXPERT_STUDY, scale=25, importance_multiplier=3.0)
    d = fitting.build_choice_data(simulate_raters(150, truth, seed=9))
    fit = fitting.fit_weights(d, lam=0.3)
    assert fit.multiplier > 1.8  # clearly above "no effect" (1.0)


def test_rank_task_tau_positive_for_true_weights(raters, planted) -> None:
    taus = fitting.rank_task_taus(raters, planted, 1.5)
    assert len(taus) == len(raters)
    assert np.mean(taus) > 0.2


def test_learning_curve_runs(data) -> None:
    curve = fitting.learning_curve(data, sizes=[10, 30], repeats=2, lam=1.0)
    assert [c["n_raters"] for c in curve] == [10, 30]


def test_reliability_kappa_and_ceiling(raters) -> None:
    s = reliability.reliability_summary(raters, n_boot=200)
    assert s["n_repeats"] > 0
    assert 0.5 <= s["agreement"] <= 1
    assert s["noise_ceiling_accuracy"] >= s["agreement"] - 1e-9
    assert reliability.noise_ceiling(1.0) == 1.0
    assert reliability.noise_ceiling(0.5) == 0.5
    assert reliability.cohens_kappa(["A", "B", "A"], ["A", "B", "A"]) == 1.0


def test_exclusion_rules_catch_inattentive_raters(planted) -> None:
    mixed = simulate_raters(40, GroundTruth(weights=planted, scale=14, inattentive_share=0.3), seed=4)
    kept, excluded = reliability.apply_exclusions(mixed)
    assert excluded, "some inattentive raters should be excluded"
    assert all("too_fast" in e.reasons or "attention" in e.reasons for e in excluded)
    assert len(kept) + len(excluded) == 40


def test_calibration_beats_raw_score(raters, data) -> None:
    res = calibration.cross_validated_calibration(raters, data, lam=1.0)
    cal, raw = res["calibrated"], res["raw_score_as_probability"]
    assert cal["ece"] < raw["ece"]
    assert cal["brier"] <= raw["brier"] + 1e-9
    assert 0 <= cal["ece"] < 0.1
    final = calibration.final_calibration(raters, EXPERT_STUDY, 1.5)
    k = final["knots"]
    assert k["x"] == sorted(k["x"]) and all(0 <= y <= 1 for y in k["y"])
    assert np.all(np.diff(calibration.apply_knots(k, np.linspace(0, 1, 50))) >= -1e-12)  # monotone


def test_full_weight_set_is_publishable(planted) -> None:
    w = full_weight_set(planted)
    assert set(w) == set(EXPERT)
    assert abs(sum(w.values()) - 1) <= WEIGHT_SUM_TOLERANCE / 100
    for h in HELD_OUT_ATTRIBUTES:
        assert w[h] == EXPERT[h]


def test_rank_stability_and_tie_rule() -> None:
    pop = Population.from_candidates(synthetic_candidates(200, seed=2, all_verified=True))
    tight = rank_stability(pop, EXPERT, dirichlet_prior_samples(EXPERT, 15, concentration=5000, seed=1))
    loose = rank_stability(pop, EXPERT, dirichlet_prior_samples(EXPERT, 15, concentration=20, seed=1))
    assert tight["topk_jaccard_mean"] > loose["topk_jaccard_mean"]
    assert tight["topk_jaccard_mean"] > 0.8

    stable = [np.array([0.9, 0.8, 0.7, 0.2])] * 10
    assert top3_tie_hint(stable)["tied"] is False
    shuffled = [np.array(v) for v in ([0.8, 0.81, 0.79, 0.2], [0.79, 0.8, 0.81, 0.2], [0.81, 0.8, 0.79, 0.1])] * 3
    assert top3_tie_hint(shuffled)["tied"] is True
    assert top3_tie_hint([np.array([0.9, 0.8])])["tied"] is False


def test_pair_analysis_detects_planted_signal_and_inflation() -> None:
    strong = analyse_pairs(simulate_pairs(60, EXPERT, signal=40, self_inflation=0.5, seed=1), EXPERT, n_boot=300, n_perm=500)
    assert strong["status"] == "ok"
    assert strong["known_groups"]["spearman_rho"] > 0.2
    assert strong["self_report_inflation"]["cleanliness_level"]["mean_inflation_steps"] > 0
    null = analyse_pairs(simulate_pairs(60, EXPERT, signal=0, self_inflation=0.0, seed=2), EXPERT, n_boot=300, n_perm=500)
    lo, hi = null["known_groups"]["spearman_ci"]
    assert lo < 0.25  # no planted relationship -> interval reaches near zero
    assert null["self_report_inflation"]["cleanliness_level"]["mean_inflation_steps"] == pytest.approx(0, abs=1e-9)
    assert analyse_pairs([], EXPERT)["status"] == "too_few_pairs"


def test_cluster_fit_tier_b(data) -> None:
    w, c = fitting.fit_clusters(data, lam=1.0)
    assert w.shape == (len(STUDY_ATTRIBUTES),) and w.sum() == pytest.approx(1.0)
    assert c.shape == (len(fitting.CLUSTERS),)
    w_shrunk, _ = fitting.fit_clusters(data, lam=1e7)
    assert np.allclose(w_shrunk, EXPERT_STUDY, atol=2e-3)
    # Within-cluster proportions are the expert's, always.
    i, j = STUDY_ATTRIBUTES.index("cleanliness_level"), STUDY_ATTRIBUTES.index("chore_approach")
    assert w[i] / w[j] == pytest.approx(EXPERT_STUDY[i] / EXPERT_STUDY[j])

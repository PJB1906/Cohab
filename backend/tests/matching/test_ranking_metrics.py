"""Hand-computed cases for precision@k / NDCG@k (COHAB_BUILD_PLAN.md §3: known
inputs, known outputs — volume adds nothing to a pure metric function)."""

from __future__ import annotations

import math

import pytest

from cohab.services.matching.ranking_metrics import ndcg_at_k, precision_at_k


class TestPrecisionAtK:
    def test_perfect_ranking(self):
        assert precision_at_k([1, 2, 3], {1, 2}, k=2) == 1.0

    def test_worst_ranking(self):
        assert precision_at_k([3, 4, 1, 2], {1, 2}, k=2) == 0.0

    def test_partial_overlap(self):
        # top-3 of [1, 3, 2, 4] is {1, 3, 2}; 2 of those (1, 2) are relevant.
        assert precision_at_k([1, 3, 2, 4], {1, 2}, k=3) == pytest.approx(2 / 3)

    def test_k_larger_than_list_divides_by_available_count(self):
        # top-k truncates to the 2 available ids, not padded to k=5.
        assert precision_at_k([1, 2], {1}, k=5) == 0.5

    def test_k_zero_or_empty_list_is_zero(self):
        assert precision_at_k([1, 2, 3], {1}, k=0) == 0.0
        assert precision_at_k([], {1}, k=3) == 0.0


class TestNdcgAtK:
    def test_ideal_ordering_scores_one(self):
        assert ndcg_at_k([2, 0], k=2) == pytest.approx(1.0)

    def test_reversed_ordering_matches_hand_computed_value(self):
        # DCG = 0/log2(2) + 2/log2(3); IDCG (ideal = [2, 0]) = 2/log2(2) + 0/log2(3) = 2.0
        expected_dcg = 0 / math.log2(2) + 2 / math.log2(3)
        expected = expected_dcg / 2.0
        assert ndcg_at_k([0, 2], k=2) == pytest.approx(expected)
        assert ndcg_at_k([0, 2], k=2) == pytest.approx(0.6309297535714574)

    def test_all_zero_relevance_is_zero_not_a_division_error(self):
        assert ndcg_at_k([0, 0, 0], k=3) == 0.0

    def test_k_zero_or_empty_list_is_zero(self):
        assert ndcg_at_k([1, 2, 3], k=0) == 0.0
        assert ndcg_at_k([], k=3) == 0.0

    def test_k_smaller_than_list_only_scores_top_k(self):
        # The 2 highest relevances (3, 2) are already the first 2 entries, in
        # order -> ideal for that slice regardless of what follows at k=2.
        assert ndcg_at_k([3, 2, 1, 0], k=2) == pytest.approx(1.0)

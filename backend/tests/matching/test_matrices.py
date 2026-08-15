"""Invariants and spot-checks on the scoring matrices — COHAB_MATCHING_SPEC.md
§4–§7. These guard against transcription errors, which are the likeliest bug in
a table of hand-entered numbers.
"""

import pytest

from cohab.services.matching import matrices as m

# spec §4: the three diagonal cells that are deliberately NOT 1.0.
_DIAGONAL_EXCEPTIONS = {
    ("sleep_schedule", "varies"): 0.80,
    ("communication_style", "let_go"): 0.55,
    ("cost_split_preference", "flexible"): 0.75,
}


@pytest.mark.parametrize("name", m.SIMILARITY_MATRICES)
def test_similarity_matrices_are_symmetric(name: str) -> None:
    matrix = m.SIMILARITY_MATRICES[name]
    for a, row in matrix.items():
        for b, value in row.items():
            assert value == matrix[b][a], f"{name}: {a}×{b} != {b}×{a}"


@pytest.mark.parametrize("name", m.SIMILARITY_MATRICES)
def test_similarity_diagonals(name: str) -> None:
    matrix = m.SIMILARITY_MATRICES[name]
    for key in matrix:
        expected = _DIAGONAL_EXCEPTIONS.get((name, key), 1.0)
        assert matrix[key][key] == expected, f"{name}: diagonal {key} = {matrix[key][key]}"


@pytest.mark.parametrize("name", m.SIMILARITY_MATRICES)
def test_similarity_matrices_are_square(name: str) -> None:
    matrix = m.SIMILARITY_MATRICES[name]
    keys = set(matrix)
    for row in matrix.values():
        assert set(row) == keys


@pytest.mark.parametrize(
    "name,a,b,expected",
    [
        # Documented harsh cells (spec §4).
        ("cleanliness_level", "very_tidy", "relaxed", 0.15),
        ("sociability", "friend", "independent", 0.25),
        ("sleep_schedule", "early", "night_owl", 0.20),
        ("diet", "veg", "nonveg", 0.50),
        ("cost_split_preference", "equal", "by_room", 0.45),
    ],
)
def test_similarity_harsh_cells(name: str, a: str, b: str, expected: float) -> None:
    assert m.SIMILARITY_MATRICES[name][a][b] == expected


def test_tolerance_asymmetry_sharing() -> None:
    # spec §5: (separate, communal) = 0.35 but (communal, separate) = 0.55.
    sharing = m.TOLERANCE_MATRICES["sharing"]
    assert sharing["separate"]["communal"] == 0.35
    assert sharing["communal"]["separate"] == 0.55


def test_tolerance_guests_first_column_all_one() -> None:
    # spec §5: a roommate who rarely has guests satisfies everyone.
    for row in m.TOLERANCE_MATRICES["guests"].values():
        assert row["rarely"] == 1.00


def test_smoking_zero_cell_and_alcohol_softer_floor() -> None:
    # spec §5: smoking (smoke_free, indoors) = 0.00; alcohol softens it to 0.15.
    assert m.TOLERANCE_MATRICES["smoking"]["smoke_free"]["indoors"] == 0.00
    assert m.TOLERANCE_MATRICES["alcohol"]["smoke_free"]["indoors"] == 0.15
    # Otherwise identical structure.
    smoking = m.TOLERANCE_MATRICES["smoking"]
    alcohol = m.TOLERANCE_MATRICES["alcohol"]
    for pref in smoking:
        for behav in smoking[pref]:
            if (pref, behav) == ("smoke_free", "indoors"):
                continue
            assert smoking[pref][behav] == alcohol[pref][behav]


def test_nonveg_cooking_veglike_columns_are_all_one() -> None:
    # spec §5: {veg, vegan, jain} share the "1.00 everywhere" first column.
    for row in m.TOLERANCE_MATRICES["nonveg_cooking"].values():
        for diet in ("veg", "vegan", "jain"):
            assert row[diet] == 1.00


def test_ordinal_similarity() -> None:
    order = m.ORDINAL_ORDERS["daytime_presence"]  # ("out", "partly", "home")
    assert m.ordinal_similarity(order, "out", "out") == 1.0
    assert m.ordinal_similarity(order, "out", "partly") == 0.5
    assert m.ordinal_similarity(order, "out", "home") == 0.0


def test_jaccard_similarity() -> None:
    assert m.jaccard_similarity(["a", "b"], ["a", "b"]) == 1.0
    assert m.jaccard_similarity(["a", "b", "c"], ["a"]) == pytest.approx(1 / 3)
    # Floor of 0.3 when either list is empty (spec §4).
    assert m.jaccard_similarity([], ["a"]) == 0.3
    assert m.jaccard_similarity(None, ["a"]) == 0.3


def test_budget_similarity() -> None:
    assert m.budget_similarity(10000, 10000) == 1.0
    # A ₹15,000 gap scores zero; ₹2,000 scores 0.87 (spec §7).
    assert m.budget_similarity(10000, 25000) == 0.0
    assert m.budget_similarity(10000, 12000) == pytest.approx(0.8667, abs=1e-3)
    # Never negative.
    assert m.budget_similarity(10000, 40000) == 0.0

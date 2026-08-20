"""`_print_yield`'s median formatting — docs/DECISIONS.md D-10 hardening
pass: `report.py:67` used to truncate a `.5` median via `int()`, diverging
from `tuning.py`/`evaluation.py`'s `{median:g}` formatting. `report.py` has
no other tests (it's a manually-run stdout script, per its own module
docstring); this is a minimal, direct regression test for that one bug,
mirroring how the rest of `services/matching/` is required to have tests
(CLAUDE.md) without needing the full DB-backed candidate pool the script
itself runs against.
"""

from unittest.mock import MagicMock

from cohab.services.matching.report import _print_yield


def test_print_yield_does_not_truncate_a_fractional_median(capsys) -> None:
    ranker = MagicMock()
    # Four subjects with eligible-pool sizes 1/2/3/4 -> median 2.5, not 2.
    ranker.filter_with_reasons.side_effect = [([object()] * n, []) for n in (1, 2, 3, 4)]

    _print_yield(ranker, subjects=[object()] * 4, pool=[])

    out = capsys.readouterr().out
    assert "median=2.5" in out

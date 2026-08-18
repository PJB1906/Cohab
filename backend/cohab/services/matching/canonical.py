"""Canonical-pair bookkeeping for `match_score` persistence — Phase 4.

`MatchRanker.rank()` always scores with `a=subject` (`scoring.py`), but the
`match_score` table requires canonical `user_id_a < user_id_b` storage (one
row per unordered pair — CLAUDE.md, PRD §5.2). Whichever of subject/candidate
is *not* the canonical `a` needs its `MatchResult` flipped before a row is
written, and flipped back when reconstructing a stored row from the
non-canonical party's viewpoint (`build_explanation` reads `sim_a` as "the
viewer's direction" — `explanations.py`). `flip` is its own inverse, so the
same function covers both directions.

Pure bookkeeping, not scoring: it rearranges an already-computed
`MatchResult`, changing no number in it.
"""

from __future__ import annotations

from cohab.services.matching.scoring import MatchResult


def flip(result: MatchResult) -> MatchResult:
    """Swap `a`/`b` throughout: subject/candidate ids, the two directional
    scores, and each breakdown entry's `sim_a`/`sim_b` and `w_a`/`w_b`."""
    breakdown = {
        name: {
            **cell,
            "sim_a": cell["sim_b"],
            "sim_b": cell["sim_a"],
            "w_a": cell["w_b"],
            "w_b": cell["w_a"],
        }
        for name, cell in result.breakdown.items()
    }
    return MatchResult(
        subject_id=result.candidate_id,
        candidate_id=result.subject_id,
        score_ab=result.score_ba,
        score_ba=result.score_ab,
        combined_score=result.combined_score,
        weight_set_id=result.weight_set_id,
        breakdown=breakdown,
    )

"""MatchRanker — Stage 1 + Stage 2 + ordering + explanations.

Runs the eligibility filter, scores each surviving candidate directionally,
sorts by combined score, and attaches the explanation card. This is the public
entry point read by report.py (and, in Phase 4, the API layer).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.eligibility import EligibilityFilter, Exclusion
from cohab.services.matching.explanations import Explanation, build_explanation
from cohab.services.matching.scoring import CompatibilityMatcher, MatchResult


@dataclass(frozen=True)
class RankedMatch:
    candidate: Candidate
    result: MatchResult
    explanation: Explanation


class MatchRanker:
    def __init__(
        self,
        matcher: CompatibilityMatcher,
        blocked_pairs: frozenset[frozenset[uuid.UUID]] | set | None = None,
    ) -> None:
        self.matcher = matcher
        self.filter = EligibilityFilter(blocked_pairs=blocked_pairs)

    def rank(
        self, subject: Candidate, pool: Iterable[Candidate]
    ) -> list[RankedMatch]:
        eligible, _excluded = self.filter.filter(subject, pool)

        matches: list[RankedMatch] = []
        for candidate in eligible:
            result = self.matcher.score(subject, candidate)
            explanation = build_explanation(subject, candidate, result)
            matches.append(RankedMatch(candidate, result, explanation))

        # Sort by combined score desc; tie-break prefers the *less lopsided* pair
        # (higher of the smaller directional score), then user_id asc for a stable
        # deterministic order.
        matches.sort(
            key=lambda m: (
                -m.result.combined_score,
                -min(m.result.score_ab, m.result.score_ba),
                m.candidate.user_id,
            )
        )
        return matches

    def filter_with_reasons(
        self, subject: Candidate, pool: Iterable[Candidate]
    ) -> tuple[list[Candidate], list[Exclusion]]:
        """Expose Stage 1 output directly — useful for report.py's yield/reason
        diagnostics (spec §11)."""
        return self.filter.filter(subject, pool)

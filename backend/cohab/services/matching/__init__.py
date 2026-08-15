"""Two-stage matching engine — COHAB_MATCHING_SPEC.md.

Stage 1 eligibility filtering, Stage 2 directional scoring, ranking and
template-based explanations (COHAB_BUILD_PLAN.md §4, Phase 2).
"""

from cohab.services.matching.candidate import Candidate
from cohab.services.matching.eligibility import EligibilityFilter, Exclusion, Reason
from cohab.services.matching.explanations import Card, Explanation, build_explanation
from cohab.services.matching.ranker import MatchRanker, RankedMatch
from cohab.services.matching.scoring import CompatibilityMatcher, MatchResult, blend, harmonic_mean
from cohab.services.matching.text import NeutralTextSimilarity, TextSimilarity, TfidfSimilarity

__all__ = [
    "Candidate",
    "EligibilityFilter",
    "Exclusion",
    "Reason",
    "Card",
    "Explanation",
    "build_explanation",
    "MatchRanker",
    "RankedMatch",
    "CompatibilityMatcher",
    "MatchResult",
    "blend",
    "harmonic_mean",
    "NeutralTextSimilarity",
    "TextSimilarity",
    "TfidfSimilarity",
]

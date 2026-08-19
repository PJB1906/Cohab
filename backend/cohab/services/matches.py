"""`GET /matches` / `GET /matches/{id}/explanation` — build plan §4 Phase 4.

Stage A: compute on read (PRD §7.1) — every call re-runs Stage 1 + Stage 2 in
the request, cheap at pilot-scale pool sizes. What Stage A's own diagram
doesn't show, but PRD §8.1's onboarding sequence does, is that the result
also gets **persisted** to `match_score`: an upsert per eligible pair, so
- `GET /matches/{id}/explanation` has a stable row to read and to attach a
  `suggested -> viewed` transition to (PRD §8.2), and
- a user's recorded interest survives a later rescore (the upsert refreshes
  score/breakdown but never touches `state`/`interested_by_*`).

At one active `weight_set` this can't yet violate CLAUDE.md's immutable-
explanation guarantee — that only becomes a live question once Phase 8
publishes a second version, at which point always-refresh-on-read would need
revisiting (noted in docs/DECISIONS.md, not solved here).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cohab.models import Listing, MatchScore, User, WeightSet
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.canonical import flip
from cohab.services.matching.explanations import Explanation, build_explanation
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher, MatchResult
from cohab.services.matching.text import TextSimilarity


class MatchesError(Exception):
    pass


class MatchNotFound(MatchesError):
    pass


class NotAParty(MatchesError):
    """The requesting user is neither side of this match_score row."""


@dataclass(frozen=True)
class MatchListEntry:
    match_id: uuid.UUID
    candidate: Candidate
    combined_score: float
    explanation: Explanation


@dataclass(frozen=True)
class MatchExplanationResult:
    match_id: uuid.UUID
    candidate: Candidate
    result: MatchResult
    explanation: Explanation
    state: str
    # `state` is shared by both parties — it flips to "interested" as soon as
    # *either* side clicks, so the UI can't use it to decide whether *this*
    # viewer already has. This is the per-viewer flag for that (found live
    # while manually verifying Phase 6: without it, the second party's
    # button reads "Interest sent" before they've ever clicked it, and the
    # match can never reach Mutual through the UI).
    you_expressed_interest: bool
    listing: Listing | None


def _load_candidate(session: Session, user_id: uuid.UUID) -> Candidate | None:
    user = session.get(
        User,
        user_id,
        options=[
            selectinload(User.preference_profile),
            selectinload(User.attribute_weights),
            selectinload(User.listing),
        ],
    )
    if user is None or user.preference_profile is None:
        return None
    return Candidate.from_orm(user, user.preference_profile, user.listing)


def _load_pool(session: Session, exclude_user_id: uuid.UUID) -> list[Candidate]:
    stmt = (
        select(User)
        .where(User.id != exclude_user_id)
        .options(
            selectinload(User.preference_profile),
            selectinload(User.attribute_weights),
            selectinload(User.listing),
        )
    )
    pool: list[Candidate] = []
    for user in session.scalars(stmt).all():
        if user.preference_profile is None:
            continue
        pool.append(Candidate.from_orm(user, user.preference_profile, user.listing))
    return pool


class MatchesService:
    def __init__(
        self,
        session: Session,
        weight_set: WeightSet,
        text_similarity: TextSimilarity,
    ) -> None:
        self.session = session
        self.weight_set = weight_set
        matcher = CompatibilityMatcher(weight_set.weights, weight_set.id, text_similarity=text_similarity)
        self.ranker = MatchRanker(matcher)

    def _upsert(self, subject_id: uuid.UUID, candidate_id: uuid.UUID, result: MatchResult) -> MatchScore:
        if subject_id < candidate_id:
            a_id, b_id, canonical = subject_id, candidate_id, result
        else:
            a_id, b_id, canonical = candidate_id, subject_id, flip(result)

        row = self.session.scalar(
            select(MatchScore).where(MatchScore.user_id_a == a_id, MatchScore.user_id_b == b_id)
        )
        if row is None:
            row = MatchScore(user_id_a=a_id, user_id_b=b_id, state="suggested")
            self.session.add(row)

        row.weight_set_id = canonical.weight_set_id
        row.score_ab = canonical.score_ab
        row.score_ba = canonical.score_ba
        row.combined_score = canonical.combined_score
        row.breakdown = canonical.breakdown
        # state / interested_by_a / interested_by_b intentionally untouched —
        # a rescore must not erase a user's recorded interest.
        self.session.flush()
        return row

    def express_interest(self, subject_user: User, match_id: uuid.UUID) -> str:
        """PRD §8.2: Viewed -> Interested on the caller's own flag; Interested
        -> Mutual once both `interested_by_*` flags are set. The only two
        transitions anything in this phase can actually produce — there's no
        reject/expire endpoint yet, so this doesn't try to model the rest of
        the state machine."""
        row = self.session.get(MatchScore, match_id)
        if row is None:
            raise MatchNotFound(match_id)
        if subject_user.id not in (row.user_id_a, row.user_id_b):
            raise NotAParty(match_id)

        if subject_user.id == row.user_id_a:
            row.interested_by_a = True
        else:
            row.interested_by_b = True

        if row.state in ("suggested", "viewed"):
            row.state = "interested"
        # Guard against regressing a pair that has already moved past Mutual
        # (chatting/contact_shared/...) back down to it — a repeat POST with
        # both flags already True (stale tab, client retry) would otherwise
        # silently undo real lifecycle progress (found in code review).
        if (
            row.interested_by_a
            and row.interested_by_b
            and row.state in ("suggested", "viewed", "interested", "mutual")
        ):
            row.state = "mutual"

        self.session.commit()
        return row.state

    def get_matches(self, subject_user: User, limit: int = 10) -> list[MatchListEntry]:
        subject = _load_candidate(self.session, subject_user.id)
        if subject is None:
            return []
        pool = _load_pool(self.session, subject_user.id)

        ranked = self.ranker.rank(subject, pool)[:limit]
        entries = [
            MatchListEntry(
                match_id=self._upsert(subject.user_id, m.candidate.user_id, m.result).id,
                candidate=m.candidate,
                combined_score=m.result.combined_score,
                explanation=m.explanation,
            )
            for m in ranked
        ]
        self.session.commit()
        return entries

    def get_explanation(self, subject_user: User, match_id: uuid.UUID) -> MatchExplanationResult:
        row = self.session.get(MatchScore, match_id)
        if row is None:
            raise MatchNotFound(match_id)
        if subject_user.id not in (row.user_id_a, row.user_id_b):
            raise NotAParty(match_id)

        other_id = row.user_id_b if subject_user.id == row.user_id_a else row.user_id_a
        other = _load_candidate(self.session, other_id)
        subject = _load_candidate(self.session, subject_user.id)
        if subject is None or other is None:
            raise MatchNotFound(match_id)

        stored = MatchResult(
            subject_id=row.user_id_a,
            candidate_id=row.user_id_b,
            score_ab=row.score_ab,
            score_ba=row.score_ba,
            combined_score=row.combined_score,
            weight_set_id=row.weight_set_id,
            breakdown=row.breakdown,
        )
        result = stored if subject_user.id == row.user_id_a else flip(stored)

        explanation = build_explanation(subject, other, result)

        if row.state == "suggested":
            row.state = "viewed"
            self.session.commit()

        listing = None
        if other.seeker_type == "has_place":
            listing = self.session.scalar(select(Listing).where(Listing.user_id == other_id))

        you_expressed_interest = (
            row.interested_by_a if subject_user.id == row.user_id_a else row.interested_by_b
        )

        return MatchExplanationResult(
            match_id=row.id,
            candidate=other,
            result=result,
            explanation=explanation,
            state=row.state,
            you_expressed_interest=you_expressed_interest,
            listing=listing,
        )

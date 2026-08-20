"""`GET /matches` / `GET /matches/{id}/explanation` — build plan §4 Phase 4.

Stage A: compute on read (PRD §7.1) — every call re-runs Stage 1 + Stage 2 in
the request, cheap at pilot-scale pool sizes. What Stage A's own diagram
doesn't show, but PRD §8.1's onboarding sequence does, is that the result
also gets **persisted** to `match_score`: an upsert per eligible pair, so
- `GET /matches/{id}/explanation` has a stable row to read and to attach a
  `suggested -> viewed` transition to (PRD §8.2), and
- a user's recorded interest survives a later rescore (the upsert refreshes
  score/breakdown but never touches `state`/`interested_by_*`).

`_upsert` only refreshes score/breakdown/weight_set_id while a row is still
"suggested" — once viewed (or moved further), CLAUDE.md's weight_set
immutability guarantee requires it stay exactly what the user was shown, even
after a later `weight_set` version is published (docs/DECISIONS.md D-4.6,
resolved in Phase 8).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from cohab.models import Listing, MatchScore, User, WeightSet
from cohab.services.match_access import ensure_pair_active
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.canonical import flip
from cohab.services.matching.explanations import Explanation, build_explanation
from cohab.services.matching.ranker import MatchRanker
from cohab.services.matching.scoring import CompatibilityMatcher, MatchResult
from cohab.services.matching.text import TextSimilarity
from cohab.services.safety import blocked_pairs_for


class MatchesError(Exception):
    pass


class MatchNotFound(MatchesError):
    pass


class NotAParty(MatchesError):
    """The requesting user is neither side of this match_score row."""


class InvalidStateTransition(MatchesError):
    """The match isn't in a state this transition can be applied from."""


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


def _settled_pairs_for(session: Session, user_id: uuid.UUID) -> frozenset[frozenset[uuid.UUID]]:
    """Pairs already `rejected` or `cohabiting` — feeds
    `EligibilityFilter.settled_pairs` (Stage 1) so a settled match never
    resurfaces as a fresh suggestion. Found in code review: nothing enforced
    `RejectConfirmDialog.tsx`'s own promise that a rejected match can't be
    "picked back up" — Stage 1 had no notion of `match_score` at all before
    this. Scoped to `user_id`, same reasoning as `blocked_pairs_for`."""
    rows = session.scalars(
        select(MatchScore).where(
            (MatchScore.user_id_a == user_id) | (MatchScore.user_id_b == user_id),
            MatchScore.state.in_(("rejected", "cohabiting")),
        )
    ).all()
    return frozenset(frozenset({row.user_id_a, row.user_id_b}) for row in rows)


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

        # Once a row has been viewed (or moved further), its score/breakdown
        # is a record of what the user was actually shown — CLAUDE.md's
        # weight_set immutability guarantee requires that stay reproducible,
        # not silently rewritten by a later rescore under a newly-published
        # weight_set (docs/DECISIONS.md D-4.6, resolved in Phase 8). Only a
        # still-"suggested" row, which nobody has looked at yet, is safe to
        # freely refresh.
        if row.state == "suggested":
            row.weight_set_id = canonical.weight_set_id
            row.score_ab = canonical.score_ab
            row.score_ba = canonical.score_ba
            row.combined_score = canonical.combined_score
            row.breakdown = canonical.breakdown
        # state / interested_by_a / interested_by_b intentionally untouched —
        # a rescore must not erase a user's recorded interest.
        self.session.flush()
        return row

    def _load_pair_row(self, subject_user: User, match_id: uuid.UUID) -> MatchScore:
        row = self.session.get(MatchScore, match_id)
        if row is None:
            raise MatchNotFound(match_id)
        if subject_user.id not in (row.user_id_a, row.user_id_b):
            raise NotAParty(match_id)
        ensure_pair_active(self.session, row)
        return row

    def express_interest(self, subject_user: User, match_id: uuid.UUID) -> str:
        """PRD §8.2: Viewed -> Interested on the caller's own flag; Interested
        -> Mutual once both `interested_by_*` flags are set."""
        row = self._load_pair_row(subject_user, match_id)
        # Phase 8 added terminal states this predates (found in code
        # review): without this guard, expressing interest on an already-
        # rejected or already-cohabiting match silently set
        # interested_by_a/b with no visible effect on `state`, rather than
        # being rejected as the invalid call it is.
        if row.state in ("rejected", "cohabiting", "expired"):
            raise InvalidStateTransition(row.state)

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

    def confirm_move_in(self, subject_user: User, match_id: uuid.UUID) -> str:
        """PRD §8.2: ContactShared -> Cohabiting ("move-in confirmed").
        `cohabiting_since` anchors both the feedback cadence and the
        cohabitation-duration figure Phase 9's survival analysis needs, so
        it's set once here and never touched again."""
        row = self._load_pair_row(subject_user, match_id)
        if row.state != "contact_shared":
            raise InvalidStateTransition(row.state)

        row.state = "cohabiting"
        row.cohabiting_since = datetime.now(timezone.utc)
        self.session.commit()
        return row.state

    def reject(self, subject_user: User, match_id: uuid.UUID) -> str:
        """PRD §8.2's "Viewed -> Rejected: dismisses" and "Chatting ->
        Rejected: either withdraws" are both "one party unilaterally ends
        it" — modelled as one transition, valid from any non-terminal state
        short of Cohabiting. A repeat call against an already-terminal state
        is a no-op guard (InvalidStateTransition), same monotonic-transition
        precedent as express_interest's guard against regressing past
        Mutual."""
        row = self._load_pair_row(subject_user, match_id)
        if row.state not in ("viewed", "interested", "mutual", "chatting", "contact_shared"):
            raise InvalidStateTransition(row.state)

        row.state = "rejected"
        self.session.commit()
        return row.state

    def get_matches(self, subject_user: User, limit: int = 10) -> list[MatchListEntry]:
        subject = _load_candidate(self.session, subject_user.id)
        if subject is None:
            return []
        pool = _load_pool(self.session, subject_user.id)

        # Block-awareness depends on the calling user, who isn't known until
        # here — `MatchesService` is constructed once per request (before
        # the subject is known), so this can't be set at __init__ time.
        # Closes docs/DECISIONS.md D-2.6: Stage 1's `blocked_pairs` param has
        # been correct and unit-tested since Phase 2 but had no live caller.
        self.ranker.filter.blocked_pairs = blocked_pairs_for(self.session, subject_user.id)
        self.ranker.filter.settled_pairs = _settled_pairs_for(self.session, subject_user.id)

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
        row = self._load_pair_row(subject_user, match_id)

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

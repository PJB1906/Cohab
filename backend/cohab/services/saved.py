"""Saved matches — a user bookmarks another user's match to compare later.

New scope, added while porting the mobile mockup's "Saved" tab (not in
`docs/COHAB_PRD.md` or `docs/COHAB_MATCHING_SPEC.md`; flag for
`docs/DECISIONS.md`). Framework-free per CLAUDE.md.

`load_match` (match_access.py) does the lookup+authorize step shared with
chat/contact-share — `MatchNotFound`/`NotAParty` propagate from there rather
than being redefined here, same precedent as `contact_share.py`.

`list_saved` reuses `matches.py`'s `_load_candidate` and the stored
`MatchScore` row (score_ab/score_ba/combined_score/breakdown) to rebuild a
per-viewer `Explanation` via `build_explanation`/`flip`, the same
reconstruction `MatchesService.get_explanation` does — deliberately not
re-run through the ranker/matcher (no `weight_set` needed here), and
deliberately not flipping `state` "suggested" -> "viewed" as a side effect of
listing saves.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cohab.models import MatchScore, SavedMatch, User
from cohab.services.match_access import MatchNotFound, NotAParty, load_match
from cohab.services.matches import _load_candidate
from cohab.services.matching.candidate import Candidate
from cohab.services.matching.canonical import flip
from cohab.services.matching.explanations import Explanation, build_explanation
from cohab.services.matching.scoring import MatchResult

__all__ = ["MatchNotFound", "NotAParty", "SavedMatchEntry", "SavedService"]


@dataclass(frozen=True)
class SavedMatchEntry:
    saved_at: datetime
    match_id: uuid.UUID
    candidate: Candidate
    combined_score: float
    explanation: Explanation
    state: str


class SavedService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _existing(self, user: User, match_id: uuid.UUID) -> SavedMatch | None:
        return self.session.scalar(
            select(SavedMatch).where(
                SavedMatch.user_id == user.id, SavedMatch.match_score_id == match_id
            )
        )

    def _entry(self, user: User, saved: SavedMatch, match_row: MatchScore) -> SavedMatchEntry:
        """Rebuild a `SavedMatchEntry` from a stored `match_score` row, from
        `user`'s point of view — the same reconstruction
        `MatchesService.get_explanation` does, minus its `suggested ->
        viewed` side effect (listing/saving a match shouldn't mark it
        viewed)."""
        other_id = match_row.user_id_b if user.id == match_row.user_id_a else match_row.user_id_a
        subject = _load_candidate(self.session, user.id)
        other = _load_candidate(self.session, other_id)
        if subject is None or other is None:
            raise MatchNotFound(match_row.id)

        stored = MatchResult(
            subject_id=match_row.user_id_a,
            candidate_id=match_row.user_id_b,
            score_ab=match_row.score_ab,
            score_ba=match_row.score_ba,
            combined_score=match_row.combined_score,
            weight_set_id=match_row.weight_set_id,
            breakdown=match_row.breakdown,
        )
        result = stored if user.id == match_row.user_id_a else flip(stored)
        explanation = build_explanation(subject, other, result)

        return SavedMatchEntry(
            saved_at=saved.created_at,
            match_id=match_row.id,
            candidate=other,
            combined_score=result.combined_score,
            explanation=explanation,
            state=match_row.state,
        )

    def save(self, user: User, match_id: uuid.UUID) -> SavedMatchEntry:
        """Idempotent: saving an already-saved match returns the existing
        row rather than raising or duplicating. `MatchNotFound`/`NotAParty`
        propagate from `load_match` for an invalid or non-party match.

        Checks both candidates are still loadable *before* writing anything —
        `_entry` needs both to rebuild the explanation, and used to be the
        first place that could raise `MatchNotFound` (e.g. a party's profile
        deleted after the match was scored), by which point the row had
        already been committed: an orphaned bookmark and a 404 response for
        what looked, from the DB's point of view, like a successful save."""
        match_row = load_match(self.session, user, match_id)
        other_id = match_row.user_id_b if user.id == match_row.user_id_a else match_row.user_id_a
        if _load_candidate(self.session, user.id) is None or _load_candidate(self.session, other_id) is None:
            raise MatchNotFound(match_id)

        existing = self._existing(user, match_id)
        if existing is None:
            row = SavedMatch(user_id=user.id, match_score_id=match_id)
            self.session.add(row)
            try:
                self.session.flush()
            except IntegrityError:
                # Two near-simultaneous saves from the same user race on
                # uq_saved_match_user_pair — same recovery pattern as
                # ContactShareService.opt_in.
                self.session.rollback()
                row = self._existing(user, match_id)
            self.session.commit()
        else:
            row = existing

        return self._entry(user, row, match_row)

    def unsave(self, user: User, match_id: uuid.UUID) -> None:
        """Idempotent: no error if the match was never saved (or already
        unsaved). Deliberately doesn't call `load_match` — deleting a row
        scoped to `user.id` can't affect anyone else's save regardless of
        whether the caller is still a party to the match."""
        existing = self._existing(user, match_id)
        if existing is not None:
            self.session.delete(existing)
            self.session.commit()

    def list_saved(self, user: User) -> list[SavedMatchEntry]:
        """Newest-first, the caller's own saves only."""
        rows = self.session.scalars(
            select(SavedMatch)
            .where(SavedMatch.user_id == user.id)
            .order_by(SavedMatch.created_at.desc())
        ).all()

        entries: list[SavedMatchEntry] = []
        for saved in rows:
            match_row = self.session.get(MatchScore, saved.match_score_id)
            if match_row is None:
                continue  # FK-guaranteed not to happen; defensive only
            try:
                entries.append(self._entry(user, saved, match_row))
            except MatchNotFound:
                continue  # candidate's profile since deleted; skip rather than 500
        return entries

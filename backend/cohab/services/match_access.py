"""Shared "look up a MatchScore and verify the caller is a party to it"
primitive. `ChatService` and `ContactShareService` both needed this
identical lookup+authorize step; each defined its own copy of it plus its
own `MatchNotFound`/`NotAParty` exception pair, which meant `api/chat.py`
had to alias-import both pairs to avoid a name collision and a fix made in
one copy wouldn't apply to the other (found in code review). Framework-free
per CLAUDE.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from cohab.models import MatchScore, User
from cohab.services.safety import is_blocked_between


class MatchAccessError(Exception):
    pass


class MatchNotFound(MatchAccessError):
    pass


class NotAParty(MatchAccessError):
    pass


class PairBlocked(MatchAccessError):
    """Phase 7 (docs/DECISIONS.md D-7.5): PRD §10 — blocking "hides existing
    threads." Raised so chat and contact-share stop working on a match the
    moment either side has blocked the other, without deleting any history."""


def load_match(session: Session, user: User, match_id: uuid.UUID) -> MatchScore:
    row = session.get(MatchScore, match_id)
    if row is None:
        raise MatchNotFound(match_id)
    if user.id not in (row.user_id_a, row.user_id_b):
        raise NotAParty(match_id)
    return row


def ensure_pair_active(session: Session, row: MatchScore) -> None:
    """Call after `load_match` in any flow that lets the two parties of a
    match interact (chat, contact-share) — raises `PairBlocked` if either
    side has blocked the other, regardless of which of them is asking."""
    if is_blocked_between(session, row.user_id_a, row.user_id_b):
        raise PairBlocked(row.id)

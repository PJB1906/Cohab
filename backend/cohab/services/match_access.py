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


class MatchAccessError(Exception):
    pass


class MatchNotFound(MatchAccessError):
    pass


class NotAParty(MatchAccessError):
    pass


def load_match(session: Session, user: User, match_id: uuid.UUID) -> MatchScore:
    row = session.get(MatchScore, match_id)
    if row is None:
        raise MatchNotFound(match_id)
    if user.id not in (row.user_id_a, row.user_id_b):
        raise NotAParty(match_id)
    return row

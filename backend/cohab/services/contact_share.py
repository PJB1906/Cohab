"""Mutual contact-sharing consent — build plan §4 Phase 6, PRD §8.2/§10.

`contact_share`: `UNIQUE (score_id, user_id)` — one row per participant, so
"both consented" is a count of two (PRD §5.2). Opting in requires the thread
to already be open (`chatting` or later): PRD screen order puts Chat (9)
before Contact share (10), and the state diagram only has Chatting ->
ContactShared, never Mutual -> ContactShared directly.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cohab.models import ContactShare, MatchScore, User
from cohab.services.match_access import MatchNotFound, NotAParty, PairBlocked, ensure_pair_active, load_match
from cohab.services.match_events import transition

__all__ = [
    "AlreadyMutuallyShared",
    "ChatNotOpenYet",
    "ContactShareService",
    "ContactStatus",
    "MatchNotFound",
    "NotAParty",
    "PairBlocked",
]

_OPT_IN_ALLOWED_STATES = {"chatting", "contact_shared"}


class ContactShareError(Exception):
    """Base for contact-share-specific failures. `MatchNotFound`/`NotAParty`
    are the shared lookup+authorize errors from `match_access` — see
    `chat.py`'s `ChatError` docstring for why they're imported, not
    redefined, here."""


class ChatNotOpenYet(ContactShareError):
    """PRD screen order: chat (9) precedes contact share (10)."""


class NoPhoneOnFile(ContactShareError):
    """v2 audit: opting in to "share my phone number" with no number on the
    account completed the consent and released nothing, so the other person
    agreed in exchange for an empty card. Refuse it with a way to fix it."""


class AlreadyMutuallyShared(ContactShareError):
    """`withdraw()` only undoes a one-sided opt-in — once both parties have
    consented the share is complete, mirroring how a revealed phone number
    can't be un-revealed. docs/DECISIONS.md D-10.5."""


@dataclass(frozen=True)
class ContactStatus:
    you_consented: bool
    other_consented: bool
    other_phone: str | None


class ContactShareService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _status(self, user: User, row: MatchScore) -> ContactStatus:
        other_id = row.user_id_b if user.id == row.user_id_a else row.user_id_a
        shares = self.session.scalars(
            select(ContactShare).where(ContactShare.match_score_id == row.id)
        ).all()
        you_consented = any(s.user_id == user.id for s in shares)
        other_consented = any(s.user_id == other_id for s in shares)

        other_phone = None
        if you_consented and other_consented:
            other = self.session.get(User, other_id)
            other_phone = other.phone_number if other is not None else None

        return ContactStatus(
            you_consented=you_consented, other_consented=other_consented, other_phone=other_phone
        )

    def get_status(self, user: User, match_id: uuid.UUID) -> ContactStatus:
        row = load_match(self.session, user, match_id)
        ensure_pair_active(self.session, row)
        return self._status(user, row)

    def opt_in(self, user: User, match_id: uuid.UUID) -> ContactStatus:
        row = load_match(self.session, user, match_id)
        ensure_pair_active(self.session, row)
        if row.state not in _OPT_IN_ALLOWED_STATES:
            raise ChatNotOpenYet(match_id)
        if not (user.phone_number or "").strip():
            raise NoPhoneOnFile(match_id)

        existing = self.session.scalar(
            select(ContactShare).where(
                ContactShare.match_score_id == match_id, ContactShare.user_id == user.id
            )
        )
        if existing is None:
            self.session.add(
                ContactShare(
                    match_score_id=match_id,
                    user_id=user.id,
                    consented_at=datetime.now(timezone.utc),
                )
            )
            try:
                self.session.flush()
            except IntegrityError:
                # Two near-simultaneous opt-ins from the same user race on
                # `uq_contact_share_score_user`. The row now exists from the
                # other transaction — rollback and continue; `_status` below
                # re-reads consent fresh (rollback expires `row`, which
                # re-fetches transparently on next attribute access).
                self.session.rollback()

        status = self._status(user, row)
        if status.you_consented and status.other_consented and row.state == "chatting":
            # PRD §8.2: Chatting -> ContactShared, both opt in
            transition(self.session, row, "contact_shared", actor_id=user.id)

        self.session.commit()
        return self._status(user, row)

    def withdraw(self, user: User, match_id: uuid.UUID) -> ContactStatus:
        """Undoes the caller's own opt-in, but only while the other party
        hasn't consented yet — mirrors the mockups' "withdraw before both
        agree" affordance, which the built app never had (docs/DECISIONS.md
        D-10.5). Once both sides have consented the share is complete;
        `row.state` never flipped to `contact_shared` for a one-sided
        opt-in, so there's no state to unwind here."""
        row = load_match(self.session, user, match_id)
        ensure_pair_active(self.session, row)

        status = self._status(user, row)
        if not status.you_consented:
            return status  # nothing to withdraw
        if status.other_consented:
            raise AlreadyMutuallyShared(match_id)

        existing = self.session.scalar(
            select(ContactShare).where(
                ContactShare.match_score_id == match_id, ContactShare.user_id == user.id
            )
        )
        if existing is not None:
            self.session.delete(existing)
            self.session.commit()

        return self._status(user, row)

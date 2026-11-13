"""Chat — REST polling, build plan §4 Phase 6 / PRD §9.1.

Transport-agnostic per CLAUDE.md: PII detection, moderation flagging and
persistence all live here, not in a transport handler. There is no
WebSocket handler in this codebase yet — REST polling is this phase's only
transport (PRD §9.1: "Transport: REST polling, not WebSockets"), with
WebSocket a documented later upgrade "once polling latency measurably
degrades the experience" (CLAUDE.md), not something this design forecloses.

A "thread" is not a separate entity: `message.match_score_id` already ties
every message to an unordered pair (Phase 1 schema), so PRD §8.2's "thread
created" transition (Mutual -> Chatting) is modelled as the state flip that
happens on first chat access, not a row insert.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from cohab.core.config import (
    CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN,
    CHAT_RATE_LIMIT_PER_THREAD_PER_MIN,
)
from cohab.core.crypto import decrypt_message_safe, encrypt_message
from cohab.models import ContactShare, MatchScore, Message, User
from cohab.services.match_access import MatchNotFound, NotAParty, PairBlocked, ensure_pair_active, load_match
from cohab.services.match_events import transition
from cohab.services.moderation import AbuseFlagger, KeywordAbuseFlagger
from cohab.services.pii import detect_pii

__all__ = [
    "ChatMessage",
    "ChatService",
    "MatchNotFound",
    "NotAParty",
    "PIIDetected",
    "PII_WARNING",
    "PairBlocked",
    "RateLimited",
    "ThreadNotOpen",
]

# PRD §8.2: a thread can only be used once the match has reached Mutual.
# "mutual" is the one state a thread can still be *opened from* (the flip to
# "chatting" IS the thread being created); the rest are already-open states.
_THREAD_OPENABLE_FROM = "mutual"
_THREAD_OPEN_STATES = {"chatting", "contact_shared", "cohabiting"}


class ChatError(Exception):
    """Base for chat-specific failures. `MatchNotFound`/`NotAParty` are the
    shared lookup+authorize errors from `match_access` — imported above,
    not redefined here, so `ChatService` and `ContactShareService` raise the
    identical exception classes (found in code review: two separate copies
    meant `api/chat.py` had to alias-import both to avoid a name clash)."""


class ThreadNotOpen(ChatError):
    """Match hasn't reached Mutual yet — PRD §9.1: "a thread cannot be
    opened from a one-sided expression of interest."""


class RateLimited(ChatError):
    pass


class PIIDetected(ChatError):
    """Not persisted — PRD §9.1 item 1's "interrupt," not a flag-and-send.
    `message` is the warning text to surface to the sender."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


PII_WARNING = (
    "You're about to share contact info — you can do this safely using "
    "Share Contact once you're both ready, instead of posting it here."
)


@dataclass(frozen=True)
class ChatMessage:
    id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime
    is_read: bool


def _open_thread(session: Session, row: MatchScore, actor_id: uuid.UUID) -> None:
    if row.state == _THREAD_OPENABLE_FROM:
        # PRD §8.2: Mutual -> Chatting, thread created
        transition(session, row, "chatting", actor_id=actor_id)
    elif row.state not in _THREAD_OPEN_STATES:
        raise ThreadNotOpen(row.id)


def _fully_contact_shared(session: Session, match_id: uuid.UUID) -> bool:
    count = session.scalar(
        select(func.count()).select_from(ContactShare).where(ContactShare.match_score_id == match_id)
    )
    return (count or 0) >= 2


class ChatService:
    def __init__(self, session: Session, abuse_flagger: AbuseFlagger | None = None) -> None:
        self.session = session
        self.abuse_flagger = abuse_flagger or KeywordAbuseFlagger()

    def _recent_count(
        self, *, since: datetime, sender_id: uuid.UUID | None, match_id: uuid.UUID | None
    ) -> int:
        stmt = select(func.count()).select_from(Message).where(Message.created_at >= since)
        if sender_id is not None:
            stmt = stmt.where(Message.sender_id == sender_id)
        if match_id is not None:
            stmt = stmt.where(Message.match_score_id == match_id)
        return self.session.scalar(stmt) or 0

    def send_message(
        self, sender: User, match_id: uuid.UUID, body: str, confirm: bool = False
    ) -> ChatMessage:
        row = load_match(self.session, sender, match_id)
        ensure_pair_active(self.session, row)
        _open_thread(self.session, row, sender.id)

        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        if (
            self._recent_count(since=window_start, sender_id=sender.id, match_id=None)
            >= CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN
        ):
            raise RateLimited("too many messages sent recently — slow down")
        if (
            self._recent_count(since=window_start, sender_id=None, match_id=match_id)
            >= CHAT_RATE_LIMIT_PER_THREAD_PER_MIN
        ):
            raise RateLimited("this conversation is moving too fast — slow down")

        pii_hit = detect_pii(body)
        if pii_hit and not confirm and not _fully_contact_shared(self.session, match_id):
            raise PIIDetected(PII_WARNING)

        message = Message(
            match_score_id=match_id,
            sender_id=sender.id,
            body_encrypted=encrypt_message(body),
            flagged=self.abuse_flagger.flag(body),
            pii_detected=pii_hit,
            is_read=False,
        )
        self.session.add(message)
        if row.first_messaged_at is None:
            row.first_messaged_at = datetime.now(timezone.utc)
        self.session.commit()
        return ChatMessage(
            id=message.id,
            sender_id=message.sender_id,
            body=body,
            created_at=message.created_at,
            is_read=message.is_read,
        )

    def mark_read(self, reader: User, match_id: uuid.UUID, up_to: datetime | None = None) -> int:
        """Explicit read receipt: mark the other party's messages up to
        `up_to` (default: all) as read. Returns how many changed."""
        row = load_match(self.session, reader, match_id)
        ensure_pair_active(self.session, row)
        if row.state not in _THREAD_OPEN_STATES:
            raise ThreadNotOpen(row.id)
        stmt = (
            update(Message)
            .where(
                Message.match_score_id == match_id,
                Message.sender_id != reader.id,
                Message.is_read.is_(False),
            )
            .values(is_read=True)
        )
        if up_to is not None:
            stmt = stmt.where(Message.created_at <= up_to)
        changed = self.session.execute(stmt).rowcount or 0
        self.session.commit()
        return changed

    def list_messages(
        self, reader: User, match_id: uuid.UUID, since: datetime | None = None
    ) -> list[ChatMessage]:
        row = load_match(self.session, reader, match_id)
        ensure_pair_active(self.session, row)
        _open_thread(self.session, row, reader.id)

        stmt = select(Message).where(Message.match_score_id == match_id).order_by(Message.created_at)
        if since is not None:
            stmt = stmt.where(Message.created_at > since)
        messages = list(self.session.scalars(stmt).all())
        # v2 W1: reading is side-effect free. v1 marked every message read
        # and committed on every poll, so a background tab "read" messages
        # nobody looked at. The client now calls `mark_read` explicitly.
        # The only write left here is the Mutual -> Chatting transition.
        if self.session.new or self.session.dirty:
            self.session.commit()

        return [
            ChatMessage(
                id=m.id,
                sender_id=m.sender_id,
                body=decrypt_message_safe(m.body_encrypted),
                created_at=m.created_at,
                is_read=m.is_read,
            )
            for m in messages
        ]

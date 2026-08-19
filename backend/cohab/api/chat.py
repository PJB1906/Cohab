"""GET/POST /chat/{match_id}/messages, /contact-status, /contact-share —
build plan §4 Phase 6.

Thin per CLAUDE.md: validate, call `ChatService`/`ContactShareService`,
serialise. The PII interrupt is the one response shape worth spelling out —
it's a 422 with a stable `detail` code so the frontend can render a specific
dialog rather than a generic error toast.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_db, require_verified_user
from cohab.api.schemas import ContactStatusOut, MessageOut, SendMessageRequest
from cohab.models import User
from cohab.services.chat import ChatMessage, ChatService, PIIDetected, RateLimited, ThreadNotOpen
from cohab.services.contact_share import ChatNotOpenYet, ContactShareService
from cohab.services.match_access import MatchNotFound, NotAParty, PairBlocked

router = APIRouter(prefix="/chat", tags=["chat"])


def _to_message_out(m: ChatMessage) -> MessageOut:
    return MessageOut(id=m.id, sender_id=m.sender_id, body=m.body, created_at=m.created_at, is_read=m.is_read)


@router.get("/{match_id}/messages", response_model=list[MessageOut])
def list_messages(
    match_id: uuid.UUID,
    since: datetime | None = None,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> list[MessageOut]:
    try:
        messages = ChatService(db).list_messages(user, match_id, since=since)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this conversation is not available")
    except ThreadNotOpen:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "chat isn't open for this match yet")
    return [_to_message_out(m) for m in messages]


@router.post("/{match_id}/messages", response_model=MessageOut)
def send_message(
    match_id: uuid.UUID,
    body: SendMessageRequest,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    try:
        message = ChatService(db).send_message(user, match_id, body.body, confirm=body.confirm)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this conversation is not available")
    except ThreadNotOpen:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "chat isn't open for this match yet")
    except RateLimited as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc))
    except PIIDetected as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            {"detail": "pii_detected", "message": exc.message},
        )
    return _to_message_out(message)


@router.get("/{match_id}/contact-status", response_model=ContactStatusOut)
def get_contact_status(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> ContactStatusOut:
    try:
        status_ = ContactShareService(db).get_status(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this conversation is not available")
    return ContactStatusOut(**status_.__dict__)


@router.post("/{match_id}/contact-share", response_model=ContactStatusOut)
def share_contact(
    match_id: uuid.UUID,
    user: User = Depends(require_verified_user),
    db: Session = Depends(get_db),
) -> ContactStatusOut:
    try:
        status_ = ContactShareService(db).opt_in(user, match_id)
    except MatchNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such match")
    except NotAParty:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a party to this match")
    except PairBlocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this conversation is not available")
    except ChatNotOpenYet:
        raise HTTPException(status.HTTP_409_CONFLICT, "open chat with this match before sharing contact")
    return ContactStatusOut(**status_.__dict__)

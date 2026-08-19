"""FastAPI dependencies — the one layer allowed to know about `Request`/
cookies/HTTP status codes (CLAUDE.md: services stay framework-free)."""

from __future__ import annotations

from typing import Generator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from sqlalchemy import select

from cohab.core.config import SESSION_COOKIE_NAME
from cohab.core.security import decode_session_token
from cohab.db import SessionLocal
from cohab.models import User, WeightSet
from cohab.services.matching.text import TfidfSimilarity


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    user_id = decode_session_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    return user


def require_verified_user(user: User = Depends(get_current_user)) -> User:
    if user.account_status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is not active")
    if user.verification_status != "verified":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account is not verified")
    return user


def require_moderator(user: User = Depends(require_verified_user)) -> User:
    """Phase 7 (docs/DECISIONS.md D-7.1): moderator auth is a flag on the
    caller's own account, reusing the same session cookie — no second login
    flow. Gates every `/moderation/*` route."""
    if not user.is_moderator:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "moderator access required")
    return user


def get_text_encoder(request: Request) -> TfidfSimilarity:
    """The vectorizer fit once at app startup (`main.py`) over the DB's
    corpus at that moment — transform-only from here on (CLAUDE.md: never
    encode inside the match request path)."""
    return request.app.state.text_encoder


def get_active_weight_set(db: Session = Depends(get_db)) -> WeightSet:
    weight_set = db.scalar(select(WeightSet).where(WeightSet.is_active.is_(True)))
    if weight_set is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "no active weight_set configured")
    return weight_set

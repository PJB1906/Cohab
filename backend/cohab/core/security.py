"""Password hashing, session tokens and OTP hashing — Phase 4.

Two different hashing primitives, deliberately: `bcrypt` (slow, salted) for
passwords, which are long-lived credentials worth defending against an
offline dictionary attack on a stolen hash; HMAC-SHA256 for OTPs, which are
6-digit, single-use and expire in minutes — `OTP_MAX_ATTEMPTS` is the actual
defence against guessing, not hash cost.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from cohab.core.config import OTP_LENGTH, SECRET_KEY, SESSION_TTL_DAYS

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_session_token(user_id: uuid.UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_session_token(token: str) -> uuid.UUID | None:
    """None for any invalid/expired/malformed token — the caller (an
    authentication dependency) turns that into a 401, not an exception."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


def generate_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


def hash_otp(code: str) -> str:
    return hmac.new(SECRET_KEY.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp_hash(code: str, otp_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), otp_hash)

"""Chat message encryption at rest — Phase 6.

PRD §10: "Chat is encrypted at rest under a server-held key, and is not
end-to-end encrypted." `Fernet` (symmetric, authenticated) keyed by a digest
of `SECRET_KEY` — the same server-held secret `core/security.py` already
uses for session JWTs and OTP hashing (D-4.5's reasoning applies here too:
one secret, no separate key-management infra for a pilot).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from cohab.core.config import SECRET_KEY


def _fernet() -> Fernet:
    # Fernet requires a 32-byte, urlsafe-base64-encoded key; SECRET_KEY is an
    # arbitrary-length string, so derive a fixed-size key from it.
    digest = hashlib.sha256(SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_message(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_message(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        raise ValueError("cannot decrypt message — wrong key or corrupted token")

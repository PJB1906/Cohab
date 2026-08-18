"""Password hashing, session tokens, OTP hashing — pure functions, no DB."""

import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from cohab.core import config
from cohab.core.security import (
    JWT_ALGORITHM,
    create_session_token,
    decode_session_token,
    generate_otp,
    hash_otp,
    hash_password,
    verify_otp_hash,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_password_hash_is_salted() -> None:
    # Same password, two hashes — must differ (bcrypt salts per call).
    assert hash_password("same password") != hash_password("same password")


def test_session_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_session_token(user_id)
    assert decode_session_token(token) == user_id


def test_session_token_rejects_garbage() -> None:
    assert decode_session_token("not-a-jwt") is None


def test_session_token_rejects_expired() -> None:
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
        config.SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    assert decode_session_token(expired) is None


def test_session_token_rejects_wrong_signature() -> None:
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        "a different secret entirely",
        algorithm=JWT_ALGORITHM,
    )
    assert decode_session_token(forged) is None


def test_generate_otp_is_numeric_and_fixed_length() -> None:
    code = generate_otp()
    assert len(code) == config.OTP_LENGTH
    assert code.isdigit()


def test_otp_hash_roundtrip() -> None:
    code = generate_otp()
    hashed = hash_otp(code)
    assert verify_otp_hash(code, hashed)
    assert not verify_otp_hash("000000" if code != "000000" else "111111", hashed)

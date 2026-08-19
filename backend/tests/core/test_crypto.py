"""Chat message encryption — pure functions, no DB."""

import pytest

from cohab.core.crypto import decrypt_message, encrypt_message


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "hey, when are you free to see the place?"
    token = encrypt_message(plaintext)
    assert token != plaintext
    assert decrypt_message(token) == plaintext


def test_decrypt_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        decrypt_message("not-a-real-token")

"""Forgot-password flow and "keep me logged in" (docs/DECISIONS.md D-14.27)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from cohab.core.config import SESSION_COOKIE_NAME
from cohab.models import Institution

PASSWORD = "correct horse battery staple"


def _email(institution: Institution) -> str:
    return f"asha@{institution.email_domain}"


def _codes(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.args[1] for r in caplog.records if r.name == "cohab.otp"]


def _verified_user(client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={"email": _email(institution), "password": PASSWORD, "full_name": "Asha Rao",
                  "gender": "female", "seeker_type": "needs_place"},
        )
    assert resp.status_code == 201, resp.text
    code = _codes(caplog)[-1]
    assert client.post("/auth/verify", json={"user_id": resp.json()["user_id"], "code": code}).status_code == 200
    client.cookies.clear()
    caplog.clear()


def _age_code(db_session, institution: Institution, seconds: int = 120) -> None:
    """Move the issued code back in time past the resend cooldown."""
    from datetime import timedelta
    from sqlalchemy import select
    from cohab.models import User, VerificationRecord
    user = db_session.scalar(select(User).where(User.email == _email(institution)))
    rec = db_session.scalar(select(VerificationRecord).where(VerificationRecord.user_id == user.id))
    rec.otp_expires_at = rec.otp_expires_at - timedelta(seconds=seconds)
    db_session.commit()


def test_reset_sets_new_password_and_logs_in(client: TestClient, institution: Institution, caplog) -> None:
    _verified_user(client, institution, caplog)
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        assert client.post("/auth/password-reset/request", json={"email": _email(institution)}).status_code == 202
    code = _codes(caplog)[-1]

    resp = client.post(
        "/auth/password-reset/confirm",
        json={"email": _email(institution), "code": code, "new_password": "a brand new password"},
    )
    assert resp.status_code == 200, resp.text
    assert SESSION_COOKIE_NAME in resp.cookies

    client.cookies.clear()
    assert client.post("/auth/login", json={"email": _email(institution), "password": PASSWORD}).status_code == 401
    assert client.post("/auth/login", json={"email": _email(institution), "password": "a brand new password"}).status_code == 200


def test_unknown_email_gets_the_same_answer_and_no_email(client: TestClient, institution: Institution, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post("/auth/password-reset/request", json={"email": f"nobody@{institution.email_domain}"})
    assert resp.status_code == 202
    assert _codes(caplog) == []


def test_wrong_code_is_rejected_and_counted(client: TestClient, institution: Institution, caplog) -> None:
    _verified_user(client, institution, caplog)
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        client.post("/auth/password-reset/request", json={"email": _email(institution)})
    real = _codes(caplog)[-1]
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(5):
        r = client.post("/auth/password-reset/confirm", json={"email": _email(institution), "code": wrong, "new_password": "whatever123"})
        assert r.status_code == 400
    # attempts exhausted: even the right code is refused now
    r = client.post("/auth/password-reset/confirm", json={"email": _email(institution), "code": real, "new_password": "whatever123"})
    assert r.status_code == 429
    assert client.post("/auth/login", json={"email": _email(institution), "password": PASSWORD}).status_code == 200


def test_second_request_inside_cooldown_is_refused(client: TestClient, institution: Institution, caplog, db_session) -> None:
    _verified_user(client, institution, caplog)
    assert client.post("/auth/password-reset/request", json={"email": _email(institution)}).status_code == 202
    assert client.post("/auth/password-reset/request", json={"email": _email(institution)}).status_code == 429
    _age_code(db_session, institution)
    assert client.post("/auth/password-reset/request", json={"email": _email(institution)}).status_code == 202


def test_remember_controls_cookie_lifetime(client: TestClient, institution: Institution, caplog) -> None:
    _verified_user(client, institution, caplog)
    kept = client.post("/auth/login", json={"email": _email(institution), "password": PASSWORD, "remember": True})
    assert "max-age" in kept.headers["set-cookie"].lower()
    client.cookies.clear()
    session_only = client.post("/auth/login", json={"email": _email(institution), "password": PASSWORD, "remember": False})
    assert session_only.status_code == 200
    assert "max-age" not in session_only.headers["set-cookie"].lower()

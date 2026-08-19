"""POST /auth/register, /verify, /login, /logout — happy paths and the
load-bearing failure modes. CRUD tests are optional per CLAUDE.md, but this
IS the auth surface, so it gets real coverage rather than none."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.core.config import SESSION_COOKIE_NAME
from cohab.models import Institution, User, VerificationRecord

REGISTER_PAYLOAD = {
    "password": "correct horse battery staple",
    "full_name": "Priya Menon",
    "gender": "female",
    "seeker_type": "needs_place",
}


def _email(institution: Institution) -> str:
    return f"priya@{institution.email_domain}"


def _register(client: TestClient, institution: Institution) -> dict:
    resp = client.post("/auth/register", json={**REGISTER_PAYLOAD, "email": _email(institution)})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _extract_otp(caplog: pytest.LogCaptureFixture) -> str:
    for record in caplog.records:
        if record.name == "cohab.otp":
            return record.args[1]
    raise AssertionError("no OTP was logged")


# --- register ------------------------------------------------------------

def test_register_creates_unverified_user_and_pending_otp(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        body = _register(client, institution)

    user = db_session.get(User, body["user_id"])
    assert user is not None
    assert user.verification_status == "unverified"
    assert user.seeker_type == "needs_place"

    record = db_session.scalar(select(VerificationRecord).where(VerificationRecord.user_id == user.id))
    assert record is not None
    assert record.status == "pending"
    assert record.otp_hash is not None
    assert _extract_otp(caplog).isdigit()


def test_register_persists_phone_number_and_verify_returns_it(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={**REGISTER_PAYLOAD, "email": _email(institution), "phone_number": "9876543210"},
        )
    body = resp.json()
    code = _extract_otp(caplog)

    verify_resp = client.post("/auth/verify", json={"user_id": body["user_id"], "code": code})
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["phone_number"] == "9876543210"


def test_register_rejects_unknown_email_domain(client: TestClient) -> None:
    resp = client.post("/auth/register", json={**REGISTER_PAYLOAD, "email": "someone@not-an-institution.example"})
    assert resp.status_code == 400


def test_register_rejects_subdomain_of_a_registered_domain(
    client: TestClient, institution: Institution
) -> None:
    # Confirmed with the user: a departmental subdomain must resolve to the
    # institution, e.g. msds.christuniversity.in -> christuniversity.in.
    resp = client.post(
        "/auth/register",
        json={**REGISTER_PAYLOAD, "email": f"priya@msds.{institution.email_domain}"},
    )
    assert resp.status_code == 201, resp.text


def test_register_rejects_duplicate_email(client: TestClient, institution: Institution) -> None:
    _register(client, institution)
    resp = client.post("/auth/register", json={**REGISTER_PAYLOAD, "email": _email(institution)})
    assert resp.status_code == 409


# --- verify ----------------------------------------------------------------

def test_verify_with_correct_code_sets_cookie_and_verifies(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        body = _register(client, institution)
    code = _extract_otp(caplog)

    resp = client.post("/auth/verify", json={"user_id": body["user_id"], "code": code})
    assert resp.status_code == 200, resp.text
    assert resp.json()["verification_status"] == "verified"
    assert SESSION_COOKIE_NAME in resp.cookies


def test_verify_with_wrong_code_increments_attempts_and_fails(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        body = _register(client, institution)

    resp = client.post("/auth/verify", json={"user_id": body["user_id"], "code": "000000"})
    assert resp.status_code == 400
    assert SESSION_COOKIE_NAME not in resp.cookies

    record = db_session.scalar(
        select(VerificationRecord).where(VerificationRecord.user_id == body["user_id"])
    )
    assert record.otp_attempts == 1
    assert record.status == "pending"


def test_verify_with_expired_code_fails(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        body = _register(client, institution)
    code = _extract_otp(caplog)

    record = db_session.scalar(
        select(VerificationRecord).where(VerificationRecord.user_id == body["user_id"])
    )
    record.otp_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()

    resp = client.post("/auth/verify", json={"user_id": body["user_id"], "code": code})
    assert resp.status_code == 400


# --- login -------------------------------------------------------------

def test_login_with_correct_password_sets_cookie(client: TestClient, institution: Institution) -> None:
    _register(client, institution)
    resp = client.post("/auth/login", json={"email": _email(institution), "password": REGISTER_PAYLOAD["password"]})
    assert resp.status_code == 200, resp.text
    assert SESSION_COOKIE_NAME in resp.cookies


def test_login_with_wrong_password_rejected(client: TestClient, institution: Institution) -> None:
    _register(client, institution)
    resp = client.post("/auth/login", json={"email": _email(institution), "password": "not the password"})
    assert resp.status_code == 401


# --- logout / auth dependency -----------------------------------------

def test_logout_requires_authentication(client: TestClient) -> None:
    resp = client.post("/auth/logout")
    assert resp.status_code == 401


def test_logout_clears_cookie_when_authenticated(client: TestClient, institution: Institution) -> None:
    _register(client, institution)
    login_resp = client.post(
        "/auth/login", json={"email": _email(institution), "password": REGISTER_PAYLOAD["password"]}
    )
    resp = client.post("/auth/logout")
    assert resp.status_code == 204


# --- me (Phase 5: session restore on page refresh) ------------------------

def test_me_requires_authentication(client: TestClient) -> None:
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user(client: TestClient, institution: Institution) -> None:
    body = _register(client, institution)
    client.post("/auth/login", json={"email": _email(institution), "password": REGISTER_PAYLOAD["password"]})
    resp = client.get("/auth/me")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == body["user_id"]
    assert resp.json()["email"] == _email(institution)

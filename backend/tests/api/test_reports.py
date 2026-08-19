"""POST /reports, POST/DELETE/GET /blocks — build plan §4 Phase 7, PRD
§8.3 / §10."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.core.config import REPORT_AUTOSUSPEND_THRESHOLD, REPORT_RATE_LIMIT_PER_DAY
from cohab.models import Institution, Report, User, UserBlock

PASSWORD = "correct horse battery staple"


def _onboard(
    client: TestClient,
    institution: Institution,
    caplog: pytest.LogCaptureFixture,
    *,
    name: str,
    email_local: str,
) -> str:
    email = f"{email_local}@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": name,
                "gender": "female",
                "seeker_type": "needs_place",
            },
        )
    user_id = resp.json()["user_id"]
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    caplog.clear()
    client.post("/auth/verify", json={"user_id": user_id, "code": code})
    return user_id


def _login(client: TestClient, email: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


@pytest.fixture()
def two_users(client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture) -> tuple[str, str]:
    """(asha_id, bala_id); client logged in as Asha."""
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala")
    _login(client, f"asha@{institution.email_domain}")
    return asha_id, bala_id


# --- reports -----------------------------------------------------------


def test_file_report_happy_path(client: TestClient, two_users: tuple[str, str]) -> None:
    _, bala_id = two_users
    resp = client.post(
        "/reports", json={"reported_user_id": bala_id, "reason": "spam", "details": "kept messaging strangers"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "open"
    assert body["escalated"] is False


def test_cannot_report_self(client: TestClient, two_users: tuple[str, str]) -> None:
    asha_id, _ = two_users
    resp = client.post("/reports", json={"reported_user_id": asha_id, "reason": "spam", "details": None})
    assert resp.status_code == 400


def test_report_nonexistent_user_404s(client: TestClient, two_users: tuple[str, str]) -> None:
    resp = client.post(
        "/reports",
        json={"reported_user_id": "00000000-0000-0000-0000-000000000000", "reason": "spam", "details": None},
    )
    assert resp.status_code == 404


def test_duplicate_report_collapses_into_one_case(
    client: TestClient, db_session: Session, two_users: tuple[str, str]
) -> None:
    """PRD §8.3: "repeated reports by one user against the same person
    collapse into a single case" — not a second row."""
    asha_id, bala_id = two_users
    first = client.post("/reports", json={"reported_user_id": bala_id, "reason": "spam", "details": "first"})
    second = client.post(
        "/reports", json={"reported_user_id": bala_id, "reason": "inappropriate_behaviour", "details": "second"}
    )
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    rows = db_session.scalars(
        select(Report).where(Report.reporter_id == asha_id, Report.reported_user_id == bala_id)
    ).all()
    assert len(rows) == 1
    assert rows[0].reason == "inappropriate_behaviour"
    assert rows[0].details == "second"


def test_rate_limit_trips_after_daily_cap(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, two_users: tuple[str, str]
) -> None:
    # Distinct targets so none of these collapse into a duplicate — each
    # must be a genuinely new case to consume the daily cap.
    targets = [
        _onboard(client, institution, caplog, name=f"Target{i}", email_local=f"target{i}")
        for i in range(REPORT_RATE_LIMIT_PER_DAY)
    ]
    _login(client, f"asha@{institution.email_domain}")
    for target_id in targets:
        resp = client.post("/reports", json={"reported_user_id": target_id, "reason": "spam", "details": None})
        assert resp.status_code == 201, resp.text

    one_more = _onboard(client, institution, caplog, name="OneMore", email_local="onemore")
    _login(client, f"asha@{institution.email_domain}")
    over_limit = client.post("/reports", json={"reported_user_id": one_more, "reason": "spam", "details": None})
    assert over_limit.status_code == 429


def test_escalating_reason_suspends_reported_user_immediately(
    client: TestClient, db_session: Session, two_users: tuple[str, str]
) -> None:
    """PRD §8.3: "Reports alleging threats or sexual harassment escalate
    immediately and may suspend pending review.\""""
    _, bala_id = two_users
    resp = client.post("/reports", json={"reported_user_id": bala_id, "reason": "threats", "details": None})
    assert resp.status_code == 201, resp.text
    assert resp.json()["escalated"] is True

    bala = db_session.get(User, bala_id)
    db_session.refresh(bala)
    assert bala.account_status == "suspended"


def test_three_distinct_reporters_autosuspend(
    client: TestClient,
    institution: Institution,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    two_users: tuple[str, str],
) -> None:
    """PRD §8.3: "Three or more independent reports from unconnected users
    trigger automatic temporary suspension.\""""
    _, bala_id = two_users

    reporters = [f"asha@{institution.email_domain}"]
    for i in range(REPORT_AUTOSUSPEND_THRESHOLD - 1):
        _onboard(client, institution, caplog, name=f"Reporter{i}", email_local=f"reporter{i}")
        reporters.append(f"reporter{i}@{institution.email_domain}")
    assert len(reporters) == REPORT_AUTOSUSPEND_THRESHOLD

    for i, email in enumerate(reporters):
        _login(client, email)
        resp = client.post(
            "/reports", json={"reported_user_id": bala_id, "reason": "spam", "details": f"report {i}"}
        )
        assert resp.status_code == 201, resp.text

    bala = db_session.get(User, bala_id)
    db_session.refresh(bala)
    assert bala.account_status == "suspended"


# --- blocks --------------------------------------------------------------


def test_block_then_list(client: TestClient, two_users: tuple[str, str]) -> None:
    _, bala_id = two_users
    resp = client.post("/blocks", json={"blocked_id": bala_id})
    assert resp.status_code == 204, resp.text

    listed = client.get("/blocks")
    assert listed.status_code == 200
    body = listed.json()
    assert [b["id"] for b in body] == [bala_id]
    assert body[0]["full_name"] == "Bala"


def test_cannot_block_self(client: TestClient, two_users: tuple[str, str]) -> None:
    asha_id, _ = two_users
    resp = client.post("/blocks", json={"blocked_id": asha_id})
    assert resp.status_code == 400


def test_unblock_only_works_for_the_blocker(
    client: TestClient, institution: Institution, db_session: Session, two_users: tuple[str, str]
) -> None:
    """PRD §10: blocking "cannot be undone by the blocked party." There's no
    endpoint shape that lets Bala remove Asha's block of her — `DELETE
    /blocks/{id}` only ever deletes *the caller's own* block of `{id}` — so
    this proves that attempt is a no-op, not merely unauthorized."""
    asha_id, bala_id = two_users
    client.post("/blocks", json={"blocked_id": bala_id})

    _login(client, f"bala@{institution.email_domain}")
    resp = client.delete(f"/blocks/{asha_id}")
    assert resp.status_code == 204
    still_blocked = db_session.scalar(
        select(UserBlock).where(UserBlock.blocker_id == asha_id, UserBlock.blocked_id == bala_id)
    )
    assert still_blocked is not None

    _login(client, f"asha@{institution.email_domain}")
    resp = client.delete(f"/blocks/{bala_id}")
    assert resp.status_code == 204
    gone = db_session.scalar(
        select(UserBlock).where(UserBlock.blocker_id == asha_id, UserBlock.blocked_id == bala_id)
    )
    assert gone is None
    assert client.get("/blocks").json() == []

"""GET/POST /chat/{match_id}/messages — build plan §4 Phase 6, PRD §9.1."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.core.config import CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN
from cohab.models import Institution, MatchScore, Message, WeightSet

PASSWORD = "correct horse battery staple"

ANSWERS = {
    "cleanliness_level": "very_tidy",
    "sleep_schedule": "early",
    "guest_tolerance": "anytime",
    "guest_frequency": "rarely",
    "payment_reliability": "early",
    "communication_style": "direct_now",
}


def _onboard(
    client: TestClient,
    institution: Institution,
    caplog: pytest.LogCaptureFixture,
    *,
    name: str,
    email_local: str,
    phone_number: str | None = None,
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
                "phone_number": phone_number,
            },
        )
    user_id = resp.json()["user_id"]
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    caplog.clear()

    client.post("/auth/verify", json={"user_id": user_id, "code": code})
    profile_resp = client.put(
        "/profile",
        json={
            "city": "Bangalore",
            "budget_min": 10000,
            "budget_max": 15000,
            "move_in_date": "2026-09-01",
            "gender_preference": "any",
            "questionnaire": ANSWERS,
            "important_attributes": [],
        },
    )
    assert profile_resp.status_code == 200, profile_resp.text
    return user_id


def _login(client: TestClient, email: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


@pytest.fixture()
def mutual_pair(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> tuple[str, str, str]:
    """Returns (asha_id, bala_id, match_id) with both sides `interested`,
    state `mutual`, and the client logged in as Asha."""
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha", phone_number="9876543210")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala", phone_number="9876500000")

    _login(client, f"asha@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_id = next(m["match_id"] for m in matches if m["candidate_id"] == bala_id)
    client.post(f"/matches/{match_id}/interest")

    _login(client, f"bala@{institution.email_domain}")
    resp = client.post(f"/matches/{match_id}/interest")
    assert resp.json()["state"] == "mutual"

    _login(client, f"asha@{institution.email_domain}")
    return asha_id, bala_id, match_id


def test_messages_403_before_mutual(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> None:
    _onboard(client, institution, caplog, name="Asha", email_local="asha")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala")
    _login(client, f"asha@{institution.email_domain}")
    match_id = next(
        m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == bala_id
    )
    resp = client.get(f"/chat/{match_id}/messages")
    assert resp.status_code == 403


def test_first_access_opens_thread(
    client: TestClient, db_session: Session, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    resp = client.get(f"/chat/{match_id}/messages")
    assert resp.status_code == 200, resp.text
    assert resp.json() == []

    row = db_session.get(MatchScore, match_id)
    db_session.refresh(row)
    assert row.state == "chatting"  # PRD §8.2: Mutual -> Chatting


def test_send_and_list_message_roundtrip(client: TestClient, mutual_pair: tuple[str, str, str]) -> None:
    _, _, match_id = mutual_pair
    resp = client.post(f"/chat/{match_id}/messages", json={"body": "hey, when works for a call?"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["body"] == "hey, when works for a call?"
    assert resp.json()["is_read"] is False

    messages = client.get(f"/chat/{match_id}/messages").json()
    assert len(messages) == 1
    assert messages[0]["body"] == "hey, when works for a call?"


def test_recipient_fetch_marks_message_read(
    client: TestClient, institution: Institution, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    client.post(f"/chat/{match_id}/messages", json={"body": "you around this evening?"})

    _login(client, f"bala@{institution.email_domain}")
    messages = client.get(f"/chat/{match_id}/messages").json()
    assert messages[0]["is_read"] is True


def test_pii_message_is_interrupted_then_confirm_sends(
    client: TestClient, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    blocked = client.post(f"/chat/{match_id}/messages", json={"body": "call me on 9876543210"})
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["detail"]["detail"] == "pii_detected"
    assert client.get(f"/chat/{match_id}/messages").json() == []  # not persisted

    sent = client.post(
        f"/chat/{match_id}/messages", json={"body": "call me on 9876543210", "confirm": True}
    )
    assert sent.status_code == 200, sent.text
    assert len(client.get(f"/chat/{match_id}/messages").json()) == 1


def test_abusive_message_is_flagged_but_not_blocked(
    client: TestClient, db_session: Session, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    resp = client.post(f"/chat/{match_id}/messages", json={"body": "I'll kill you if you're late"})
    assert resp.status_code == 200, resp.text  # PRD §9.1 item 2: flag, don't block

    row = db_session.scalar(select(Message).where(Message.match_score_id == match_id))
    assert row.flagged is True


def test_non_party_cannot_read_or_send(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    _onboard(client, institution, caplog, name="Chitra", email_local="chitra")
    assert client.get(f"/chat/{match_id}/messages").status_code == 403
    assert client.post(f"/chat/{match_id}/messages", json={"body": "hi"}).status_code == 403


def test_blocked_pair_cannot_read_or_send(client: TestClient, mutual_pair: tuple[str, str, str]) -> None:
    """docs/DECISIONS.md D-7.5: PRD §10 — blocking "hides existing
    threads." Opens the thread first so there's something to hide."""
    _, bala_id, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")  # mutual -> chatting

    resp = client.post("/blocks", json={"blocked_id": bala_id})
    assert resp.status_code == 204, resp.text

    assert client.get(f"/chat/{match_id}/messages").status_code == 403
    assert client.post(f"/chat/{match_id}/messages", json={"body": "hi"}).status_code == 403


def test_account_rate_limit_trips(client: TestClient, mutual_pair: tuple[str, str, str]) -> None:
    _, _, match_id = mutual_pair
    for i in range(CHAT_RATE_LIMIT_PER_ACCOUNT_PER_MIN):
        resp = client.post(f"/chat/{match_id}/messages", json={"body": f"message number {i}"})
        assert resp.status_code == 200, resp.text
    over_limit = client.post(f"/chat/{match_id}/messages", json={"body": "one too many"})
    assert over_limit.status_code == 429

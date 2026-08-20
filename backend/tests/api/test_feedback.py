"""POST /matches/{id}/feedback, GET /feedback/pending — build plan §4 Phase 8,
PRD §8.2's lifecycle / §9 screen 12."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cohab.models import Institution, MatchScore, WeightSet

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
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, *, name: str, email_local: str
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
def paired(
    client: TestClient, institution: Institution, weight_set: WeightSet, db_session: Session, caplog: pytest.LogCaptureFixture
) -> tuple[str, str, str]:
    """(asha_id, bala_id, match_id), state "suggested", client logged in as
    Asha. Later lifecycle states are set directly on the row, same precedent
    as tests/api/test_matches.py's replay test — this suite is about
    FeedbackService, not re-driving the whole chat/contact-share flow."""
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala")

    _login(client, f"asha@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_id = next(m["match_id"] for m in matches if m["candidate_id"] == bala_id)
    return asha_id, bala_id, match_id


def _set_state(db_session: Session, match_id: str, state: str, cohabiting_since: datetime | None = None) -> MatchScore:
    row = db_session.get(MatchScore, match_id)
    row.state = state
    row.cohabiting_since = cohabiting_since
    db_session.commit()
    return row


def test_feedback_requires_authentication(client: TestClient) -> None:
    resp = client.post("/matches/00000000-0000-0000-0000-000000000000/feedback", json={"outcome": "not_pursued"})
    assert resp.status_code == 401


def test_feedback_404_for_nonexistent_match(client: TestClient, institution: Institution, paired: tuple[str, str, str]) -> None:
    resp = client.post("/matches/00000000-0000-0000-0000-000000000000/feedback", json={"outcome": "not_pursued"})
    assert resp.status_code == 404


def test_feedback_403_for_a_non_party(
    client: TestClient, institution: Institution, db_session: Session, caplog: pytest.LogCaptureFixture, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    _set_state(db_session, match_id, "rejected")
    _onboard(client, institution, caplog, name="Chitra", email_local="chitra")
    resp = client.post(f"/matches/{match_id}/feedback", json={"outcome": "not_pursued"})
    assert resp.status_code == 403


def test_feedback_409_when_match_not_yet_eligible(client: TestClient, institution: Institution, paired: tuple[str, str, str]) -> None:
    _, _, match_id = paired  # still "suggested"
    resp = client.post(f"/matches/{match_id}/feedback", json={"outcome": "not_pursued"})
    assert resp.status_code == 409, resp.text


def test_feedback_422_for_an_outcome_invalid_for_the_matchs_state(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    _set_state(db_session, match_id, "rejected")
    resp = client.post(f"/matches/{match_id}/feedback", json={"outcome": "still_together"})
    assert resp.status_code == 422, resp.text


def test_feedback_accepted_for_a_rejected_match(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    _set_state(db_session, match_id, "rejected")
    resp = client.post(f"/matches/{match_id}/feedback", json={"outcome": "incompatible"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["outcome"] == "incompatible"
    assert body["cohabitation_duration_days"] is None


def test_feedback_still_together_duration_is_computed_server_side(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    since = datetime.now(timezone.utc) - timedelta(days=45)
    _set_state(db_session, match_id, "cohabiting", cohabiting_since=since)

    # A client-supplied duration must be ignored for "still_together" — the
    # server derives it from cohabiting_since, never trusting the client here.
    resp = client.post(f"/matches/{match_id}/feedback", json={"outcome": "still_together", "cohabitation_duration_days": 9999})
    assert resp.status_code == 201, resp.text
    duration = resp.json()["cohabitation_duration_days"]
    assert 44 <= duration <= 46


def test_feedback_moved_out_uses_the_client_supplied_duration(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    since = datetime.now(timezone.utc) - timedelta(days=60)
    _set_state(db_session, match_id, "cohabiting", cohabiting_since=since)

    resp = client.post(f"/matches/{match_id}/feedback", json={"outcome": "moved_out", "cohabitation_duration_days": 21})
    assert resp.status_code == 201, resp.text
    assert resp.json()["cohabitation_duration_days"] == 21


def test_feedback_second_submission_by_the_same_user_conflicts(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    _set_state(db_session, match_id, "rejected")
    first = client.post(f"/matches/{match_id}/feedback", json={"outcome": "other"})
    assert first.status_code == 201, first.text

    second = client.post(f"/matches/{match_id}/feedback", json={"outcome": "incompatible"})
    assert second.status_code == 409, second.text


def test_feedback_each_party_can_submit_independently(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    asha_id, bala_id, match_id = paired
    _set_state(db_session, match_id, "rejected")

    resp_a = client.post(f"/matches/{match_id}/feedback", json={"outcome": "not_pursued"})
    assert resp_a.status_code == 201, resp_a.text

    _login(client, f"bala@{institution.email_domain}")
    resp_b = client.post(f"/matches/{match_id}/feedback", json={"outcome": "incompatible"})
    assert resp_b.status_code == 201, resp_b.text


def test_pending_feedback_lists_a_rejected_match_immediately(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, bala_id, match_id = paired
    _set_state(db_session, match_id, "rejected")

    resp = client.get("/feedback/pending")
    assert resp.status_code == 200, resp.text
    entries = resp.json()
    assert any(e["match_id"] == match_id for e in entries)


def test_pending_feedback_excludes_a_cohabiting_match_before_30_days(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    since = datetime.now(timezone.utc) - timedelta(days=10)
    _set_state(db_session, match_id, "cohabiting", cohabiting_since=since)

    resp = client.get("/feedback/pending")
    entries = resp.json()
    assert not any(e["match_id"] == match_id for e in entries)


def test_pending_feedback_includes_a_cohabiting_match_after_30_days(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    since = datetime.now(timezone.utc) - timedelta(days=31)
    _set_state(db_session, match_id, "cohabiting", cohabiting_since=since)

    resp = client.get("/feedback/pending")
    entries = resp.json()
    assert any(e["match_id"] == match_id for e in entries)


def test_pending_feedback_excludes_a_match_already_reported_by_the_caller(
    client: TestClient, institution: Institution, db_session: Session, paired: tuple[str, str, str]
) -> None:
    _, _, match_id = paired
    _set_state(db_session, match_id, "rejected")
    client.post(f"/matches/{match_id}/feedback", json={"outcome": "not_pursued"})

    resp = client.get("/feedback/pending")
    entries = resp.json()
    assert not any(e["match_id"] == match_id for e in entries)

"""POST/DELETE/GET /saved — bookmark a match to compare later.

New scope, not in COHAB_PRD.md/COHAB_MATCHING_SPEC.md (see services/saved.py).
Fixture/style follows tests/api/test_contact_share.py's `mutual_pair` — the
simplest fixture in this suite that yields a real `match_score` row without
needing the full matching-spec scenario setup.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cohab.models import Institution, WeightSet

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
def pair(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> tuple[str, str, str]:
    """(asha_id, bala_id, match_id): a real match_score row between two
    onboarded users, client logged in as Asha."""
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala")

    _login(client, f"asha@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_id = next(m["match_id"] for m in matches if m["candidate_id"] == bala_id)
    return asha_id, bala_id, match_id


def test_save_returns_match_card(client: TestClient, pair: tuple[str, str, str]) -> None:
    _, bala_id, match_id = pair
    resp = client.post(f"/saved/{match_id}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["candidate_id"] == bala_id
    assert body["match_id"] == match_id


def test_save_is_idempotent(client: TestClient, pair: tuple[str, str, str]) -> None:
    _, _, match_id = pair
    first = client.post(f"/saved/{match_id}")
    second = client.post(f"/saved/{match_id}")
    assert first.status_code == 200
    assert second.status_code == 200

    listed = client.get("/saved").json()
    assert len(listed) == 1


def test_unsave_is_idempotent(client: TestClient, pair: tuple[str, str, str]) -> None:
    _, _, match_id = pair
    client.post(f"/saved/{match_id}")

    first = client.delete(f"/saved/{match_id}")
    second = client.delete(f"/saved/{match_id}")
    assert first.status_code == 204
    assert second.status_code == 204

    assert client.get("/saved").json() == []


def test_unsave_never_saved_is_a_no_op(client: TestClient, pair: tuple[str, str, str]) -> None:
    _, _, match_id = pair
    resp = client.delete(f"/saved/{match_id}")
    assert resp.status_code == 204


def test_save_nonexistent_match_is_404(client: TestClient, pair: tuple[str, str, str]) -> None:
    resp = client.post(f"/saved/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_save_match_not_a_party_to_is_403(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, pair: tuple[str, str, str]
) -> None:
    _, _, match_id = pair
    _onboard(client, institution, caplog, name="Chitra", email_local="chitra")
    # `_onboard` leaves the client logged in as Chitra, who is not a party
    # to Asha/Bala's match.
    resp = client.post(f"/saved/{match_id}")
    assert resp.status_code == 403


def test_list_ordered_newest_first(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> None:
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala")
    chitra_id = _onboard(client, institution, caplog, name="Chitra", email_local="chitra")

    _login(client, f"asha@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_bala = next(m["match_id"] for m in matches if m["candidate_id"] == bala_id)
    match_chitra = next(m["match_id"] for m in matches if m["candidate_id"] == chitra_id)

    client.post(f"/saved/{match_bala}")
    client.post(f"/saved/{match_chitra}")

    listed = client.get("/saved").json()
    assert [row["match"]["match_id"] for row in listed] == [match_chitra, match_bala]
    assert "saved_at" in listed[0]


def test_list_only_returns_callers_own_saves(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> None:
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala")
    _onboard(client, institution, caplog, name="Chitra", email_local="chitra")

    _login(client, f"asha@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_bala = next(m["match_id"] for m in matches if m["candidate_id"] == bala_id)
    client.post(f"/saved/{match_bala}")

    _login(client, f"chitra@{institution.email_domain}")
    assert client.get("/saved").json() == []

    _login(client, f"bala@{institution.email_domain}")
    # Bala is a party to the same match_score row but never saved it.
    assert client.get("/saved").json() == []

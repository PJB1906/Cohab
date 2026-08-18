"""GET /profile, PUT /profile — happy path plus the load-bearing failure
modes. Registers+verifies a user first since profile save requires login."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import Institution, PreferenceProfile, UserAttributeWeight

REGISTER_PAYLOAD = {
    "password": "correct horse battery staple",
    "full_name": "Priya Menon",
    "gender": "female",
    "seeker_type": "needs_place",
}

VALID_PROFILE = {
    "city": "Bangalore",
    "budget_min": 10000,
    "budget_max": 15000,
    "move_in_date": "2026-09-01",
    "gender_preference": "any",
    "questionnaire": {"lifestyle_notes": "quiet, tidy, working on my thesis"},
    "important_attributes": ["cleanliness_level", "sleep_schedule"],
}


def _logged_in_client(client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture) -> None:
    email = f"priya@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post("/auth/register", json={**REGISTER_PAYLOAD, "email": email})
    user_id = resp.json()["user_id"]
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    client.post("/auth/verify", json={"user_id": user_id, "code": code})
    return user_id


def test_get_profile_before_save_is_404(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _logged_in_client(client, institution, caplog)
    resp = client.get("/profile")
    assert resp.status_code == 404


def test_put_profile_requires_login(client: TestClient) -> None:
    resp = client.put("/profile", json=VALID_PROFILE)
    assert resp.status_code == 401


def test_put_profile_persists_and_computes_text_vector(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _logged_in_client(client, institution, caplog)

    resp = client.put("/profile", json=VALID_PROFILE)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["city"] == "Bangalore"
    assert sorted(body["important_attributes"]) == sorted(VALID_PROFILE["important_attributes"])

    profile = db_session.scalar(select(PreferenceProfile).where(PreferenceProfile.user_id == user_id))
    assert profile is not None
    assert profile.text_vector is not None
    assert profile.text_vector_kind == "tfidf"

    weights = db_session.scalars(
        select(UserAttributeWeight).where(UserAttributeWeight.user_id == user_id)
    ).all()
    assert {w.attribute_name for w in weights} == set(VALID_PROFILE["important_attributes"])


def test_put_profile_rejects_budget_min_above_max(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _logged_in_client(client, institution, caplog)
    bad = {**VALID_PROFILE, "budget_min": 20000, "budget_max": 10000}
    resp = client.put("/profile", json=bad)
    assert resp.status_code == 422


def test_put_profile_rejects_unknown_important_attribute(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _logged_in_client(client, institution, caplog)
    bad = {**VALID_PROFILE, "important_attributes": ["not_a_real_attribute"]}
    resp = client.put("/profile", json=bad)
    assert resp.status_code == 400


def test_put_profile_rejects_unknown_questionnaire_key(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _logged_in_client(client, institution, caplog)
    bad = {**VALID_PROFILE, "questionnaire": {"not_a_real_question": "x"}}
    resp = client.put("/profile", json=bad)
    assert resp.status_code == 422


def test_put_profile_twice_updates_rather_than_duplicates(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _logged_in_client(client, institution, caplog)
    client.put("/profile", json=VALID_PROFILE)
    resp = client.put("/profile", json={**VALID_PROFILE, "city": "Chennai"})
    assert resp.status_code == 200

    profiles = db_session.scalars(
        select(PreferenceProfile).where(PreferenceProfile.user_id == user_id)
    ).all()
    assert len(profiles) == 1
    assert profiles[0].city == "Chennai"

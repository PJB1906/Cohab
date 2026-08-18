"""GET /matches, GET /matches/{id}/explanation — end-to-end through the real
matcher (EligibilityFilter, CompatibilityMatcher, MatchRanker), not mocked."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import Institution, MatchScore, WeightSet

PASSWORD = "correct horse battery staple"

# The dev DB this suite runs against already carries ~1,500 rows from a prior
# `python -m cohab.seed` run (docker compose's named volume persists across
# restarts) — tests share that pool rather than assuming an empty database,
# which is also the more honest test: Stage 1/2 must work correctly
# regardless of how many other real candidates are in the pool. A limit far
# above the seed size guarantees a specific eligible candidate is returned
# regardless of rank position; MatchesService.get_matches Stage-1-filters
# before slicing, so this doesn't change how many rows actually get scored.
LARGE_LIMIT = 3000


def _find(items: list[dict], candidate_id: str) -> dict:
    for item in items:
        if item["candidate_id"] == candidate_id:
            return item
    raise AssertionError(f"{candidate_id} not found among {len(items)} matches")


def _onboard(
    client: TestClient,
    institution: Institution,
    caplog: pytest.LogCaptureFixture,
    *,
    name: str,
    email_local: str,
    questionnaire: dict,
    budget_min: int = 10000,
    budget_max: int = 15000,
    move_in_date: str = "2026-09-01",
    gender: str = "female",
) -> str:
    """Register, verify, and save a profile for a brand-new user. Leaves the
    client logged in as this user (verify sets the session cookie)."""
    email = f"{email_local}@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": name,
                "gender": gender,
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
            "budget_min": budget_min,
            "budget_max": budget_max,
            "move_in_date": move_in_date,
            "gender_preference": "any",
            "questionnaire": questionnaire,
            "important_attributes": [],
        },
    )
    assert profile_resp.status_code == 200, profile_resp.text
    return user_id


ASHA_ANSWERS = {
    "cleanliness_level": "very_tidy",
    "sleep_schedule": "early",
    "guest_tolerance": "anytime",
    "guest_frequency": "rarely",
    "payment_reliability": "early",
    "communication_style": "direct_now",
}

# Agrees with Asha on cleanliness/guests/payment/communication; diverges hard
# on sleep (early vs night_owl scores 0.20 in the matrix — well under the 0.5
# divergence threshold).
BALA_ANSWERS = {
    **ASHA_ANSWERS,
    "sleep_schedule": "night_owl",
}


@pytest.fixture()
def asha_and_bala(client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture) -> tuple[str, str]:
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha", questionnaire=ASHA_ANSWERS)
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala", questionnaire=BALA_ANSWERS)
    return asha_id, bala_id


def _login(client: TestClient, email: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


def test_matches_requires_authentication(client: TestClient, weight_set: WeightSet) -> None:
    resp = client.get("/matches")
    assert resp.status_code == 401


def test_matches_requires_verification(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture
) -> None:
    email = f"unverified@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        client.post(
            "/auth/register",
            json={"email": email, "password": PASSWORD, "full_name": "X", "gender": "female", "seeker_type": "needs_place"},
        )
    # login doesn't require verification (a user may need to re-enter the
    # flow to finish OTP entry) — this is how an authenticated-but-unverified
    # session is reached to exercise require_verified_user's second check.
    _login(client, email)
    resp = client.get("/matches")
    assert resp.status_code == 403


def test_get_matches_returns_eligible_candidate_with_explanation_tags(
    client: TestClient, institution: Institution, asha_and_bala: tuple[str, str]
) -> None:
    asha_id, bala_id = asha_and_bala
    _login(client, f"asha@{institution.email_domain}")

    resp = client.get(f"/matches?limit={LARGE_LIMIT}")
    assert resp.status_code == 200, resp.text
    item = _find(resp.json(), bala_id)
    assert item["candidate_name"] == "Bala"
    assert 0.0 <= item["combined_score"] <= 1.0
    assert len(item["agreements"]) > 0
    assert item["divergence"] is not None  # sleep_schedule, by design


def test_get_matches_is_idempotent_no_duplicate_rows(
    client: TestClient, institution: Institution, db_session: Session, asha_and_bala: tuple[str, str]
) -> None:
    asha_id, bala_id = asha_and_bala
    _login(client, f"asha@{institution.email_domain}")
    first = _find(client.get(f"/matches?limit={LARGE_LIMIT}").json(), bala_id)
    second = _find(client.get(f"/matches?limit={LARGE_LIMIT}").json(), bala_id)

    assert first["match_id"] == second["match_id"]

    a_id, b_id = sorted([asha_id, bala_id])
    rows = db_session.scalars(
        select(MatchScore).where(MatchScore.user_id_a == a_id, MatchScore.user_id_b == b_id)
    ).all()
    assert len(rows) == 1


def test_explanation_readable_from_both_sides_and_transitions_state(
    client: TestClient, institution: Institution, db_session: Session, asha_and_bala: tuple[str, str]
) -> None:
    asha_id, bala_id = asha_and_bala
    _login(client, f"asha@{institution.email_domain}")
    match_id = _find(client.get(f"/matches?limit={LARGE_LIMIT}").json(), bala_id)["match_id"]

    row = db_session.get(MatchScore, match_id)
    assert row.state == "suggested"

    resp_a = client.get(f"/matches/{match_id}/explanation")
    assert resp_a.status_code == 200, resp_a.text
    body_a = resp_a.json()
    assert body_a["candidate_id"] == bala_id
    assert body_a["divergence"]["attribute"] == "sleep_schedule"

    db_session.refresh(row)
    assert row.state == "viewed"  # suggested -> viewed (PRD §8.2)

    _login(client, f"bala@{institution.email_domain}")
    resp_b = client.get(f"/matches/{match_id}/explanation")
    assert resp_b.status_code == 200, resp_b.text
    body_b = resp_b.json()
    assert body_b["candidate_id"] == asha_id
    # Same underlying pair and the same divergent attribute, viewed from the
    # other side.
    assert body_b["divergence"]["attribute"] == "sleep_schedule"


def test_explanation_404_for_nonexistent_match(client: TestClient, institution: Institution, asha_and_bala: tuple[str, str]) -> None:
    _login(client, f"asha@{institution.email_domain}")
    resp = client.get("/matches/00000000-0000-0000-0000-000000000000/explanation")
    assert resp.status_code == 404


def test_explanation_403_for_a_non_party(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, asha_and_bala: tuple[str, str]
) -> None:
    asha_id, bala_id = asha_and_bala
    _login(client, f"asha@{institution.email_domain}")
    match_id = _find(client.get(f"/matches?limit={LARGE_LIMIT}").json(), bala_id)["match_id"]

    _onboard(client, institution, caplog, name="Chitra", email_local="chitra", questionnaire=ASHA_ANSWERS)
    resp = client.get(f"/matches/{match_id}/explanation")
    assert resp.status_code == 403


def test_ineligible_candidate_excluded_by_hard_constraints(
    client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture, asha_and_bala: tuple[str, str]
) -> None:
    # A different city fails Stage 1 outright (spec §2) — must never appear.
    deepa_id = _onboard(
        client, institution, caplog, name="Deepa", email_local="deepa",
        questionnaire=ASHA_ANSWERS, budget_min=10000, budget_max=15000,
    )
    # Deepa's own profile save above overrides the client's login to Deepa;
    # switch to Asha before asserting on Asha's match list.
    _login(client, f"asha@{institution.email_domain}")
    resp = client.get(f"/matches?limit={LARGE_LIMIT}")
    _find(resp.json(), deepa_id)  # same city/budget — should be eligible (raises if absent)

    _login(client, f"deepa@{institution.email_domain}")
    # Now prove a genuinely different city is excluded: reuse Deepa's account
    # to move to Chennai and confirm she drops out of Asha's list.
    client.put(
        "/profile",
        json={
            "city": "Chennai",
            "budget_min": 10000,
            "budget_max": 15000,
            "move_in_date": "2026-09-01",
            "gender_preference": "any",
            "questionnaire": ASHA_ANSWERS,
            "important_attributes": [],
        },
    )
    _login(client, f"asha@{institution.email_domain}")
    resp = client.get(f"/matches?limit={LARGE_LIMIT}")
    ids = {item["candidate_id"] for item in resp.json()}
    assert deepa_id not in ids

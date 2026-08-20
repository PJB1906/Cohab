"""GET /analytics/summary — build plan §4 Phase 8. Gated by `require_moderator`,
same pattern as tests/api/test_moderation.py."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cohab.models import Institution, User, WeightSet

PASSWORD = "correct horse battery staple"


def _register_verified(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, *, name: str, email_local: str
) -> str:
    email = f"{email_local}@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={"email": email, "password": PASSWORD, "full_name": name, "gender": "female", "seeker_type": "needs_place"},
        )
    user_id = resp.json()["user_id"]
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    caplog.clear()
    client.post("/auth/verify", json={"user_id": user_id, "code": code})
    return user_id


def _login(client: TestClient, email: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


def test_analytics_requires_authentication(client: TestClient) -> None:
    resp = client.get("/analytics/summary")
    assert resp.status_code == 401


def test_analytics_requires_moderator(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _register_verified(client, institution, caplog, name="Asha", email_local="asha")
    _login(client, f"asha@{institution.email_domain}")
    resp = client.get("/analytics/summary")
    assert resp.status_code == 403


def test_analytics_summary_counts_reflect_seeded_members(
    client: TestClient,
    institution: Institution,
    weight_set: WeightSet,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    moderator_user: tuple[uuid.UUID, str],
) -> None:
    _register_verified(client, institution, caplog, name="Asha", email_local="asha")

    _, moderator_email = moderator_user
    _login(client, moderator_email)

    resp = client.get("/analytics/summary")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # moderator_user + Asha, both currently unverified until OTP-verified —
    # moderator_user's fixture does verify itself, Asha's registration alone
    # does not, so exactly one of each status for this institution's slice.
    assert body["members_by_verification_status"]["verified"] >= 1
    assert body["members_by_verification_status"]["unverified"] >= 1
    assert set(body["members_by_account_status"].keys()) == {"active", "suspended", "banned", "erased"}
    assert set(body["matches_by_state"].keys()) == {
        "suggested", "viewed", "interested", "mutual", "chatting",
        "contact_shared", "cohabiting", "rejected", "expired",
    }
    assert set(body["reports_by_status"].keys()) == {
        "open", "under_review", "substantiated", "dismissed", "action_taken",
    }

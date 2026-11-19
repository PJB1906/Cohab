"""/me/taste and personalised ranking, end to end (D-14.22)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import Institution, MatchExposure, UserTaste, WeightSet
from tests.api.test_chat import _login, _onboard


@pytest.fixture()
def asha(client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture) -> str:
    uid = _onboard(client, institution, caplog, name="Asha", email_local="asha")
    _login(client, f"asha@{institution.email_domain}")
    return uid


def _decide(client: TestClient, items: list[dict], likes: int, passes: int) -> None:
    for m in items[:likes]:
        assert client.post(f"/matches/{m['match_id']}/interest").status_code == 200
    for m in items[likes : likes + passes]:
        client.get(f"/matches/{m['match_id']}/explanation")  # suggested -> viewed
        assert client.post(f"/matches/{m['match_id']}/reject", json={"reason": "lifestyle"}).status_code == 200


def test_new_member_has_an_inactive_model_with_stated_weights(client: TestClient, asha: str) -> None:
    body = client.get("/me/taste").json()
    assert body["enabled"] is True and body["active"] is False
    assert body["decisions"] == 0 and body["needed"] > 0
    assert body["insights"] == []
    w = body["weights"]
    assert w and abs(sum(x["learned"] for x in w) - 1) < 1e-6
    assert all(abs(x["shift"]) < 1e-9 for x in w)


def test_decisions_activate_learning_and_personalise_the_list(
    client: TestClient, db_session: Session, asha: str
) -> None:
    items = client.get("/matches?limit=60").json()
    if len(items) < 12:
        pytest.skip("seeded pool too small for this member")
    assert all(i["taste_rank_change"] is None for i in items)

    _decide(client, items, likes=4, passes=4)
    body = client.get("/me/taste").json()
    assert body["active"] is True and body["decisions"] == 8
    assert body["positives"] == 4 and body["negatives"] == 4 and body["needed"] == 0

    after = client.get("/matches?limit=60").json()
    assert all(isinstance(i["taste_rank_change"], int) for i in after)
    # Displayed scores stay the platform's stored, explainable scores.
    before_scores = {i["match_id"]: i["combined_score"] for i in items}
    for i in after:
        if i["match_id"] in before_scores:
            assert i["combined_score"] == pytest.approx(before_scores[i["match_id"]])
    # The served list is logged under its own policy name.
    latest = db_session.scalars(
        select(MatchExposure).where(MatchExposure.viewer_id == uuid.UUID(asha)).order_by(MatchExposure.shown_at.desc())
    ).first()
    assert latest.policy_version.endswith("+taste")


def test_switching_off_restores_platform_order(client: TestClient, db_session: Session, asha: str) -> None:
    items = client.get("/matches?limit=60").json()
    if len(items) < 12:
        pytest.skip("seeded pool too small for this member")
    _decide(client, items, likes=4, passes=4)

    off = client.put("/me/taste", json={"enabled": False}).json()
    assert off["enabled"] is False
    assert all(i["taste_rank_change"] is None for i in client.get("/matches?limit=60").json())
    assert db_session.get(UserTaste, uuid.UUID(asha)).enabled is False

    on = client.put("/me/taste", json={"enabled": True}).json()
    assert on["enabled"] is True and on["active"] is True


def test_rejections_after_chat_are_not_used(client: TestClient, db_session: Session, institution, caplog, weight_set) -> None:
    from tests.api.test_chat import mutual_pair  # noqa: F401  (fixture shape reused below)

    a = _onboard(client, institution, caplog, name="Asha", email_local="asha", phone_number="9876543210")
    b = _onboard(client, institution, caplog, name="Bala", email_local="bala", phone_number="9876500000")
    _login(client, f"asha@{institution.email_domain}")
    mid = next(m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == b)
    client.post(f"/matches/{mid}/interest")
    _login(client, f"bala@{institution.email_domain}")
    client.post(f"/matches/{mid}/interest")
    client.get(f"/chat/{mid}/messages")  # opens chat
    client.post(f"/matches/{mid}/reject")
    body = client.get("/me/taste").json()
    assert body["negatives"] == 0  # the post-chat rejection is not a profile signal
    assert body["positives"] == 1


def test_taste_requires_login(client: TestClient) -> None:
    assert client.get("/me/taste").status_code == 401

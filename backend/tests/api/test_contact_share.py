"""POST /chat/{match_id}/contact-share, GET /chat/{match_id}/contact-status —
build plan §4 Phase 6, PRD §8.2/§10."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cohab.models import Institution, MatchScore, User, WeightSet

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
    phone_number: str,
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
    """(asha_id, bala_id, match_id): both `interested`, state `mutual`,
    Asha's phone is 9876543210, Bala's is 9876500000, client logged in as
    Asha."""
    asha_id = _onboard(client, institution, caplog, name="Asha", email_local="asha", phone_number="9876543210")
    bala_id = _onboard(client, institution, caplog, name="Bala", email_local="bala", phone_number="9876500000")

    _login(client, f"asha@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_id = next(m["match_id"] for m in matches if m["candidate_id"] == bala_id)
    client.post(f"/matches/{match_id}/interest")

    _login(client, f"bala@{institution.email_domain}")
    assert client.post(f"/matches/{match_id}/interest").json()["state"] == "mutual"

    _login(client, f"asha@{institution.email_domain}")
    return asha_id, bala_id, match_id


def test_opt_in_before_chat_open_is_409(client: TestClient, mutual_pair: tuple[str, str, str]) -> None:
    _, _, match_id = mutual_pair
    resp = client.post(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 409


def test_one_sided_consent_reveals_nothing(client: TestClient, mutual_pair: tuple[str, str, str]) -> None:
    _, _, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")  # opens the thread (mutual -> chatting)

    resp = client.post(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["you_consented"] is True
    assert body["other_consented"] is False
    assert body["other_phone"] is None


def test_withdraw_undoes_one_sided_consent(client: TestClient, mutual_pair: tuple[str, str, str]) -> None:
    """Mockup fidelity: the mockups let a user withdraw consent before the
    other party has accepted; the built ContactShare screen had no way back
    once opted in. docs/DECISIONS.md D-10.5."""
    _, _, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")
    client.post(f"/chat/{match_id}/contact-share")

    resp = client.delete(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 200, resp.text
    assert resp.json()["you_consented"] is False

    status = client.get(f"/chat/{match_id}/contact-status").json()
    assert status["you_consented"] is False


def test_withdraw_after_mutual_share_is_409(
    client: TestClient, institution: Institution, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")
    client.post(f"/chat/{match_id}/contact-share")
    _login(client, f"bala@{institution.email_domain}")
    client.post(f"/chat/{match_id}/contact-share")

    resp = client.delete(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 409


def test_withdraw_with_nothing_to_withdraw_is_a_no_op(
    client: TestClient, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")

    resp = client.delete(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 200, resp.text
    assert resp.json()["you_consented"] is False


def test_both_sided_consent_reveals_phone_and_flips_state(
    client: TestClient, institution: Institution, db_session: Session, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")
    client.post(f"/chat/{match_id}/contact-share")

    _login(client, f"bala@{institution.email_domain}")
    resp = client.post(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["you_consented"] is True
    assert body["other_consented"] is True
    assert body["other_phone"] == "9876543210"  # Asha's number, seen from Bala's side

    row = db_session.get(MatchScore, match_id)
    db_session.refresh(row)
    assert row.state == "contact_shared"  # PRD §8.2: Chatting -> ContactShared

    # And from Asha's side, the status endpoint now shows Bala's number.
    _login(client, f"asha@{institution.email_domain}")
    status = client.get(f"/chat/{match_id}/contact-status").json()
    assert status["other_phone"] == "9876500000"


def test_opt_in_converts_concurrent_duplicate_insert_to_recovered_status(
    client: TestClient, db_session: Session, mutual_pair: tuple[str, str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two near-simultaneous opt-ins from the same user both find "no
    existing `ContactShare` row" before either commits — the loser used to
    hit a raw `IntegrityError` on `uq_contact_share_score_user` on its own
    `flush()` instead of recovering. Reproduced by forcing the service's own
    pre-insert check to report "not found" once a row already exists —
    `_status`'s own read (plural `scalars`, unaffected by this) then proves
    consent is correctly recorded regardless."""
    from cohab.services.contact_share import ContactShareService

    asha_id, _bala_id, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")  # opens the thread (mutual -> chatting)

    service = ContactShareService(db_session)
    asha = db_session.get(User, uuid.UUID(asha_id))
    first = service.opt_in(asha, uuid.UUID(match_id))
    assert first.you_consented is True

    monkeypatch.setattr(db_session, "scalar", lambda *a, **kw: None)
    second = service.opt_in(asha, uuid.UUID(match_id))
    assert second.you_consented is True


def test_contact_share_403_for_non_party(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, mutual_pair: tuple[str, str, str]
) -> None:
    _, _, match_id = mutual_pair
    client.get(f"/chat/{match_id}/messages")
    _onboard(client, institution, caplog, name="Chitra", email_local="chitra", phone_number="9876511111")
    resp = client.post(f"/chat/{match_id}/contact-share")
    assert resp.status_code == 403

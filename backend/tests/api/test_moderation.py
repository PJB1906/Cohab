"""GET/POST /moderation/reports/* — build plan §4 Phase 7, PRD §8.3 / §9
screen 13."""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cohab.models import Institution, User, WeightSet

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
    return user_id


def _login(client: TestClient, email: str) -> None:
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text


def _make_moderator(
    client: TestClient,
    institution: Institution,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    *,
    email_local: str,
) -> str:
    """A second moderator account — mirrors conftest.py's `moderator_user`
    fixture, but as a plain helper for tests that need more than one."""
    email = f"{email_local}@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": PASSWORD,
                "full_name": "Other Moderator",
                "gender": "female",
                "seeker_type": "needs_place",
            },
        )
    user_id = resp.json()["user_id"]
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    caplog.clear()
    client.post("/auth/verify", json={"user_id": user_id, "code": code})
    user = db_session.get(User, user_id)
    user.is_moderator = True
    db_session.commit()
    return email


@pytest.fixture()
def open_report(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> tuple[str, str, str]:
    """(reporter_id, reported_id, report_id) for a freshly-filed, still-open
    report. Leaves the client logged in as the reporter — tests that need
    the moderator logged in must switch explicitly."""
    reporter_id = _onboard(client, institution, caplog, name="Reporter", email_local="reporter")
    reported_id = _onboard(client, institution, caplog, name="Reported", email_local="reported")
    _login(client, f"reporter@{institution.email_domain}")
    resp = client.post("/reports", json={"reported_user_id": reported_id, "reason": "spam", "details": "spammy"})
    assert resp.status_code == 201, resp.text
    return reporter_id, reported_id, resp.json()["id"]


def test_moderation_routes_require_moderator(client: TestClient, open_report: tuple[str, str, str]) -> None:
    # `open_report` leaves the client logged in as a plain (non-moderator) user.
    _, _, report_id = open_report
    assert client.get("/moderation/reports").status_code == 403
    assert client.get(f"/moderation/reports/{report_id}").status_code == 403
    assert client.post(f"/moderation/reports/{report_id}/claim").status_code == 403


def test_claim_moves_open_to_under_review_and_assigns(
    client: TestClient, moderator_user: tuple[uuid.UUID, str], open_report: tuple[str, str, str]
) -> None:
    _, _, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)

    resp = client.post(f"/moderation/reports/{report_id}/claim")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "under_review"


def test_cannot_claim_a_report_twice(
    client: TestClient, moderator_user: tuple[uuid.UUID, str], open_report: tuple[str, str, str]
) -> None:
    _, _, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")
    resp = client.post(f"/moderation/reports/{report_id}/claim")
    assert resp.status_code == 409


def test_cannot_resolve_before_claiming(
    client: TestClient, moderator_user: tuple[uuid.UUID, str], open_report: tuple[str, str, str]
) -> None:
    _, _, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    resp = client.post(
        f"/moderation/reports/{report_id}/resolve", json={"finding": "dismissed", "sanction": None, "note": None}
    )
    assert resp.status_code == 409


def test_resolve_substantiated_with_suspend_records_sanction_separately_from_finding(
    client: TestClient,
    db_session: Session,
    moderator_user: tuple[uuid.UUID, str],
    open_report: tuple[str, str, str],
) -> None:
    """PRD §8.3: "Finding and sanction are recorded separately, so the
    audit trail shows what was concluded as well as what was done.\""""
    _, reported_id, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")

    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "substantiated", "sanction": "suspend", "note": "confirmed via evidence"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "action_taken"  # the finding
    assert body["sanction"] == "suspend"  # the sanction — a separate field
    assert body["resolution_note"] == "confirmed via evidence"

    reported = db_session.get(User, reported_id)
    db_session.refresh(reported)
    assert reported.account_status == "suspended"


def test_resolve_dismissed_leaves_account_untouched(
    client: TestClient,
    db_session: Session,
    moderator_user: tuple[uuid.UUID, str],
    open_report: tuple[str, str, str],
) -> None:
    _, reported_id, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")

    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "dismissed", "sanction": None, "note": "no evidence found"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "dismissed"
    assert body["sanction"] is None

    reported = db_session.get(User, reported_id)
    db_session.refresh(reported)
    assert reported.account_status == "active"


def test_resolve_substantiated_with_ban_bans_account(
    client: TestClient,
    db_session: Session,
    moderator_user: tuple[uuid.UUID, str],
    open_report: tuple[str, str, str],
) -> None:
    """`ban` and `suspend` set different `account_status` values — the
    `suspend` test above only exercises one side of that ternary."""
    _, reported_id, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")

    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "substantiated", "sanction": "ban", "note": "repeat offender"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["sanction"] == "ban"

    reported = db_session.get(User, reported_id)
    db_session.refresh(reported)
    assert reported.account_status == "banned"


def test_resolve_substantiated_with_warn_does_not_change_account_status(
    client: TestClient,
    db_session: Session,
    moderator_user: tuple[uuid.UUID, str],
    open_report: tuple[str, str, str],
) -> None:
    """`warn` is record-only (docs/DECISIONS.md D-7.3) — the finding and
    sanction are still stored, but `account_status` is untouched."""
    _, reported_id, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")

    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "substantiated", "sanction": "warn", "note": "first offence, spoke with them"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "action_taken"
    assert body["sanction"] == "warn"

    reported = db_session.get(User, reported_id)
    db_session.refresh(reported)
    assert reported.account_status == "active"


def test_only_the_assigned_moderator_can_resolve(
    client: TestClient,
    institution: Institution,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    moderator_user: tuple[uuid.UUID, str],
    open_report: tuple[str, str, str],
) -> None:
    """Claiming assigns responsibility for a case — a different moderator
    shouldn't be able to close it out from under the one who claimed it."""
    _, _, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")

    other_mod_email = _make_moderator(client, institution, db_session, caplog, email_local="othermod")
    _login(client, other_mod_email)
    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "dismissed", "sanction": None, "note": None},
    )
    assert resp.status_code == 403


def test_substantiated_requires_a_sanction(
    client: TestClient, moderator_user: tuple[uuid.UUID, str], open_report: tuple[str, str, str]
) -> None:
    _, _, report_id = open_report
    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")

    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "substantiated", "sanction": None, "note": None},
    )
    assert resp.status_code == 400


def test_dismissal_reactivates_a_user_suspended_only_by_this_report(
    client: TestClient,
    institution: Institution,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    moderator_user: tuple[uuid.UUID, str],
) -> None:
    """An escalating reason suspends pending review (PRD §8.3). If that
    report is later dismissed and nothing else is open against the same
    user, the suspension — provisional, not a concluded sanction — lifts."""
    reported_id = _onboard(client, institution, caplog, name="Reported", email_local="reported2")
    _onboard(client, institution, caplog, name="Reporter", email_local="reporter2")
    _login(client, f"reporter2@{institution.email_domain}")
    filed = client.post("/reports", json={"reported_user_id": reported_id, "reason": "threats", "details": None})
    assert filed.status_code == 201, filed.text
    report_id = filed.json()["id"]

    reported = db_session.get(User, reported_id)
    db_session.refresh(reported)
    assert reported.account_status == "suspended"  # escalation suspend, pending review

    _, mod_email = moderator_user
    _login(client, mod_email)
    client.post(f"/moderation/reports/{report_id}/claim")
    resp = client.post(
        f"/moderation/reports/{report_id}/resolve",
        json={"finding": "dismissed", "sanction": None, "note": "unfounded"},
    )
    assert resp.status_code == 200, resp.text

    db_session.refresh(reported)
    assert reported.account_status == "active"


def test_evidence_returns_only_flagged_messages_from_the_reported_user(
    client: TestClient,
    institution: Institution,
    weight_set: WeightSet,
    caplog: pytest.LogCaptureFixture,
    moderator_user: tuple[uuid.UUID, str],
) -> None:
    """Evidence is scoped to the reported user's own flagged messages, not
    the whole thread (docs/DECISIONS.md D-7.6)."""
    reported_id = _onboard(client, institution, caplog, name="Reported", email_local="reported3")
    _onboard(client, institution, caplog, name="Reporter", email_local="reporter3")

    for email_local in ("reporter3", "reported3"):
        _login(client, f"{email_local}@{institution.email_domain}")
        client.put(
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

    _login(client, f"reporter3@{institution.email_domain}")
    matches = client.get("/matches?limit=3000").json()
    match_id = next(m["match_id"] for m in matches if m["candidate_id"] == reported_id)
    client.post(f"/matches/{match_id}/interest")
    _login(client, f"reported3@{institution.email_domain}")
    client.post(f"/matches/{match_id}/interest")

    # Reported user sends an abusive (flaggable) message; reporter sends a
    # clean one — only the former should surface as evidence.
    client.post(f"/chat/{match_id}/messages", json={"body": "I'll kill you if you're late"})
    _login(client, f"reporter3@{institution.email_domain}")
    client.post(f"/chat/{match_id}/messages", json={"body": "looking forward to it"})

    filed = client.post("/reports", json={"reported_user_id": reported_id, "reason": "harassment", "details": None})
    assert filed.status_code == 201, filed.text
    report_id = filed.json()["id"]

    _, mod_email = moderator_user
    _login(client, mod_email)
    resp = client.get(f"/moderation/reports/{report_id}")
    assert resp.status_code == 200, resp.text
    evidence = resp.json()["evidence"]
    assert len(evidence) == 1
    assert evidence[0]["body"] == "I'll kill you if you're late"
    assert evidence[0]["sender_id"] == reported_id

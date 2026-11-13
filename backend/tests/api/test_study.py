"""/study/* API — Cohab Lab and roommate pairs (Cohab v2 plan W2/W3)."""

from __future__ import annotations

import random
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import StudyRater, StudyTrial, User
from cohab.services.study.instrument import (
    CONSENT_VERSION,
    GAMEABLE_FIELDS,
    OPTIONS,
    OUTCOME_ITEMS,
    PAIR_CONSENT_VERSION,
    RATER_FIELDS,
)
from cohab.services.study.service import hash_token


def answers(seed: int = 0) -> dict[str, str]:
    rng = random.Random(seed)
    return {f: rng.choice(OPTIONS[f]) for f in RATER_FIELDS}


def _h(token: str) -> dict[str, str]:
    return {"X-Study-Token": token}


def _start(client: TestClient) -> str:
    resp = client.post("/study/lab/raters", json={"cohort": "test"})
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    assert client.post("/study/lab/consent", json={"consent_version": CONSENT_VERSION}, headers=_h(token)).status_code == 200
    resp = client.put(
        "/study/lab/profile",
        json={"answers": answers(), "important_attributes": ["cleanliness_level"], "demographics": {"age_band": "21-23"}},
        headers=_h(token),
    )
    assert resp.status_code == 200, resp.text
    return token


def _answer(client: TestClient, token: str, trial: dict) -> dict:
    if trial["kind"] == "rank":
        body = {"ranking": [c["id"] for c in trial["cards"]]}
    else:
        body = {"choice": "left", "confidence": 4, "would_message": "left", "response_ms": 2100}
    resp = client.post(f"/study/lab/trials/{trial['trial_id']}/response", json=body, headers=_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_instrument_is_public(client: TestClient) -> None:
    body = client.get("/study/instrument").json()
    assert body["open"] is True
    assert body["consent_version"] == CONSENT_VERSION
    assert len(body["study_attributes"]) == 17


def test_token_is_stored_only_as_hash(client: TestClient, db_session: Session) -> None:
    token = client.post("/study/lab/raters").json()["token"]
    rater = db_session.scalar(select(StudyRater).where(StudyRater.token_hash == hash_token(token)))
    assert rater is not None
    assert token not in {rater.token_hash, str(rater.id)}


def test_steps_must_happen_in_order(client: TestClient) -> None:
    token = client.post("/study/lab/raters").json()["token"]
    assert client.get("/study/lab/next", headers=_h(token)).status_code == 409  # no consent
    bad = client.post("/study/lab/consent", json={"consent_version": "old"}, headers=_h(token))
    assert bad.status_code == 422
    client.post("/study/lab/consent", json={"consent_version": CONSENT_VERSION}, headers=_h(token))
    assert client.get("/study/lab/next", headers=_h(token)).status_code == 409  # no profile
    assert client.get("/study/lab/next", headers=_h("nope")).status_code == 401


def test_profile_validation(client: TestClient) -> None:
    token = client.post("/study/lab/raters").json()["token"]
    client.post("/study/lab/consent", json={"consent_version": CONSENT_VERSION}, headers=_h(token))
    resp = client.put(
        "/study/lab/profile", json={"answers": answers() | {"diet": "pizza"}, "important_attributes": []}, headers=_h(token)
    )
    assert resp.status_code == 422
    assert any("diet" in p for p in resp.json()["detail"]["problems"])


def test_full_session_to_completion(client: TestClient, db_session: Session) -> None:
    token = _start(client)
    first = client.get("/study/lab/next", headers=_h(token)).json()
    total = first["progress"]["total"]
    assert total == 40 and first["progress"]["answered"] == 0
    # Cards never carry anything identifying.
    assert set(first["trial"]["cards"][0]) == {"id", "answers"}

    # Same trial is served again until answered (resume by token).
    again = client.get("/study/lab/next", headers=_h(token)).json()
    assert again["trial"]["trial_id"] == first["trial"]["trial_id"]

    trial = first["trial"]
    for _ in range(total):
        progress = _answer(client, token, trial)
        nxt = client.get("/study/lab/next", headers=_h(token)).json()
        trial = nxt["trial"]
        if trial is None:
            break
    assert progress["completed"] is True and progress["answered"] == total

    # Profile is locked after trials start.
    locked = client.put("/study/lab/profile", json={"answers": answers(1), "important_attributes": []}, headers=_h(token))
    assert locked.status_code == 409


def test_answers_must_be_in_order_and_once(client: TestClient, db_session: Session) -> None:
    token = _start(client)
    first = client.get("/study/lab/next", headers=_h(token)).json()["trial"]
    rater = db_session.scalar(select(StudyRater).where(StudyRater.token_hash == hash_token(token)))
    later = db_session.scalar(select(StudyTrial).where(StudyTrial.rater_id == rater.id, StudyTrial.position == 5))
    body = {"choice": "left", "confidence": 3, "would_message": "neither"}
    assert client.post(f"/study/lab/trials/{later.id}/response", json=body, headers=_h(token)).status_code == 409
    assert client.post(f"/study/lab/trials/{first['trial_id']}/response", json=body, headers=_h(token)).status_code == 200
    assert client.post(f"/study/lab/trials/{first['trial_id']}/response", json=body, headers=_h(token)).status_code == 409
    missing = client.post(
        f"/study/lab/trials/{uuid.uuid4()}/response", json=body, headers=_h(token)
    )
    assert missing.status_code == 401


def test_withdraw_deletes_everything(client: TestClient, db_session: Session) -> None:
    token = _start(client)
    client.get("/study/lab/next", headers=_h(token))
    assert client.delete("/study/lab/me", headers=_h(token)).status_code == 204
    assert db_session.scalar(select(StudyRater).where(StudyRater.token_hash == hash_token(token))) is None
    assert client.get("/study/lab/next", headers=_h(token)).status_code == 401


def test_study_can_be_closed_by_flag(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDY_ENABLED", "false")
    assert client.post("/study/lab/raters").status_code == 404
    assert client.get("/study/instrument").json()["open"] is False


def _pair_body(seed: int) -> dict:
    rng = random.Random(seed)
    return {
        "consent_version": PAIR_CONSENT_VERSION,
        "answers": answers(seed),
        "important_attributes": [],
        "roommate_ratings": {f: rng.choice(OPTIONS[f]) for f in GAMEABLE_FIELDS},
        "outcomes": {k: rng.randint(1, 5) for k in OUTCOME_ITEMS},
        "months_together": 7,
        "still_together": True,
    }


def test_roommate_pair_flow(client: TestClient) -> None:
    created = client.post("/study/pairs").json()
    token_a, invite = created["token"], created["invite_token"]
    assert client.get("/study/pairs/me", headers=_h(token_a)).json() == {
        "role": "a", "submitted": False, "roommate_joined": False, "roommate_submitted": False,
    }
    token_b = client.post("/study/pairs/join", json={"invite_token": invite}).json()["token"]
    assert client.post("/study/pairs/join", json={"invite_token": invite}).status_code == 409  # single use

    bad = _pair_body(1) | {"outcomes": {"overall_satisfaction": 9}}
    assert client.put("/study/pairs/me", json=bad, headers=_h(token_a)).status_code == 422

    assert client.put("/study/pairs/me", json=_pair_body(1), headers=_h(token_a)).json()["roommate_submitted"] is False
    status_b = client.put("/study/pairs/me", json=_pair_body(2), headers=_h(token_b)).json()
    assert status_b == {"role": "b", "submitted": True, "roommate_joined": True, "roommate_submitted": True}
    assert client.put("/study/pairs/me", json=_pair_body(2), headers=_h(token_b)).status_code == 409


def test_admin_summary_and_export_are_moderator_only(
    client: TestClient, db_session: Session, moderator_user
) -> None:
    token = _start(client)
    trial = client.get("/study/lab/next", headers=_h(token)).json()["trial"]
    _answer(client, token, trial)

    # moderator_user left the client logged in as the moderator.
    summary = client.get("/study/admin/summary")
    assert summary.status_code == 200, summary.text
    assert summary.json()["raters_consented"] >= 1
    assert summary.json()["responses"] >= 1
    export = client.get("/study/admin/export").json()
    rec = next(r for r in export["raters"] if r["cohort"] == "test")
    assert rec["trials"][0]["chosen"] in ("A", "B")
    assert "token_hash" not in rec

    user_id, _email = moderator_user
    db_session.get(User, user_id).is_moderator = False
    db_session.flush()
    assert client.get("/study/admin/summary").status_code == 403


def test_study_creation_is_rate_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from cohab.core import ratelimit

    monkeypatch.setattr(ratelimit, "study_per_client", ratelimit.SlidingWindowLimiter(2, 3600))
    headers = {"X-Forwarded-For": "203.0.113.7"}
    assert client.post("/study/lab/raters", headers=headers).status_code == 201
    assert client.post("/study/pairs", headers=headers).status_code == 201
    blocked = client.post("/study/lab/raters", headers=headers)
    assert blocked.status_code == 429
    assert "try again later" in blocked.json()["detail"]
    # Another network is unaffected.
    assert client.post("/study/lab/raters", headers={"X-Forwarded-For": "198.51.100.4"}).status_code == 201


def test_sliding_window_expires_old_events() -> None:
    from cohab.core.ratelimit import SlidingWindowLimiter

    lim = SlidingWindowLimiter(2, 10)
    assert lim.hit("k", now=0) and lim.hit("k", now=1)
    assert not lim.hit("k", now=5)
    assert lim.hit("k", now=11.5)  # the first event has left the window

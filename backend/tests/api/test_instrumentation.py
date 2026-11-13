"""v2 W1 — exposure log, state-event chain, read-path writes, funnel,
health and metrics (Cohab v2 plan W1; deck slide 23 acceptance: "a full
journey yields a gap-free, ordered event chain")."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from cohab.models import Institution, MatchExposure, MatchScore, MatchStateEvent, User, WeightSet
from tests.api.test_chat import _login, _onboard


def _events(db: Session, match_id: str) -> list[MatchStateEvent]:
    return list(
        db.scalars(
            select(MatchStateEvent)
            .where(MatchStateEvent.match_score_id == uuid.UUID(match_id))
            .order_by(MatchStateEvent.at, MatchStateEvent.id)
        ).all()
    )


def _chain(db: Session, match_id: str) -> list[tuple[str | None, str]]:
    events = _events(db, match_id)
    # Same-transaction events can share a timestamp; order by the chain
    # itself (each from_state is the previous to_state).
    by_from = {e.from_state: e for e in events}
    chain, state = [], None
    while state in by_from:
        e = by_from.pop(state)
        chain.append((e.from_state, e.to_state))
        state = e.to_state
    assert not by_from, f"events not on one chain: {by_from}"
    return chain


@pytest.fixture()
def pair(client: TestClient, institution: Institution, weight_set: WeightSet, caplog: pytest.LogCaptureFixture):
    asha = _onboard(client, institution, caplog, name="Asha", email_local="asha", phone_number="9876543210")
    bala = _onboard(client, institution, caplog, name="Bala", email_local="bala", phone_number="9876500000")
    _login(client, f"asha@{institution.email_domain}")
    return asha, bala


def test_get_matches_logs_one_exposure_per_candidate_with_rank(
    client: TestClient, db_session: Session, pair: tuple[str, str], weight_set: WeightSet
) -> None:
    asha, bala = pair
    resp = client.get("/matches?limit=3000")
    assert resp.status_code == 200
    items = resp.json()
    match_id = next(m["match_id"] for m in items if m["candidate_id"] == bala)

    exposures = list(
        db_session.scalars(select(MatchExposure).where(MatchExposure.viewer_id == uuid.UUID(asha))).all()
    )
    assert len(exposures) == len(items)
    by_match = {str(e.match_score_id): e for e in exposures}
    e = by_match[match_id]
    assert e.rank_position == [m["match_id"] for m in items].index(match_id) + 1
    assert e.surface == "list"
    assert e.propensity == 1.0
    active = db_session.scalar(select(WeightSet).where(WeightSet.is_active.is_(True)))
    assert e.weight_set_id == active.id
    assert e.policy_version == f"{active.source}-v{active.version}"
    row = db_session.get(MatchScore, uuid.UUID(match_id))
    db_session.refresh(row)
    assert row.first_shown_at is not None


def test_repeat_read_writes_no_score_rows(
    client: TestClient, db_session: Session, pair: tuple[str, str]
) -> None:
    """The conflict branch only updates a row whose score actually changed,
    so re-reading an unchanged pool leaves `updated_at` alone."""
    _asha, bala = pair
    match_id = next(m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == bala)
    row = db_session.get(MatchScore, uuid.UUID(match_id))
    db_session.refresh(row)
    before = row.updated_at
    n_events = len(_events(db_session, match_id))

    client.get("/matches?limit=3000")
    db_session.refresh(row)
    assert row.updated_at == before
    assert len(_events(db_session, match_id)) == n_events  # no second "created" event


def test_full_journey_yields_gap_free_ordered_chain(
    client: TestClient, db_session: Session, institution: Institution, pair: tuple[str, str]
) -> None:
    asha, bala = pair
    match_id = next(m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == bala)
    client.get(f"/matches/{match_id}/explanation")
    client.post(f"/matches/{match_id}/interest")
    _login(client, f"bala@{institution.email_domain}")
    client.post(f"/matches/{match_id}/interest")
    client.post(f"/chat/{match_id}/messages", json={"body": "hello!"})
    client.post(f"/chat/{match_id}/contact-share")
    _login(client, f"asha@{institution.email_domain}")
    client.post(f"/chat/{match_id}/contact-share")
    assert client.post(f"/matches/{match_id}/confirm-move-in").json()["state"] == "cohabiting"

    assert _chain(db_session, match_id) == [
        (None, "suggested"),
        ("suggested", "viewed"),
        ("viewed", "interested"),
        ("interested", "mutual"),
        ("mutual", "chatting"),
        ("chatting", "contact_shared"),
        ("contact_shared", "cohabiting"),
    ]
    actors = [e.actor_id for e in _events(db_session, match_id)]
    assert actors[0] is None  # creation is a system event
    assert uuid.UUID(bala) in actors and uuid.UUID(asha) in actors

    row = db_session.get(MatchScore, uuid.UUID(match_id))
    db_session.refresh(row)
    assert row.first_messaged_at is not None


def test_reject_records_reason_in_column_and_event(
    client: TestClient, db_session: Session, pair: tuple[str, str]
) -> None:
    _asha, bala = pair
    match_id = next(m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == bala)
    client.get(f"/matches/{match_id}/explanation")
    resp = client.post(f"/matches/{match_id}/reject", json={"reason": "schedule"})
    assert resp.json()["state"] == "rejected"

    row = db_session.get(MatchScore, uuid.UUID(match_id))
    db_session.refresh(row)
    assert row.rejection_reason == "schedule"
    last = _events(db_session, match_id)[-1]
    assert (last.to_state, last.event_metadata) == ("rejected", {"rejection_reason": "schedule"})


def test_reject_without_body_still_works_and_bad_reason_is_422(
    client: TestClient, pair: tuple[str, str]
) -> None:
    _asha, bala = pair
    match_id = next(m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == bala)
    client.get(f"/matches/{match_id}/explanation")
    assert client.post(f"/matches/{match_id}/reject", json={"reason": "vibes"}).status_code == 422
    assert client.post(f"/matches/{match_id}/reject").json()["state"] == "rejected"


def test_batch_reads_do_not_log_exposures(db_session: Session, pair: tuple[str, str], weight_set: WeightSet) -> None:
    from cohab.services.matches import MatchesService
    from cohab.services.matching.text import NeutralTextSimilarity

    asha, _bala = pair
    user = db_session.get(User, uuid.UUID(asha))
    before = db_session.scalar(select(func.count()).select_from(MatchExposure))
    MatchesService(db_session, weight_set, NeutralTextSimilarity()).get_matches(user, 3000, log_exposure=False)
    assert db_session.scalar(select(func.count()).select_from(MatchExposure)) == before


def test_funnel_is_moderator_only_and_counts_stages(
    client: TestClient, db_session: Session, institution: Institution, pair: tuple[str, str]
) -> None:
    asha, bala = pair
    match_id = next(m["match_id"] for m in client.get("/matches?limit=3000").json() if m["candidate_id"] == bala)
    client.post(f"/matches/{match_id}/interest")
    _login(client, f"bala@{institution.email_domain}")
    client.post(f"/matches/{match_id}/interest")
    assert client.get("/analytics/funnel").status_code == 403

    db_session.get(User, uuid.UUID(bala)).is_moderator = True
    db_session.flush()
    resp = client.get("/analytics/funnel")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    stages = {s["stage"]: s for s in body["stages"]}
    assert stages["mutual"]["reached"] >= 1
    assert stages["interested"]["reached"] >= stages["mutual"]["reached"]
    assert stages["suggested"]["reached"] >= stages["viewed"]["reached"]
    assert stages["mutual"]["median_hours_from_suggested"] is not None
    assert "unspecified" in body["rejection_reasons"]


def test_health_checks_database_and_responses_carry_request_id(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}
    assert len(resp.headers["x-request-id"]) == 32
    echoed = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert echoed.headers["x-request-id"] == "abc-123"
    injected = client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert injected.headers["x-request-id"] != "bad id\nwith newline"


def test_metrics_counts_requests_by_route_template(client: TestClient) -> None:
    client.get("/health")
    body = client.get("/metrics").text
    assert 'cohab_http_requests_total{method="GET",route="/health",status="200"}' in body
    assert "cohab_http_request_seconds_count" in body


def test_metrics_requires_token_when_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_TOKEN", "s3cret")
    assert client.get("/metrics").status_code == 404
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret"}).status_code == 200

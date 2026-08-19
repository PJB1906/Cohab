"""DB-backed TestClient fixtures — new territory for this repo (the existing
suite is pure Python / no live DB). Each test runs inside a SAVEPOINT on the
existing docker-compose Postgres (no separate test-DB infra) that's rolled
back on teardown, so tests never see each other's data and the DB itself
ends up unchanged. `pytest.skip`s the whole session if the DB isn't
reachable, so `pytest tests/matching` keeps working with no services running.
"""

from __future__ import annotations

import logging
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from cohab.api.deps import get_db
from cohab.db import DATABASE_URL
from cohab.main import app
from cohab.models import Institution, User, WeightSet

_engine = create_engine(DATABASE_URL)

# A valid subset of spec §8's default weight table — sums to 1, real
# attribute names, enough for the matches tests to exercise real scoring
# without transcribing all 20 rows.
DEFAULT_WEIGHTS = {
    "cleanliness_level": 0.20,
    "sleep_schedule": 0.20,
    "guests": 0.15,
    "payment_reliability": 0.15,
    "communication_style": 0.15,
    "budget_proximity": 0.15,
}


@pytest.fixture(scope="session", autouse=True)
def _require_db() -> None:
    try:
        with _engine.connect():
            pass
    except OperationalError:
        pytest.skip("database not reachable — start it with `docker compose up -d db`")


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = _engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        # `with` triggers the startup event (fits app.state.text_encoder) —
        # plain instantiation does not.
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def institution(db_session: Session) -> Institution:
    inst = Institution(name="Christ University", email_domain=f"test-{uuid.uuid4().hex[:8]}.in")
    db_session.add(inst)
    db_session.flush()
    return inst


@pytest.fixture()
def weight_set(db_session: Session) -> WeightSet:
    ws = WeightSet(version=1, source="expert", weights=DEFAULT_WEIGHTS, is_active=True)
    db_session.add(ws)
    db_session.flush()
    return ws


@pytest.fixture()
def moderator_user(
    client: TestClient,
    institution: Institution,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> tuple[uuid.UUID, str]:
    """A verified account with `is_moderator=True`. Registered through the
    real HTTP flow like every other test user (matches this suite's own
    convention), then flipped directly on the row — there's no self-service
    endpoint for it (docs/DECISIONS.md D-7.1: moderators are provisioned
    directly, not signed up). Returns (user_id, email); leaves the client's
    session logged in as this account."""
    email = f"moderator@{institution.email_domain}"
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "correct horse battery staple",
                "full_name": "Casey Moderator",
                "gender": "female",
                "seeker_type": "needs_place",
            },
        )
    user_id = uuid.UUID(resp.json()["user_id"])
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    caplog.clear()
    client.post("/auth/verify", json={"user_id": str(user_id), "code": code})

    user = db_session.get(User, user_id)
    user.is_moderator = True
    db_session.commit()
    return user_id, email

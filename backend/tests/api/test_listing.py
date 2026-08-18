"""GET /listing, PUT /listing — happy path plus the load-bearing failure
modes: unauthenticated, unverified, and needs_place (has nothing to list)."""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.models import Institution, Listing

VALID_LISTING = {
    "locality": "Koramangala",
    "rent_per_person": 18000,
    "deposit": 36000,
    "room_type": "private",
    "available_from": "2026-09-01",
    "amenities": ["wifi", "washing_machine"],
    "current_housemates": 1,
}


def _register_and_verify(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture, seeker_type: str
) -> str:
    email = f"rahul-{seeker_type}@{institution.email_domain}"
    payload = {
        "email": email,
        "password": "correct horse battery staple",
        "full_name": "Rahul Iyer",
        "gender": "male",
        "seeker_type": seeker_type,
    }
    with caplog.at_level(logging.INFO, logger="cohab.otp"):
        resp = client.post("/auth/register", json=payload)
    user_id = resp.json()["user_id"]
    code = next(r.args[1] for r in caplog.records if r.name == "cohab.otp")
    client.post("/auth/verify", json={"user_id": user_id, "code": code})
    return user_id


def test_put_listing_requires_authentication(client: TestClient) -> None:
    resp = client.put("/listing", json=VALID_LISTING)
    assert resp.status_code == 401


def test_put_listing_rejects_needs_place(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _register_and_verify(client, institution, caplog, "needs_place")
    resp = client.put("/listing", json=VALID_LISTING)
    assert resp.status_code == 400


def test_put_listing_persists_for_has_place(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _register_and_verify(client, institution, caplog, "has_place")

    resp = client.put("/listing", json=VALID_LISTING)
    assert resp.status_code == 200, resp.text
    assert resp.json()["locality"] == "Koramangala"

    listing = db_session.scalar(select(Listing).where(Listing.user_id == user_id))
    assert listing is not None
    assert listing.rent_per_person == 18000


def test_put_listing_twice_updates_rather_than_duplicates(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _register_and_verify(client, institution, caplog, "has_place")
    client.put("/listing", json=VALID_LISTING)
    resp = client.put("/listing", json={**VALID_LISTING, "rent_per_person": 20000})
    assert resp.status_code == 200

    listings = db_session.scalars(select(Listing).where(Listing.user_id == user_id)).all()
    assert len(listings) == 1
    assert listings[0].rent_per_person == 20000


def test_get_listing_before_save_is_404(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _register_and_verify(client, institution, caplog, "has_place")
    resp = client.get("/listing")
    assert resp.status_code == 404

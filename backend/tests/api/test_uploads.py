"""POST /uploads/image — Phase 5 photo uploads (build plan §4, extended
scope, see docs/DECISIONS.md)."""

from __future__ import annotations

import base64
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from cohab.models import Institution, User

PASSWORD = "correct horse battery staple"

# A minimal 1x1 transparent PNG — real bytes, not a placeholder, so
# content-type/size validation exercises an actual image payload.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNk+A8AAQUBAScY"
    "42YAAAAASUVORK5CYII="
)


def _register_and_login(client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture) -> str:
    email = f"uploader@{institution.email_domain}"
    resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Uploader",
            "gender": "female",
            "seeker_type": "needs_place",
        },
    )
    client.post("/auth/login", json={"email": email, "password": PASSWORD})
    return resp.json()["user_id"]


def test_upload_requires_authentication(client: TestClient) -> None:
    resp = client.post(
        "/uploads/image", data={"kind": "avatar"}, files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    assert resp.status_code == 401


def test_avatar_upload_sets_user_avatar_url(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _register_and_login(client, institution, caplog)
    resp = client.post(
        "/uploads/image", data={"kind": "avatar"}, files={"file": ("a.png", TINY_PNG, "image/png")}
    )
    assert resp.status_code == 200, resp.text
    url = resp.json()["url"]
    assert url.startswith("/media/")

    user = db_session.get(User, user_id)
    assert user.avatar_url == url


def test_listing_upload_does_not_touch_user_avatar(
    client: TestClient, db_session: Session, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    user_id = _register_and_login(client, institution, caplog)
    resp = client.post(
        "/uploads/image", data={"kind": "listing"}, files={"file": ("room.png", TINY_PNG, "image/png")}
    )
    assert resp.status_code == 200, resp.text

    user = db_session.get(User, user_id)
    assert user.avatar_url is None


def test_upload_rejects_unsupported_content_type(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _register_and_login(client, institution, caplog)
    resp = client.post(
        "/uploads/image",
        data={"kind": "avatar"},
        files={"file": ("a.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_oversized_file(
    client: TestClient, institution: Institution, caplog: pytest.LogCaptureFixture
) -> None:
    _register_and_login(client, institution, caplog)
    too_big = b"\x00" * (6 * 1024 * 1024)
    resp = client.post(
        "/uploads/image",
        data={"kind": "avatar"},
        files={"file": ("a.png", too_big, "image/png")},
    )
    assert resp.status_code == 400

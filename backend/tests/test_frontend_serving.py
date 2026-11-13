"""`cohab.main.serve_frontend` — the `/api` prefix strip and the
SPA-vs-API-collision avoidance a merged-origin deploy needs
(docs/DECISIONS.md). A throwaway `FRONTEND_DIST` via monkeypatch, so this
doesn't depend on whether `npm run build` has actually been run."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import cohab.main as main


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    (tmp_path / "index.html").write_text("<html>app shell</html>")
    (tmp_path / "app.js").write_text("console.log('hi')")
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path)
    return TestClient(main.app)


def test_api_prefix_is_stripped_onto_the_real_route(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_bare_api_route_is_unaffected_for_non_navigation_callers(client: TestClient) -> None:
    """TestClient sends no `Accept: text/html` by default — the same shape
    as `fetch()` — so a bare API path must still reach its real handler,
    exactly as every other test in this suite relies on."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "ok"}


def test_a_page_navigation_gets_the_app_shell_even_at_a_colliding_api_path(client: TestClient) -> None:
    """`GET /matches` is both a frontend page and a real, auth-gated API
    route. A browser hard-refresh — signalled by `Accept: text/html` — must
    get the SPA shell, not the API's 401."""
    resp = client.get("/matches", headers={"accept": "text/html,application/xhtml+xml"})
    assert resp.status_code == 200
    assert resp.text == "<html>app shell</html>"


def test_an_unmatched_path_falls_back_to_the_app_shell(client: TestClient) -> None:
    resp = client.get("/matches/some-id", headers={"accept": "text/html"})
    assert resp.status_code == 200
    assert resp.text == "<html>app shell</html>"


def test_a_built_static_asset_is_served(client: TestClient) -> None:
    resp = client.get("/app.js", headers={"accept": "*/*"})
    assert resp.status_code == 200
    assert "hi" in resp.text


def test_missing_frontend_dist_is_a_no_op(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "FRONTEND_DIST", tmp_path / "does-not-exist")
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200

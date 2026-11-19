import logging
import os
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.responses import FileResponse, JSONResponse, Response

from cohab.api.analytics import router as analytics_router
from cohab.api.auth import router as auth_router
from cohab.api.chat import router as chat_router
from cohab.api.evidence import router as evidence_router
from cohab.api.feedback import router as feedback_router
from cohab.api.listing import router as listing_router
from cohab.api.matches import router as matches_router
from cohab.api.moderation import router as moderation_router
from cohab.api.profile import router as profile_router
from cohab.api.reports import router as reports_router
from cohab.api.saved import router as saved_router
from cohab.api.study import router as study_router
from cohab.api.taste import router as taste_router
from cohab.api.uploads import router as uploads_router
from cohab.core.config import FRONTEND_DIST_DIR
from cohab.core.observability import configure_logging, metrics, new_request_id, request_id_var
from cohab.db import SessionLocal
from cohab.models import PreferenceProfile
from cohab.services.matching.text import TfidfSimilarity
from cohab.services.storage import get_image_storage, guess_content_type

# Found live: `ConsoleOTPSender` (services/otp.py) logs the OTP via
# `logging.getLogger("cohab.otp").info(...)`, which only ever reached a
# terminal under pytest's `caplog` (it force-captures regardless of level).
# Nothing configured the root logger for a real `uvicorn` run, so the code a
# developer needs to complete registration never printed — the OTP flow was
# silently unusable outside the test suite. `ConsoleOTPSender`'s own
# docstring says it exists so the flow works without real SMTP; this is what
# makes that true.
JSON_LOGS = os.environ.get("LOG_FORMAT", "text").lower() == "json"
configure_logging(json_logs=JSON_LOGS)
_access_log = logging.getLogger("cohab.access")


def _warn_if_port_already_serving() -> None:
    """Log a loud warning when something is *already* answering on our port.

    Windows lets a second `uvicorn --port 8000` bind successfully rather than
    failing with "address in use", because uvicorn does not set
    SO_EXCLUSIVEADDRUSE. Two servers then share the port and requests go to
    whichever wins the race. The symptom is baffling: a backend edit appears
    to do nothing, because the *older* process — holding pre-edit code — is
    answering some or all requests. That cost a real debugging session; see
    docs/DECISIONS.md D-13.14.

    This only warns. Refusing to start would be worse: it would break the
    legitimate `--reload` restart, where the old worker is still shutting
    down as the new one boots. A warning in the log is enough to turn a
    confusing hour into an obvious one. `run.cmd` does the actual prevention
    by freeing the port before launching.
    """
    host = os.environ.get("COHAB_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("COHAB_PORT", "8000"))
    except ValueError:
        return

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(0.35)
    try:
        already_serving = probe.connect_ex((host, port)) == 0
    except OSError:
        already_serving = False
    finally:
        probe.close()

    if already_serving:
        log = logging.getLogger("cohab.startup")
        log.warning("=" * 72)
        log.warning("Another server is ALREADY listening on %s:%s.", host, port)
        # ASCII only: this is read in a Windows console, whose default code
        # page mangles an em-dash into a replacement character.
        log.warning("On Windows both can bind, and requests go to whichever wins,")
        log.warning("so code changes may appear to have no effect. Check with:")
        log.warning("    netstat -ano | findstr :%s", port)
        log.warning("and stop the stale PID, or just use run.cmd, which frees the")
        log.warning("port before starting. (docs/DECISIONS.md D-13.14)")
        log.warning("=" * 72)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Fit the shared TF-IDF vectorizer once per process, over whatever
    lifestyle_notes exist in the DB right now (CLAUDE.md: text vectors are
    computed once and cached, never inside the match request path — this is
    the "once" for the live API). Transform-only after this; a profile saved
    later with genuinely new vocabulary is out-of-vocabulary until the next
    restart, a documented limitation (D-4.x)."""
    _warn_if_port_already_serving()
    # v2 audit: a database that is down at boot used to kill the process with
    # a 200-line traceback. Start anyway with an unfitted encoder (text
    # similarity then scores neutral, as it does for any empty note) so
    # /health can report "degraded" and the app recovers when the DB returns.
    notes: list = []
    session = SessionLocal()
    try:
        notes = [
            q.get("lifestyle_notes")
            for q in session.scalars(select(PreferenceProfile.questionnaire)).all()
        ]
    except SQLAlchemyError as exc:
        logging.getLogger("cohab.startup").error(
            "Database unreachable at startup (%s). Serving in degraded mode; "
            "start it with `docker compose up -d db` and restart.",
            type(exc).__name__,
        )
    finally:
        session.close()
    app.state.text_encoder = TfidfSimilarity().fit(notes)
    yield


app = FastAPI(title="Cohab", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(profile_router)
app.include_router(listing_router)
app.include_router(matches_router)
app.include_router(saved_router)
app.include_router(uploads_router)
app.include_router(reports_router)
app.include_router(moderation_router)
app.include_router(feedback_router)
app.include_router(analytics_router)
app.include_router(study_router)
app.include_router(evidence_router)
app.include_router(taste_router)

@app.get("/media/{name}")
def get_media(name: str) -> Response:
    """Proxies the stored image through the app rather than mounting the
    storage directory directly — works the same whether `services/storage.py`
    is backed by local disk or R2, and keeps `X-Content-Type-Options: nosniff`
    on every response, pairing the upload-time magic-byte check
    (services/uploads.py, D-10.2) with an equivalent guard on the serving
    side. `name` only ever comes from `uuid.uuid4().hex`-derived filenames
    this app itself generated, so a literal check is enough to refuse
    anything else rather than trusting path-join safety implicitly."""
    if "/" in name or ".." in name:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    contents = get_image_storage().load(name)
    if contents is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Response(
        content=contents,
        media_type=guess_content_type(name),
        headers={"X-Content-Type-Options": "nosniff"},
    )

FRONTEND_DIST = Path(FRONTEND_DIST_DIR)


def _dist_file(rel_path: str) -> Path | None:
    """Resolve `rel_path` under `FRONTEND_DIST`, refusing to escape it
    (`..` traversal). Returns None if it isn't an existing file there."""
    candidate = (FRONTEND_DIST / rel_path.lstrip("/")).resolve()
    try:
        candidate.relative_to(FRONTEND_DIST.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


@app.middleware("http")
async def serve_frontend(request: Request, call_next):
    """CLAUDE.md: "vite build, and FastAPI serves the static bundle" —
    same-origin, one deployable unit. Two gaps close here, both invisible in
    dev because Vite's own dev server (a second process) already absorbs
    them (vite.config.ts):

    1. `api/client.ts` calls every endpoint at `/api/...`, but every router
       below is registered at its bare path (`/auth/...`) — matching what
       the tests call directly, and what Vite's dev proxy already forwards
       to after stripping `/api` itself. With no proxy once this app is the
       only server, the same strip has to happen here, onto the identical
       bare path every route and test already uses — no route/test changes.
    2. Several frontend *pages* share a literal path with a real API route
       on this app (`GET /matches` the page vs. `GET /matches` the data
       endpoint; same for `/profile`, `/saved`). A hard refresh on such a
       page must render the app shell, not whatever that API route returns
       (JSON, or a 401). A real browser navigation is told apart from every
       other caller (`fetch()`, `TestClient`) by its `Accept` header — only
       navigation requests ask for `text/html` — so that's the signal used
       here, never the path, which is exactly what makes it not collide.

    Falls through to `call_next` untouched whenever there's nothing built
    to serve (`FRONTEND_DIST` missing — e.g. a backend-only dev session with
    no `npm run build` run), so this is a no-op until a build exists.
    """
    path = request.scope["path"]

    if path.startswith("/api/"):
        request.scope["path"] = path[len("/api") :]
        return await call_next(request)

    if path.startswith("/media/") or path in ("/health", "/metrics") or not FRONTEND_DIST.is_dir():
        return await call_next(request)

    wants_page = request.method in ("GET", "HEAD") and "text/html" in request.headers.get("accept", "")
    if wants_page:
        index = FRONTEND_DIST / "index.html"
        return FileResponse(index) if index.is_file() else await call_next(request)

    response = await call_next(request)
    if response.status_code == 404:
        asset = _dist_file(path)
        if asset is not None:
            return FileResponse(asset)
    return response


@app.exception_handler(OperationalError)
async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
    """v2 audit: a dropped database connection mid-request returned a bare
    500. Answer 503 with a sentence the client can show."""
    logging.getLogger("cohab.db").error("database error on %s: %s", request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=503,
        content={"detail": "Cohab is temporarily unavailable. Please try again in a moment."},
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    """v2 W1: a request ID on every log line and response, and per-route
    counters for /metrics. Registered after `serve_frontend`, so it wraps it
    and sees the final status of every request."""
    rid = new_request_id(request.headers.get("x-request-id"))
    token = request_id_var.set(rid)
    started = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        route = request.scope.get("route")
        # No route: the frontend middleware answered (app page or built
        # asset) when it succeeded, otherwise nothing matched at all.
        template = getattr(route, "path", None) or ("frontend" if status_code < 400 else "unmatched")
        elapsed = time.perf_counter() - started
        metrics.observe(request.method, template, status_code, elapsed)
        if JSON_LOGS:
            # uvicorn's own access log is plain text whatever LOG_FORMAT says
            # (D-14.21); this is the structured equivalent, carrying the
            # request ID. The route template, never the raw path, so IDs in
            # URLs do not land in logs.
            _access_log.info("%s %s %s %.1fms", request.method, template, status_code, elapsed * 1000)
        request_id_var.reset(token)


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    """v2 W1: checks the database, not just that the process is up, so a
    load balancer stops routing to an instance that lost its DB."""
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means unhealthy
        response.status_code = 503
        return {"status": "degraded", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


@app.get("/metrics", include_in_schema=False)
def get_metrics(request: Request) -> Response:
    """Prometheus text format. Needs `Authorization: Bearer $METRICS_TOKEN`
    when that variable is set; with it unset, only loopback callers."""
    expected = os.environ.get("METRICS_TOKEN")
    if expected:
        if request.headers.get("authorization") != f"Bearer {expected}":
            raise HTTPException(status.HTTP_404_NOT_FOUND)
    elif request.client is None or request.client.host not in ("127.0.0.1", "::1", "testclient"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return Response(metrics.render(), media_type="text/plain; version=0.0.4")

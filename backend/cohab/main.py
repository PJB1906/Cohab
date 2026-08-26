import logging
import os
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.responses import Response

from cohab.api.analytics import router as analytics_router
from cohab.api.auth import router as auth_router
from cohab.api.chat import router as chat_router
from cohab.api.feedback import router as feedback_router
from cohab.api.listing import router as listing_router
from cohab.api.matches import router as matches_router
from cohab.api.moderation import router as moderation_router
from cohab.api.profile import router as profile_router
from cohab.api.reports import router as reports_router
from cohab.api.saved import router as saved_router
from cohab.api.uploads import router as uploads_router
from cohab.core.config import UPLOAD_DIR
from cohab.db import SessionLocal
from cohab.models import PreferenceProfile
from cohab.services.matching.text import TfidfSimilarity

# Found live: `ConsoleOTPSender` (services/otp.py) logs the OTP via
# `logging.getLogger("cohab.otp").info(...)`, which only ever reached a
# terminal under pytest's `caplog` (it force-captures regardless of level).
# Nothing configured the root logger for a real `uvicorn` run, so the code a
# developer needs to complete registration never printed — the OTP flow was
# silently unusable outside the test suite. `ConsoleOTPSender`'s own
# docstring says it exists so the flow works without real SMTP; this is what
# makes that true.
logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")


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
    session = SessionLocal()
    try:
        notes = [
            q.get("lifestyle_notes")
            for q in session.scalars(select(PreferenceProfile.questionnaire)).all()
        ]
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

class _NoSniffStaticFiles(StaticFiles):
    """`X-Content-Type-Options: nosniff` on every served file — content
    sniffing by the browser is exactly the risk the upload-time magic-byte
    check (services/uploads.py) closes off at write time; this closes the
    matching gap on the serving side. docs/DECISIONS.md D-10.2."""

    def file_response(self, *args: object, **kwargs: object) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


# Phase 5 photo uploads — local disk, served back at /media (docs/DECISIONS.md).
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/media", _NoSniffStaticFiles(directory=UPLOAD_DIR), name="media")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

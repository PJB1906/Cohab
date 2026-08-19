import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from cohab.api.auth import router as auth_router
from cohab.api.chat import router as chat_router
from cohab.api.listing import router as listing_router
from cohab.api.matches import router as matches_router
from cohab.api.moderation import router as moderation_router
from cohab.api.profile import router as profile_router
from cohab.api.reports import router as reports_router
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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Fit the shared TF-IDF vectorizer once per process, over whatever
    lifestyle_notes exist in the DB right now (CLAUDE.md: text vectors are
    computed once and cached, never inside the match request path — this is
    the "once" for the live API). Transform-only after this; a profile saved
    later with genuinely new vocabulary is out-of-vocabulary until the next
    restart, a documented limitation (D-4.x)."""
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
app.include_router(uploads_router)
app.include_router(reports_router)
app.include_router(moderation_router)

# Phase 5 photo uploads — local disk, served back at /media (docs/DECISIONS.md).
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=UPLOAD_DIR), name="media")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

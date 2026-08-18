from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from sqlalchemy import select

from cohab.api.auth import router as auth_router
from cohab.api.listing import router as listing_router
from cohab.api.matches import router as matches_router
from cohab.api.profile import router as profile_router
from cohab.db import SessionLocal
from cohab.models import PreferenceProfile
from cohab.services.matching.text import TfidfSimilarity


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
app.include_router(profile_router)
app.include_router(listing_router)
app.include_router(matches_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

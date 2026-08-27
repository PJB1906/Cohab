"""Populate avatars and listing photos for the seeded pool.

Run: `python -m cohab.seed_photos`           (all users + all listings)
     `python -m cohab.seed_photos --limit 60` (a demo-sized subset)
     `python -m cohab.seed_photos --force`     (re-fetch, replacing existing)

Downloads once through `services/storage.py::get_image_storage()` and points
`user.avatar_url` / `listing.photos` at the resulting `/media/<name>` paths —
the same shape `services/uploads.py::save_image` produces, so the app cannot
tell these apart from a genuine upload and no serving code needed changing.

Sources, and the honest caveat (docs/DECISIONS.md D-13.10):

- `i.pravatar.cc` — photographs of real people, served by a placeholder
  service. Attaching them to synthetic profiles is fine for a local demo and
  should NOT be shipped to a public pilot: they are real faces on fabricated
  identities. A production pilot must use member-uploaded photos only.
- `picsum.photos` (Lorem Picsum) — Unsplash-derived photography under the
  Unsplash licence, used here for rooms.

Deterministic: image choice is keyed off each row's UUID, so re-running
picks the same picture for the same person, and screenshots stay stable
between runs.
"""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from cohab.db import SessionLocal
from cohab.models import Listing, User
from cohab.services.storage import ImageStorage, get_image_storage

# pravatar exposes a fixed gallery of 70 portraits addressed by index.
PRAVATAR_COUNT = 70
PHOTOS_PER_LISTING = 3
TIMEOUT = 20.0


def _stable_index(row_id: uuid.UUID, modulo: int) -> int:
    """A repeatable choice per row, so re-runs are idempotent in appearance
    as well as in effect."""
    return int(row_id.hex[:8], 16) % modulo


def _download(client: httpx.Client, url: str, storage: ImageStorage) -> str | None:
    """Fetch one image, write it under a content-addressed-ish name, and
    return its `/media/...` path. Returns None on any failure — a seed that
    aborts halfway through 1500 downloads because one host hiccupped is
    worse than one that skips a row."""
    try:
        response = client.get(url, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    content_type = response.headers.get("content-type", "")
    ext = "png" if "png" in content_type else "webp" if "webp" in content_type else "jpg"
    name = f"seed-{uuid.uuid4().hex}.{ext}"
    storage.save(name, response.content)
    return f"/media/{name}"


def seed_avatars(session: Session, client: httpx.Client, storage: ImageStorage, *, limit: int | None, force: bool) -> int:
    query = select(User).order_by(User.created_at)
    if not force:
        query = query.where(User.avatar_url.is_(None))
    if limit:
        query = query.limit(limit)

    users = list(session.scalars(query))
    print(f"  {len(users)} user(s) to process")

    done = 0
    for i, user in enumerate(users, 1):
        idx = _stable_index(user.id, PRAVATAR_COUNT) + 1
        url = _download(client, f"https://i.pravatar.cc/400?img={idx}", storage)
        if url is None:
            continue
        user.avatar_url = url
        done += 1
        if i % 50 == 0:
            session.commit()
            print(f"    {i}/{len(users)}…")
    session.commit()
    return done


def seed_listing_photos(session: Session, client: httpx.Client, storage: ImageStorage, *, limit: int | None, force: bool) -> int:
    listings = list(session.scalars(select(Listing).order_by(Listing.created_at)))
    if not force:
        listings = [listing for listing in listings if not listing.photos]
    if limit:
        listings = listings[:limit]

    print(f"  {len(listings)} listing(s) to process")

    done = 0
    for i, listing in enumerate(listings, 1):
        base = _stable_index(listing.id, 900)
        urls: list[str] = []
        for offset in range(PHOTOS_PER_LISTING):
            # `/seed/<key>/` makes Picsum return the same photo for the same
            # key, which is what keeps this deterministic across runs.
            key = f"cohab{base + offset}"
            url = _download(client, f"https://picsum.photos/seed/{key}/900/600", storage)
            if url:
                urls.append(url)
        if not urls:
            continue
        # Reassign rather than mutate: `photos` is a JSONB column, and an
        # in-place `.append()` is not seen as a change by SQLAlchemy.
        listing.photos = urls
        done += 1
        if i % 25 == 0:
            session.commit()
            print(f"    {i}/{len(listings)}…")
    session.commit()
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed avatars and listing photos.")
    parser.add_argument("--limit", type=int, default=None, help="cap rows processed (per table)")
    parser.add_argument("--force", action="store_true", help="replace images that already exist")
    parser.add_argument("--skip-avatars", action="store_true")
    parser.add_argument("--skip-listings", action="store_true")
    args = parser.parse_args()

    storage = get_image_storage()

    session = SessionLocal()
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            avatars = listings = 0
            if not args.skip_avatars:
                print("[1/2] Avatars")
                avatars = seed_avatars(session, client, storage, limit=args.limit, force=args.force)
            if not args.skip_listings:
                print("[2/2] Listing photos")
                listings = seed_listing_photos(session, client, storage, limit=args.limit, force=args.force)

        print(f"\nDone. {avatars} avatar(s), {listings} listing(s) photographed, served at /media/<name>.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())

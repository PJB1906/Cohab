"""Local-disk photo storage — build plan §4 Phase 5 (extended scope, see
docs/DECISIONS.md). No object-storage service exists anywhere in this stack;
files land under `core.config.UPLOAD_DIR` and are served back through the
`/media` StaticFiles mount (`cohab/main.py`). No resizing/thumbnailing —
flagged as a documented future step, not built for the pilot.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from cohab.core.config import MAX_UPLOAD_MB, UPLOAD_DIR
from cohab.models import User

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# docs/DECISIONS.md D-10.2: the declared `Content-Type` header is
# client-supplied and untrusted on its own — sniff the real file signature
# before writing anything to disk and serving it back at `/media/<name>`.
# Signatures, not spec-sourced (PRD/spec don't mention file validation).
_MAGIC_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    # WebP is a RIFF container: bytes 0-3 "RIFF", bytes 8-11 "WEBP".
    "image/webp": (b"RIFF",),
}


class UnsupportedImageType(Exception):
    pass


class ImageTooLarge(Exception):
    pass


def _sniff_image_type(contents: bytes) -> str | None:
    """The content-type the file's own magic bytes actually claim, or
    `None` if nothing recognized matches. WebP needs a second check at
    offset 8 beyond the RIFF prefix every RIFF-based format shares."""
    for content_type, signatures in _MAGIC_SIGNATURES.items():
        if any(contents.startswith(sig) for sig in signatures):
            if content_type == "image/webp" and contents[8:12] != b"WEBP":
                continue
            return content_type
    return None


def save_image(file: UploadFile, contents: bytes) -> str:
    """Validates and writes an already-read image upload, returning the
    served path (`/media/<name>`). `contents` is read by the caller (the
    route) rather than here, so the size check happens before this function
    ever touches disk."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedImageType(file.content_type)
    if len(contents) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ImageTooLarge(len(contents))
    if _sniff_image_type(contents) != file.content_type:
        raise UnsupportedImageType(file.content_type)

    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    name = f"{uuid.uuid4().hex}.{ext}"
    directory = Path(UPLOAD_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(contents)
    return f"/media/{name}"


def set_avatar(session: Session, user: User, url: str) -> None:
    """Applies an uploaded image's URL to a user's avatar. A standalone
    service function per CLAUDE.md's thin-route rule — `api/uploads.py`'s
    route used to mutate `user.avatar_url` and call `db.commit()` directly."""
    user.avatar_url = url
    session.commit()

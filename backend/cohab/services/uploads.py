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

from cohab.core.config import MAX_UPLOAD_MB, UPLOAD_DIR

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class UnsupportedImageType(Exception):
    pass


class ImageTooLarge(Exception):
    pass


def save_image(file: UploadFile, contents: bytes) -> str:
    """Validates and writes an already-read image upload, returning the
    served path (`/media/<name>`). `contents` is read by the caller (the
    route) rather than here, so the size check happens before this function
    ever touches disk."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise UnsupportedImageType(file.content_type)
    if len(contents) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ImageTooLarge(len(contents))

    ext = ALLOWED_CONTENT_TYPES[file.content_type]
    name = f"{uuid.uuid4().hex}.{ext}"
    directory = Path(UPLOAD_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(contents)
    return f"/media/{name}"

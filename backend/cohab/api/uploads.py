"""POST /uploads/image — build plan §4 Phase 5 (extended scope, see
docs/DECISIONS.md).

`kind="avatar"` also writes `user.avatar_url` in the same call, since an
avatar isn't part of the onboarding wizard's single-`PUT /profile` batch —
applying it immediately is simpler and matches "upload, see it applied" UX.
`kind="listing"` only returns the URL; the frontend holds it in its listing
draft and saves it with the existing `PUT /listing`.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from cohab.api.deps import get_current_user, get_db
from cohab.models import User
from cohab.services.uploads import ImageTooLarge, UnsupportedImageType, save_image, set_avatar

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("/image")
async def upload_image(
    kind: Literal["avatar", "listing"] = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    contents = await file.read()
    try:
        url = save_image(file, contents)
    except UnsupportedImageType:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "unsupported image type — use jpeg, png or webp"
        )
    except ImageTooLarge:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "image is too large")

    if kind == "avatar":
        set_avatar(db, user, url)

    return {"url": url}

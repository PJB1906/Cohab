"""Image storage behind an interface — same swap-behind-a-protocol pattern as
`OTPSender` (services/otp.py). `LocalDiskStorage` was the only implementation
through Phase 10; `R2Storage` (docs/DECISIONS.md) exists because a deploy
host with no persistent disk would otherwise silently lose every uploaded
photo on the next restart. `get_image_storage()` picks between them from
config so callers (services/uploads.py, seed_avatars.py, seed_photos.py,
main.py's `/media` route) don't need to know which is active.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Protocol, runtime_checkable

import boto3
from botocore.exceptions import ClientError

from cohab.core.config import (
    R2_ACCESS_KEY_ID,
    R2_BUCKET_NAME,
    R2_ENDPOINT_URL,
    R2_SECRET_ACCESS_KEY,
    UPLOAD_DIR,
)


def guess_content_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


@runtime_checkable
class ImageStorage(Protocol):
    def save(self, name: str, contents: bytes) -> None: ...
    def load(self, name: str) -> bytes | None: ...


class LocalDiskStorage:
    """Writes under `UPLOAD_DIR` on the local filesystem. Fine for dev and
    for a host with a real persistent disk; loses everything on redeploy
    otherwise, which is the whole reason `R2Storage` exists below."""

    def __init__(self, directory: str) -> None:
        self._dir = Path(directory)

    def save(self, name: str, contents: bytes) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / name).write_bytes(contents)

    def load(self, name: str) -> bytes | None:
        path = self._dir / name
        return path.read_bytes() if path.is_file() else None


class R2Storage:
    """Cloudflare R2 (S3-compatible). `main.py`'s `/media/{name}` route
    proxies the fetch through the app rather than exposing the R2 URL
    directly, so the nosniff response header (D-10.2) applies the same way
    regardless of which storage backend is active."""

    def __init__(self, *, endpoint_url: str, access_key_id: str, secret_access_key: str, bucket: str) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def save(self, name: str, contents: bytes) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=name, Body=contents, ContentType=guess_content_type(name)
        )

    def load(self, name: str) -> bytes | None:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=name)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise
        return response["Body"].read()


def get_image_storage() -> ImageStorage:
    """All four R2 settings present → R2 (persists across redeploys). Else
    local disk, same as every session before this one."""
    if R2_ENDPOINT_URL and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME:
        return R2Storage(
            endpoint_url=R2_ENDPOINT_URL,
            access_key_id=R2_ACCESS_KEY_ID,
            secret_access_key=R2_SECRET_ACCESS_KEY,
            bucket=R2_BUCKET_NAME,
        )
    return LocalDiskStorage(UPLOAD_DIR)

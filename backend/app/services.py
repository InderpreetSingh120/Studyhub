"""File storage for note attachments.

Local filesystem during development (`STORAGE_BACKEND=local`), S3-compatible
object storage in production (`STORAGE_BACKEND=s3`) — Cloudflare R2 and
Backblaze B2 both expose the same API, so one code path covers both.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import BinaryIO

import boto3

from .config import settings

CHUNK = 1024 * 1024


class FileTooLarge(Exception):
    """Raised when an upload exceeds `MAX_UPLOAD_BYTES`."""


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint or None,
        aws_access_key_id=settings.storage_access_key_id,
        aws_secret_access_key=settings.storage_secret_access_key,
        region_name=settings.storage_region,
    )


def local_path(key: str) -> Path:
    """Resolve a storage key to a path, refusing anything outside the upload dir."""
    path = (settings.upload_dir / key).resolve()
    if not path.is_relative_to(settings.upload_dir.resolve()):
        raise ValueError(f"invalid storage key: {key!r}")
    return path


def safe_filename(name: str) -> str:
    """Drop directory components and unusual characters from a client filename."""
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(". ")
    return name[:100] or "file"


def save_file(key: str, source: BinaryIO, content_type: str) -> int:
    """Write `source` to storage under `key` and return the number of bytes.

    The size limit is enforced while reading, so an oversized upload never
    reaches storage. Files are buffered in memory first (capped at
    `MAX_UPLOAD_BYTES`) so both backends share a single code path.
    """
    limit = settings.max_upload_bytes
    data = bytearray()
    while chunk := source.read(CHUNK):
        data += chunk
        if len(data) > limit:
            raise FileTooLarge(f"upload exceeds {limit} bytes")

    if settings.storage_backend == "s3":
        _s3().put_object(
            Bucket=settings.storage_bucket,
            Key=key,
            Body=bytes(data),
            ContentType=content_type,
        )
    else:
        path = local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return len(data)


def read_file(key: str) -> bytes:
    """Read a stored object back into memory (used to extract PDF text)."""
    if settings.storage_backend == "s3":
        response = _s3().get_object(Bucket=settings.storage_bucket, Key=key)
        return response["Body"].read()
    return local_path(key).read_bytes()


def delete_file(key: str) -> None:
    """Remove a stored object; missing objects are not an error."""
    if settings.storage_backend == "s3":
        _s3().delete_object(Bucket=settings.storage_bucket, Key=key)
        return
    path = local_path(key)
    path.unlink(missing_ok=True)
    try:
        path.parent.rmdir()  # drop the now-empty per-note folder
    except OSError:
        pass


def download_url(key: str) -> str | None:
    """External URL for the object, or None when FastAPI should serve it.

    Only S3 storage has its own origin; local files are streamed by the app.
    """
    if settings.storage_backend != "s3":
        return None
    if settings.storage_public_url:
        return f"{settings.storage_public_url}/{key}"
    return _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage_bucket, "Key": key},
        ExpiresIn=900,
    )

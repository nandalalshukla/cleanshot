"""Shared FastAPI dependencies."""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, Request, UploadFile, status

from ..config import Settings
from ..pipeline.registry import SegmenterRegistry


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_registry(request: Request) -> SegmenterRegistry:
    return request.app.state.segmenters


def require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None),
) -> None:
    if settings.api_key and not (x_api_key and secrets.compare_digest(x_api_key, settings.api_key)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")


async def read_upload(file: UploadFile, settings: Settings) -> bytes:
    """Read an upload, enforcing the configured size limit without trusting Content-Length."""
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"{file.filename or 'File'} is larger than {settings.max_upload_mb} MB",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty file")
    return data

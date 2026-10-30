"""Domain records for batches and the images inside them."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BatchStatus(StrEnum):
    DRAFT = "draft"
    """Created, still accepting uploads."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    """Every image finished (some may have failed — see counts)."""
    CANCELLED = "cancelled"


class ImageStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def finished(self) -> bool:
        return self in (ImageStatus.DONE, ImageStatus.FAILED, ImageStatus.CANCELLED)


@dataclass
class OutputFile:
    preset: str
    filename: str
    width: int
    height: int


@dataclass
class ImageRecord:
    id: str
    batch_id: str
    position: int
    filename: str
    stored_name: str
    status: ImageStatus
    created_at: float
    updated_at: float
    width: int = 0
    height: int = 0
    error: str | None = None
    attempts: int = 0
    outputs: list[OutputFile] = field(default_factory=list)
    quality: dict[str, Any] | None = None
    timings: dict[str, float] = field(default_factory=dict)


@dataclass
class BatchRecord:
    id: str
    client_id: str | None
    name: str
    status: BatchStatus
    options: dict[str, Any]
    created_at: float
    updated_at: float
    images: list[ImageRecord] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in ImageStatus}
        for img in self.images:
            out[img.status.value] += 1
        return out

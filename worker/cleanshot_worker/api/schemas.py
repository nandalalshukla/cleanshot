"""Pydantic request/response models. Mirrored by app/src/api/types.ts."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, Field

from ..jobs.models import BatchRecord, BatchStatus, ImageRecord, ImageStatus
from ..pipeline.framing import Alignment
from ..pipeline.options import ProcessOptions
from ..pipeline.presets import Preset, PresetId
from ..pipeline.segmentation import SegmentationModel


class ModelOut(BaseModel):
    id: SegmentationModel
    label: str
    description: str
    approx_size_mb: int


class PresetOut(BaseModel):
    id: PresetId
    label: str
    marketplace: str
    width: int
    height: int
    aspect: str
    background_color: str
    fill: float
    alignment: Alignment
    white_background_required: bool
    description: str

    @classmethod
    def from_preset(cls, p: Preset) -> PresetOut:
        return cls(
            id=p.id,
            label=p.label,
            marketplace=p.marketplace,
            width=p.width,
            height=p.height,
            aspect=p.aspect_label,
            background_color=p.background_color,
            fill=p.fill,
            alignment=p.alignment,
            white_background_required=p.white_background_required,
            description=p.description,
        )


# ---- batches ---------------------------------------------------------------------------------


class BatchCreate(BaseModel):
    name: str | None = Field(None, max_length=80)
    options: ProcessOptions = Field(default_factory=ProcessOptions)


class OutputOut(BaseModel):
    preset: str
    filename: str
    width: int
    height: int
    url: str


class ImageOut(BaseModel):
    id: str
    position: int
    filename: str
    status: ImageStatus
    error: str | None
    width: int
    height: int
    attempts: int
    outputs: list[OutputOut]
    quality: dict[str, Any] | None
    timings: dict[str, float]
    original_url: str
    preview_url: str | None
    cutout_url: str | None

    @classmethod
    def from_record(cls, img: ImageRecord) -> ImageOut:
        base = f"/v1/batches/{img.batch_id}/images/{img.id}"
        done = img.status is ImageStatus.DONE
        return cls(
            id=img.id,
            position=img.position,
            filename=img.filename,
            status=img.status,
            error=img.error,
            width=img.width,
            height=img.height,
            attempts=img.attempts,
            outputs=[OutputOut(**asdict(o), url=f"{base}/outputs/{o.preset}") for o in img.outputs]
            if done
            else [],
            quality=img.quality,
            timings=img.timings,
            original_url=f"{base}/original",
            preview_url=f"{base}/preview" if done else None,
            cutout_url=f"{base}/cutout" if done else None,
        )


class BatchSummary(BaseModel):
    id: str
    name: str
    status: BatchStatus
    created_at: float
    updated_at: float
    total: int
    counts: dict[str, int]
    progress: float = Field(description="Finished images / total, 0..1")
    needs_retake: int = Field(description="Images whose quality check says retake")
    warnings: int = Field(description="Images with quality warnings worth a look")
    cover_url: str | None
    download_url: str

    @classmethod
    def from_record(cls, batch: BatchRecord) -> BatchSummary:
        counts = batch.counts()
        total = len(batch.images)
        finished = sum(1 for i in batch.images if i.status.finished)
        verdicts = [(i.quality or {}).get("verdict") for i in batch.images]
        cover = next((i for i in batch.images if i.status is ImageStatus.DONE), None)
        if cover:
            cover_url = f"/v1/batches/{batch.id}/images/{cover.id}/preview"
        elif batch.images:
            cover_url = f"/v1/batches/{batch.id}/images/{batch.images[0].id}/original"
        else:
            cover_url = None
        return cls(
            id=batch.id,
            name=batch.name,
            status=batch.status,
            created_at=batch.created_at,
            updated_at=batch.updated_at,
            total=total,
            counts=counts,
            progress=round(finished / total, 4) if total else 0.0,
            needs_retake=verdicts.count("retake"),
            warnings=verdicts.count("warning"),
            cover_url=cover_url,
            download_url=f"/v1/batches/{batch.id}/download",
        )


class BatchOut(BatchSummary):
    options: ProcessOptions
    images: list[ImageOut]

    @classmethod
    def from_record(cls, batch: BatchRecord) -> BatchOut:
        summary = BatchSummary.from_record(batch)
        return cls(
            **summary.model_dump(),
            options=ProcessOptions.model_validate(batch.options),
            images=[ImageOut.from_record(i) for i in batch.images],
        )

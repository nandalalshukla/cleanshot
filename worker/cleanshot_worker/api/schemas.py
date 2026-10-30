"""Pydantic request/response models. Mirrored by app/src/api/types.ts."""

from __future__ import annotations

from pydantic import BaseModel

from ..pipeline.segmentation import SegmentationModel


class ModelOut(BaseModel):
    id: SegmentationModel
    label: str
    description: str
    approx_size_mb: int

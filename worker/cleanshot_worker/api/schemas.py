"""Pydantic request/response models. Mirrored by app/src/api/types.ts."""

from __future__ import annotations

from pydantic import BaseModel

from ..pipeline.framing import Alignment
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

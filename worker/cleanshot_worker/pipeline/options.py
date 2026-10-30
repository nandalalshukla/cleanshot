"""User-facing processing options. Shared by the API, the batch queue and the pipeline."""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .framing import Alignment
from .segmentation import SegmentationModel

HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class OutputFormat(StrEnum):
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


class ProcessOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: SegmentationModel = SegmentationModel.U2NETP
    width: int = Field(2000, ge=256, le=4096)
    height: int = Field(2000, ge=256, le=4096)
    fill: float = Field(0.85, ge=0.3, le=1.0, description="Share of the frame the product fills")
    alignment: Alignment = Alignment.CENTER
    background_color: str = "#FFFFFF"
    refine_edges: bool = True
    output_format: OutputFormat = OutputFormat.JPEG

    @field_validator("background_color")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not HEX_COLOR.match(v):
            raise ValueError("must be a hex colour like #FFFFFF")
        return "#" + v.lstrip("#").upper()

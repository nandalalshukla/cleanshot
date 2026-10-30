"""User-facing processing options. Shared by the API, the batch queue and the pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .framing import Alignment
from .presets import PresetId, get_preset
from .scene import SceneId
from .segmentation import SegmentationModel
from .shadow import ShadowStyle

HEX_COLOR = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class BackgroundMode(StrEnum):
    COLOR = "color"
    """Solid white or brand colour."""
    SCENE = "scene"
    """Generated lifestyle scene."""


class OutputFormat(StrEnum):
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


def normalize_hex(v: str) -> str:
    if not HEX_COLOR.match(v):
        raise ValueError("must be a hex colour like #FFFFFF")
    v = v.lstrip("#").upper()
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return "#" + v


@dataclass(frozen=True)
class RenderSpec:
    """Fully-resolved settings for one output image."""

    preset: PresetId
    width: int
    height: int
    fill: float
    alignment: Alignment
    background_color: str
    output_format: OutputFormat
    shadow: ShadowStyle = ShadowStyle.GROUND
    shadow_opacity: float = 0.35
    background_mode: BackgroundMode = BackgroundMode.COLOR
    scene: SceneId = SceneId.STUDIO
    scene_prompt: str | None = None

    @property
    def filename_suffix(self) -> str:
        ext = "jpg" if self.output_format is OutputFormat.JPEG else self.output_format.value
        return f"{self.preset.value}_{self.width}x{self.height}.{ext}"


class ProcessOptions(BaseModel):
    """What the seller picked in the app. Fields left as ``None`` fall back to the preset."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    model: SegmentationModel = SegmentationModel.U2NETP
    refine_edges: bool = True
    presets: list[PresetId] = Field(default_factory=lambda: [PresetId.AMAZON], min_length=1)
    custom_width: int = Field(2000, ge=256, le=4096)
    custom_height: int = Field(2000, ge=256, le=4096)

    fill: float | None = Field(None, ge=0.3, le=1.0, description="Share of frame the product fills")
    alignment: Alignment | None = None
    background_color: str | None = Field(None, description="Brand colour; overrides preset white")
    output_format: OutputFormat = OutputFormat.JPEG
    shadow: ShadowStyle = ShadowStyle.GROUND
    shadow_opacity: float = Field(0.35, ge=0.0, le=1.0)
    auto_color: bool = Field(True, description="White balance, levels and exposure fix-up")
    color_strength: float = Field(0.8, ge=0.0, le=1.0)

    background_mode: BackgroundMode = BackgroundMode.COLOR
    scene: SceneId = SceneId.STUDIO
    scene_prompt: str | None = Field(
        None, max_length=200, description="Describe the scene (used with scene='custom')"
    )
    scene_seed: int | None = Field(
        None, ge=0, le=2**31 - 1, description="Fix to reproduce a scene; default is per batch"
    )

    @field_validator("presets")
    @classmethod
    def _unique(cls, v: list[PresetId]) -> list[PresetId]:
        return list(dict.fromkeys(v))

    @field_validator("scene_prompt")
    @classmethod
    def _prompt(cls, v: str | None) -> str | None:
        v = " ".join(v.split()) if v else None
        return v or None

    @field_validator("background_color")
    @classmethod
    def _hex(cls, v: str | None) -> str | None:
        return normalize_hex(v) if v else None

    def render_specs(self) -> list[RenderSpec]:
        specs = []
        for preset_id in self.presets:
            p = get_preset(preset_id)
            custom = preset_id is PresetId.CUSTOM
            scene_mode = self.background_mode is BackgroundMode.SCENE
            # In a scene the product should stand on the surface, not float mid-frame.
            default_alignment = Alignment.BOTTOM if scene_mode else p.alignment
            specs.append(
                RenderSpec(
                    preset=preset_id,
                    width=self.custom_width if custom else p.width,
                    height=self.custom_height if custom else p.height,
                    fill=self.fill if self.fill is not None else p.fill,
                    alignment=self.alignment or default_alignment,
                    background_color=self.background_color or p.background_color,
                    output_format=self.output_format,
                    shadow=self.shadow,
                    shadow_opacity=self.shadow_opacity,
                    background_mode=self.background_mode,
                    scene=self.scene,
                    scene_prompt=self.scene_prompt,
                )
            )
        return specs

"""The end-to-end pipeline for a single photo.

    decode → segment → auto colour → refine edges
           → [per preset: crop/centre/pad → colour or generated scene → shadow → composite]
           → quality check → encode

Segmentation and refinement run once; framing and compositing run once per export preset.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from . import compose, image_io
from .color import ColorAdjustments, ColorParams, auto_color
from .framing import Placement, frame_product, mask_bbox
from .layer import Layer
from .options import BackgroundMode, ProcessOptions, RenderSpec
from .quality import QualityReport, assess
from .refine import decontaminate_edges, refine_mask
from .scene import ProceduralSceneGenerator, SceneService
from .segmentation import Segmenter
from .shadow import ShadowParams, apply_shadow, make_shadow

log = logging.getLogger(__name__)


class NoProductFoundError(ValueError):
    """Segmentation produced an empty mask."""


@dataclass
class RenderedOutput:
    spec: RenderSpec
    image: Image.Image
    placement: Placement

    def encode(self) -> bytes:
        return image_io.encode(self.image, self.spec.output_format.value)


@dataclass
class ProcessResult:
    outputs: list[RenderedOutput]
    cutout: Image.Image
    """Product cropped to its bounds on transparency, at source resolution."""
    raw_alpha: np.ndarray
    """Unrefined mask at input resolution."""
    quality: QualityReport
    color: ColorAdjustments | None = None
    timings: dict[str, float] = field(default_factory=dict)

    @property
    def primary(self) -> RenderedOutput:
        return self.outputs[0]


class _Timer:
    def __init__(self) -> None:
        self.timings: dict[str, float] = {}
        self._t = time.perf_counter()

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.timings[name] = round(self.timings.get(name, 0.0) + now - self._t, 4)
        self._t = now


def prepare_layer(
    image: Image.Image, options: ProcessOptions, segmenter: Segmenter, timer: _Timer
) -> tuple[Layer, np.ndarray, ColorAdjustments | None]:
    """Segment, colour-correct and refine.

    Returns the full-resolution product layer, the raw mask and any colour adjustments.
    Segmentation runs on the original photo (models are trained on natural images); colour
    correction then uses the mask to white-balance against the backdrop.
    """
    raw_alpha = segmenter.segment(image)
    timer.lap("segment")
    if float(raw_alpha.max(initial=0.0)) < 0.5:
        raise NoProductFoundError("No product detected in the photo")

    rgb = image_io.to_array(image)
    adjustments = None
    if options.auto_color:
        rgb, adjustments = auto_color(rgb, raw_alpha, ColorParams(strength=options.color_strength))
        timer.lap("color")

    alpha = refine_mask(raw_alpha) if options.refine_edges else raw_alpha
    layer = Layer(rgb, alpha)
    if options.refine_edges:
        layer = decontaminate_edges(layer)
    timer.lap("refine")
    return layer, raw_alpha, adjustments


_fallback_scenes: SceneService | None = None


def _default_scenes() -> SceneService:
    global _fallback_scenes
    if _fallback_scenes is None:
        _fallback_scenes = SceneService(ProceduralSceneGenerator())
    return _fallback_scenes


def background_for(spec: RenderSpec, scenes: SceneService | None, seed: int) -> np.ndarray:
    canvas = (spec.width, spec.height)
    if spec.background_mode is BackgroundMode.SCENE:
        return (scenes or _default_scenes()).render(spec.scene, spec.scene_prompt, canvas, seed)
    return compose.solid(canvas, compose.hex_to_rgb(spec.background_color))


def render(
    layer: Layer,
    spec: RenderSpec,
    timer: _Timer | None = None,
    scenes: SceneService | None = None,
    seed: int = 0,
) -> RenderedOutput:
    timer = timer or _Timer()
    canvas = (spec.width, spec.height)
    try:
        framed, placement = frame_product(layer, canvas, spec.fill, spec.alignment)
    except ValueError as exc:
        raise NoProductFoundError(str(exc)) from exc
    timer.lap("frame")

    background = background_for(spec, scenes, seed)
    timer.lap("background")
    shadow = make_shadow(
        framed.alpha, placement, ShadowParams(style=spec.shadow, opacity=spec.shadow_opacity)
    )
    if shadow is not None:
        background = apply_shadow(background, shadow)
    timer.lap("shadow")

    final = compose.over(framed, background)
    timer.lap("compose")
    return RenderedOutput(spec, image_io.to_image(final), placement)


def crop_cutout(layer: Layer) -> Image.Image:
    box = mask_bbox(layer.alpha)
    if box is None:
        return layer.to_rgba()
    return layer.to_rgba().crop((box.x0, box.y0, box.x1, box.y1))


def process_image(
    image: Image.Image,
    options: ProcessOptions,
    segmenter: Segmenter,
    scenes: SceneService | None = None,
    seed: int = 0,
) -> ProcessResult:
    """Run the whole pipeline. ``seed`` picks the generated scene (shared across a batch)."""
    timer = _Timer()
    layer, raw_alpha, adjustments = prepare_layer(image, options, segmenter, timer)
    specs = options.render_specs()
    if options.scene_seed is not None:
        seed = options.scene_seed
    outputs = [render(layer, spec, timer, scenes, seed) for spec in specs]
    target_side = max(max(s.width, s.height) * s.fill for s in specs)
    # Grade the photo as captured, so lighting advice reflects what the seller shot.
    quality = assess(image_io.to_array(image), raw_alpha, target_side=int(target_side))
    timer.lap("quality")
    log.debug("processed image in %s", timer.timings)
    return ProcessResult(
        outputs=outputs,
        cutout=crop_cutout(layer),
        raw_alpha=raw_alpha,
        quality=quality,
        color=adjustments,
        timings=timer.timings,
    )

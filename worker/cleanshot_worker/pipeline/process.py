"""The end-to-end pipeline for a single photo.

decode → segment → refine edges → crop/centre/pad → background → encode
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from . import compose, image_io
from .framing import Placement, frame_product
from .layer import Layer
from .options import ProcessOptions
from .refine import decontaminate_edges, refine_mask
from .segmentation import Segmenter

log = logging.getLogger(__name__)


class NoProductFoundError(ValueError):
    """Segmentation produced an empty mask."""


@dataclass
class ProcessResult:
    image: Image.Image
    """Final marketplace image (opaque)."""
    cutout: Image.Image
    """Framed product on a transparent canvas — useful for re-compositing client side."""
    raw_alpha: np.ndarray
    """Unrefined mask at input resolution (used by quality checks)."""
    placement: Placement
    timings: dict[str, float] = field(default_factory=dict)

    def encoded(self, options: ProcessOptions) -> bytes:
        return image_io.encode(self.image, options.output_format.value)


class _Timer:
    def __init__(self) -> None:
        self.timings: dict[str, float] = {}
        self._t = time.perf_counter()

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.timings[name] = round(now - self._t, 4)
        self._t = now


def process_image(
    image: Image.Image, options: ProcessOptions, segmenter: Segmenter
) -> ProcessResult:
    timer = _Timer()
    rgb = image_io.to_array(image)

    raw_alpha = segmenter.segment(image)
    timer.lap("segment")
    if float(raw_alpha.max(initial=0.0)) < 0.5:
        raise NoProductFoundError("No product detected in the photo")

    alpha = refine_mask(raw_alpha) if options.refine_edges else raw_alpha
    layer = Layer(rgb, alpha)
    if options.refine_edges:
        layer = decontaminate_edges(layer)
    timer.lap("refine")

    canvas = (options.width, options.height)
    try:
        framed, placement = frame_product(layer, canvas, options.fill, options.alignment)
    except ValueError as exc:
        raise NoProductFoundError(str(exc)) from exc
    timer.lap("frame")

    background = compose.solid(canvas, compose.hex_to_rgb(options.background_color))
    final = compose.over(framed, background)
    timer.lap("compose")

    log.debug("processed image in %s", timer.timings)
    return ProcessResult(
        image=image_io.to_image(final),
        cutout=framed.to_rgba(),
        raw_alpha=raw_alpha,
        placement=placement,
        timings=timer.timings,
    )

"""Auto-crop, scale and centre the product on a fixed-size canvas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np

from .layer import Layer


class Alignment(StrEnum):
    CENTER = "center"
    BOTTOM = "bottom"
    """Sit the product on an invisible floor — looks natural with a ground shadow."""


@dataclass(frozen=True)
class BBox:
    x0: int
    y0: int
    x1: int  # exclusive
    y1: int  # exclusive

    @property
    def width(self) -> int:
        return self.x1 - self.x0

    @property
    def height(self) -> int:
        return self.y1 - self.y0


@dataclass(frozen=True)
class Placement:
    """Where the product ended up on the canvas, in canvas pixels."""

    bbox: BBox
    scale: float


def mask_bbox(alpha: np.ndarray, threshold: float = 0.05) -> BBox | None:
    ys, xs = np.nonzero(alpha > threshold)
    if len(xs) == 0:
        return None
    return BBox(int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def frame_product(
    layer: Layer,
    canvas: tuple[int, int],
    fill: float = 0.85,
    alignment: Alignment = Alignment.CENTER,
    bottom_margin: float | None = None,
    max_upscale: float | None = None,
) -> tuple[Layer, Placement]:
    """Crop the product to its mask, scale it to fill ``fill`` of the canvas and place it.

    ``fill`` is the fraction of the canvas the product's longest relative side should occupy:
    the product is scaled so that it fits inside ``fill * canvas`` in both dimensions.
    Small products are upscaled to hit the target unless ``max_upscale`` caps it; the quality
    check flags heavily upscaled (soft) results instead of silently shrinking the product.
    """
    if not 0.1 <= fill <= 1.0:
        raise ValueError("fill must be between 0.1 and 1.0")
    cw, ch = canvas
    box = mask_bbox(layer.alpha)
    if box is None:
        raise ValueError("Mask is empty — no product detected")

    rgb = layer.rgb[box.y0 : box.y1, box.x0 : box.x1]
    alpha = layer.alpha[box.y0 : box.y1, box.x0 : box.x1]

    scale = min(cw * fill / box.width, ch * fill / box.height)
    if max_upscale is not None:
        scale = min(scale, max_upscale)
    nw, nh = max(1, round(box.width * scale)), max(1, round(box.height * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    rgb = cv2.resize(rgb, (nw, nh), interpolation=interp)
    alpha = np.clip(cv2.resize(alpha, (nw, nh), interpolation=interp), 0.0, 1.0)

    x = (cw - nw) // 2
    if alignment is Alignment.BOTTOM:
        margin = (1 - fill) / 2 if bottom_margin is None else bottom_margin
        y = ch - nh - round(ch * margin)
    else:
        y = (ch - nh) // 2
    y = int(np.clip(y, 0, max(ch - nh, 0)))

    out_rgb = np.zeros((ch, cw, 3), dtype=np.uint8)
    out_alpha = np.zeros((ch, cw), dtype=np.float32)
    out_rgb[y : y + nh, x : x + nw] = rgb
    out_alpha[y : y + nh, x : x + nw] = alpha
    placement = Placement(BBox(x, y, x + nw, y + nh), float(scale))
    return Layer(out_rgb, out_alpha), placement

"""Synthetic shadows. Cheap tricks that make a cut-out look photographed rather than pasted.

* ``ground`` — the product's mask squashed into a thin ellipse under its base and blurred,
  plus a tighter, darker contact shadow where it touches the floor.
* ``drop``   — the whole silhouette offset down-right and blurred (good for flat-lays).

Shadows are computed at quarter resolution (blur hides the difference) and returned as a
full-canvas float mask that darkens the background before the product is composited on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np

from .framing import Placement

_WORK_SCALE = 0.25


class ShadowStyle(StrEnum):
    NONE = "none"
    GROUND = "ground"
    DROP = "drop"


@dataclass(frozen=True)
class ShadowParams:
    style: ShadowStyle = ShadowStyle.GROUND
    opacity: float = 0.35
    squash: float = 0.08
    """Ground shadow height as a fraction of the product's height."""
    spread: float = 0.06
    """Blur radius as a fraction of the product's width."""


def _small(alpha: np.ndarray) -> np.ndarray:
    h, w = alpha.shape
    return cv2.resize(
        alpha,
        (max(1, int(w * _WORK_SCALE)), max(1, int(h * _WORK_SCALE))),
        interpolation=cv2.INTER_AREA,
    )


def _full(small: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    return cv2.resize(small, size, interpolation=cv2.INTER_LINEAR)


def _blur(img: np.ndarray, sigma: float) -> np.ndarray:
    return cv2.GaussianBlur(img, (0, 0), max(sigma, 0.5)) if sigma > 0 else img


def ground_shadow(alpha: np.ndarray, placement: Placement, params: ShadowParams) -> np.ndarray:
    h, w = alpha.shape
    box = placement.bbox
    small = _small(alpha)
    sh, sw = small.shape
    # Product footprint, in the small working space.
    x0, x1 = (
        int(box.x0 * _WORK_SCALE),
        max(int(box.x1 * _WORK_SCALE), int(box.x0 * _WORK_SCALE) + 1),
    )
    y0, y1 = (
        int(box.y0 * _WORK_SCALE),
        max(int(box.y1 * _WORK_SCALE), int(box.y0 * _WORK_SCALE) + 1),
    )
    silhouette = small[y0:y1, x0:x1]
    pw, ph = silhouette.shape[1], silhouette.shape[0]

    def squashed(height_ratio: float, width_ratio: float) -> np.ndarray:
        sq_h = max(2, int(ph * height_ratio))
        sq_w = max(2, int(pw * width_ratio))
        flat = cv2.resize(silhouette, (sq_w, sq_h), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((sh, sw), np.float32)
        cx = (x0 + x1) // 2
        # Centre the flattened silhouette on the product's base line.
        top = y1 - sq_h // 2
        left = cx - sq_w // 2
        ys, xs = slice(max(top, 0), min(top + sq_h, sh)), slice(max(left, 0), min(left + sq_w, sw))
        canvas[ys, xs] = flat[ys.start - top : ys.stop - top, xs.start - left : xs.stop - left]
        return canvas

    spread = params.spread * pw
    soft = _blur(squashed(params.squash, 1.0), spread)
    contact = _blur(squashed(params.squash * 0.35, 0.85), spread * 0.25)
    shadow = np.clip(soft * 0.75 + contact * 0.6, 0.0, 1.0)
    return np.clip(_full(shadow, (w, h)) * params.opacity, 0.0, 1.0)


def drop_shadow(alpha: np.ndarray, placement: Placement, params: ShadowParams) -> np.ndarray:
    h, w = alpha.shape
    small = _small(alpha)
    pw = placement.bbox.width * _WORK_SCALE
    offset = max(1, int(pw * 0.03))
    shifted = np.zeros_like(small)
    shifted[offset:, offset:] = small[:-offset, :-offset]
    shadow = _blur(shifted, params.spread * pw * 0.5)
    return np.clip(_full(shadow, (w, h)) * params.opacity, 0.0, 1.0)


def make_shadow(alpha: np.ndarray, placement: Placement, params: ShadowParams) -> np.ndarray | None:
    """Return an ``HxW`` shadow strength mask in ``[0, 1]`` or ``None`` for no shadow."""
    if params.style == ShadowStyle.NONE or params.opacity <= 0:
        return None
    if params.style == ShadowStyle.DROP:
        return drop_shadow(alpha, placement, params)
    return ground_shadow(alpha, placement, params)


def apply_shadow(
    background: np.ndarray, shadow: np.ndarray, color: tuple[int, int, int] = (0, 0, 0)
) -> np.ndarray:
    s = shadow[..., None]
    out = background.astype(np.float32) * (1 - s) + np.array(color, np.float32) * s
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)

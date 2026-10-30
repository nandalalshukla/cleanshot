"""Mask clean-up and edge refinement.

Raw segmentation masks tend to have three problems on phone snaps:

1. small specks of background picked up as foreground (crumbs, table texture),
2. pin-holes inside the product (glare, logos),
3. a thin halo of the original background colour along the edges.

``refine_mask`` fixes 1 and 2 and lightly feathers the edge; ``decontaminate_edges`` fixes 3 by
pulling edge colours towards the nearby product colour so the product sits cleanly on white.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .layer import Layer


@dataclass(frozen=True)
class RefineOptions:
    speck_ratio: float = 0.02
    """Drop blobs smaller than this fraction of the largest blob."""
    hole_ratio: float = 0.002
    """Fill enclosed holes smaller than this fraction of the object area (keeps mug handles)."""
    choke_px: int = 1
    """Shrink the mask edge by this many pixels to cut background halo."""
    feather_px: float = 1.2
    """Gaussian sigma applied to the edge band for a natural, anti-aliased edge."""


def _binary(alpha: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    return (alpha > threshold).astype(np.uint8)


def remove_specks(alpha: np.ndarray, ratio: float) -> np.ndarray:
    binary = _binary(alpha)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if n <= 2:  # background + at most one blob
        return alpha
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = np.zeros(n, dtype=bool)
    keep[1:] = areas >= np.max(areas) * ratio
    return np.where(keep[labels] | (binary == 0), alpha, 0.0).astype(np.float32)


def fill_small_holes(alpha: np.ndarray, ratio: float) -> np.ndarray:
    binary = _binary(alpha)
    object_area = int(binary.sum())
    if object_area == 0:
        return alpha
    inverse = 1 - binary
    n, labels, stats, _ = cv2.connectedComponentsWithStats(inverse, connectivity=4)
    h, w = binary.shape
    out = alpha.copy()
    max_hole = object_area * ratio
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        touches_border = x == 0 or y == 0 or x + bw == w or y + bh == h
        if not touches_border and area <= max_hole:
            out[labels == i] = 1.0
    return out


def refine_mask(alpha: np.ndarray, options: RefineOptions | None = None) -> np.ndarray:
    opts = options or RefineOptions()
    alpha = np.clip(alpha.astype(np.float32), 0.0, 1.0)
    alpha = remove_specks(alpha, opts.speck_ratio)
    alpha = fill_small_holes(alpha, opts.hole_ratio)

    if opts.choke_px > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (2 * opts.choke_px + 1, 2 * opts.choke_px + 1)
        )
        alpha = cv2.erode(alpha, kernel)

    if opts.feather_px > 0:
        blurred = cv2.GaussianBlur(alpha, (0, 0), opts.feather_px)
        # Only soften the transition band so solid interiors stay fully opaque.
        k = np.ones((3, 3), np.uint8)
        near_fg = np.asarray(cv2.dilate(_binary(alpha, 0.02), k), dtype=bool)
        near_bg = np.asarray(cv2.dilate(1 - _binary(alpha, 0.98), k), dtype=bool)
        alpha = np.where(near_fg & near_bg, blurred, alpha)

    return np.clip(alpha, 0.0, 1.0).astype(np.float32)


def decontaminate_edges(layer: Layer, radius: int = 6) -> Layer:
    """Replace colours of semi-transparent edge pixels with nearby solid-foreground colours."""
    solid = (layer.alpha > 0.95).astype(np.float32)
    if solid.sum() == 0:
        return layer
    rgb = layer.rgb.astype(np.float32)
    k = 2 * radius + 1
    weight = cv2.blur(solid, (k, k))
    fg_est = cv2.blur(rgb * solid[..., None], (k, k)) / np.maximum(weight, 1e-4)[..., None]
    edge = ((layer.alpha > 0.0) & (layer.alpha < 0.95) & (weight > 0.01))[..., None]
    # Blend more strongly the more transparent a pixel is.
    t = np.clip(1.0 - layer.alpha, 0.0, 1.0)[..., None]
    cleaned = np.where(edge, rgb * (1 - t) + fg_est * t, rgb)
    return Layer(np.clip(cleaned, 0, 255).astype(np.uint8), layer.alpha)

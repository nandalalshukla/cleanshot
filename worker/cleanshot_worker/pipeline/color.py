"""Automatic colour correction for product photos.

Phone snaps taken indoors usually have a colour cast (warm bulbs, cool tube lights) and are
slightly under-exposed. Corrections, in order:

1. **White balance** — the backdrop behind the product (table, wall, sheet) is the best neutral
   reference we have, so the illuminant is estimated from *background* pixels with the
   shades-of-grey method. Falls back to the whole photo when too little background is visible.
   Only part of the cast is removed and gains are clamped, so a genuinely coloured backdrop
   doesn't get "corrected" into grey.
2. **Auto levels** — stretch the product's luminance between robust black/white points.
   The same curve is applied to R, G and B so hues don't shift.
3. **Exposure** — a gamma lift when the product is still dark.
4. **Vibrance** — a gentle saturation boost that favours muted colours.

``strength`` blends the corrected result with the original (0 = off, 1 = full).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class ColorParams:
    strength: float = 1.0
    max_gain: float = 1.25
    """Clamp on per-channel white-balance gains."""
    adaptation: float = 0.6
    """How much of the estimated cast to remove (1 = fully neutral). Partial correction keeps
    the scene believable and limits damage when the backdrop is genuinely coloured (beige
    tables, wooden floors)."""
    minkowski_p: float = 6.0
    black_percentile: float = 0.5
    white_percentile: float = 99.5
    max_stretch: float = 1.6
    target_median_luma: float = 0.5
    max_gamma_lift: float = 0.35
    vibrance: float = 0.12


@dataclass(frozen=True)
class ColorAdjustments:
    """What was changed, for logging and debugging."""

    wb_gains: tuple[float, float, float]
    black_point: float
    white_point: float
    gamma: float
    reference: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _illuminant(pixels: np.ndarray, p: float) -> np.ndarray:
    """Shades-of-grey estimate of the light colour from an Nx3 float array in [0, 1]."""
    # Ignore clipped highlights and near-black pixels: they carry no colour information.
    lum = pixels.mean(axis=1)
    usable = pixels[(lum > 0.05) & (pixels.max(axis=1) < 0.98)]
    if len(usable) < 100:
        usable = pixels
    est = np.power(np.mean(np.power(usable, p), axis=0), 1.0 / p)
    return np.maximum(est, 1e-4)


def white_balance_gains(
    rgb: np.ndarray, alpha: np.ndarray | None, params: ColorParams
) -> tuple[np.ndarray, str]:
    img = rgb.reshape(-1, 3).astype(np.float32) / 255.0
    reference = "image"
    if alpha is not None:
        bg = alpha.reshape(-1) < 0.05
        if bg.mean() > 0.15:
            img = img[bg]
            reference = "background"
    # Subsample for speed: a few hundred thousand pixels give a stable estimate.
    if len(img) > 200_000:
        img = img[:: len(img) // 200_000]
    ill = _illuminant(img, params.minkowski_p)
    gains = np.power(ill.mean() / ill, params.adaptation)
    gains = np.clip(gains, 1 / params.max_gain, params.max_gain)
    gains /= gains.mean()  # keep overall brightness; levels handles exposure
    return gains.astype(np.float32), reference


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)


def _vibrance(rgb: np.ndarray, amount: float) -> np.ndarray:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)  # float32 input: S in [0, 1]
    s = hsv[..., 1]
    hsv[..., 1] = np.clip(s + amount * s * (1.0 - s), 0.0, 1.0)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def auto_color(
    rgb: np.ndarray, alpha: np.ndarray | None = None, params: ColorParams | None = None
) -> tuple[np.ndarray, ColorAdjustments]:
    """Return a colour-corrected copy of ``rgb`` (uint8 HxWx3) and what was applied."""
    params = params or ColorParams()
    if params.strength <= 0:
        return rgb, ColorAdjustments((1.0, 1.0, 1.0), 0.0, 1.0, 1.0, "off")

    src = rgb.astype(np.float32) / 255.0
    gains, reference = white_balance_gains(rgb, alpha, params)
    out = np.clip(src * gains, 0.0, 1.0)

    # Levels and exposure are measured on the product only (or whole image without a mask).
    fg = alpha > 0.5 if alpha is not None and (alpha > 0.5).any() else np.ones(rgb.shape[:2], bool)
    lum = _luma(out)[fg]
    black = float(np.percentile(lum, params.black_percentile))
    white = float(np.percentile(lum, params.white_percentile))
    # Leave photos that already use the full range alone; otherwise stretch, but never by more
    # than max_stretch, and don't crush shadows that are genuinely dark grey.
    black = 0.0 if black <= 0.02 else min(black, 0.06)
    white = 1.0 if white >= 0.92 else white / 0.97
    white = max(white, black + 1.0 / params.max_stretch)
    out = np.clip((out - black) / (white - black), 0.0, 1.0)

    median = float(np.median(_luma(out)[fg]))
    gamma = 1.0
    if 0.02 < median < params.target_median_luma:
        gamma = float(np.log(params.target_median_luma) / np.log(median))
        gamma = max(gamma, 1.0 - params.max_gamma_lift)
        out = np.power(out, gamma)

    if params.vibrance:
        out = _vibrance(out.astype(np.float32), params.vibrance)

    if params.strength < 1:
        out = src * (1 - params.strength) + out * params.strength

    result = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)
    adjustments = ColorAdjustments(
        wb_gains=tuple(round(float(g), 3) for g in gains),  # type: ignore[arg-type]
        black_point=round(black, 3),
        white_point=round(white, 3),
        gamma=round(gamma, 3),
        reference=reference,
    )
    return result, adjustments

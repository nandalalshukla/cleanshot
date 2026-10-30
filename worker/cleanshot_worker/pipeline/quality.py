"""Automatic quality checks, so sellers know which photos to retake before listing them.

Each check adds a flag with a severity:

* ``retake``  — the output is very likely unusable (tiny product, product cut off, mostly holes).
* ``warning`` — usable but worth a look (some holes, soft focus, low light, upscaled a lot).

The report also carries the raw measurements so thresholds can be tuned from real data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import cv2
import numpy as np


class Severity(StrEnum):
    WARNING = "warning"
    RETAKE = "retake"


class Verdict(StrEnum):
    OK = "ok"
    WARNING = "warning"
    RETAKE = "retake"


@dataclass(frozen=True)
class Thresholds:
    min_coverage: float = 0.03
    """Product smaller than 3% of the photo → too far away or mis-detected."""
    small_coverage: float = 0.08
    max_coverage: float = 0.92
    """Product filling the whole photo usually means the background wasn't found."""
    hole_ratio_warn: float = 0.03
    hole_ratio_retake: float = 0.15
    """Enclosed background inside the product, as a share of the product's area."""
    edge_touch_ratio: float = 0.12
    """Share of a photo border covered by the product before we call it cut off."""
    max_fragments: int = 3
    min_product_side_px: int = 500
    blur_variance: float = 60.0
    """Variance of the Laplacian along the product's outline; lower = blurrier."""
    dark_luma: float = 50.0
    bright_clip_ratio: float = 0.25
    soft_ratio: float = 0.3
    """Semi-transparent share of the mask: high means the model was unsure."""


MESSAGES: dict[str, tuple[Severity, str]] = {
    "no_product": (
        Severity.RETAKE,
        "No clear product found. Retake with the product in the centre.",
    ),
    "product_too_small": (Severity.RETAKE, "Product is tiny in the photo. Move closer and retake."),
    "product_small": (Severity.WARNING, "Product is small in the photo; details may look soft."),
    "background_not_found": (
        Severity.RETAKE,
        "Couldn't separate the product from the background. Use a plain, contrasting surface.",
    ),
    "holes_large": (Severity.RETAKE, "Parts of the product were cut out. Retake with even light."),
    "holes": (Severity.WARNING, "Some gaps in the product cut-out. Check the result."),
    "cut_off": (Severity.RETAKE, "Product is cut off at the photo edge. Fit all of it in frame."),
    "fragmented": (Severity.WARNING, "Several separate objects detected. Remove clutter nearby."),
    "low_resolution": (Severity.WARNING, "Low resolution — the export will be upscaled and soft."),
    "blurry": (Severity.WARNING, "Photo looks blurry. Hold steady or tap to focus."),
    "too_dark": (Severity.WARNING, "Photo is dark. Shoot near a window or add light."),
    "overexposed": (Severity.WARNING, "Parts are blown out. Avoid direct sunlight or flash."),
    "uncertain_edges": (Severity.WARNING, "Edges are uncertain. Try the Quality or Best model."),
}


@dataclass
class Flag:
    code: str
    severity: Severity
    message: str


@dataclass
class QualityReport:
    verdict: Verdict
    score: int
    flags: list[Flag] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _flag(code: str) -> Flag:
    severity, message = MESSAGES[code]
    return Flag(code, severity, message)


def no_product_flag() -> Flag:
    return _flag("no_product")


def _enclosed_holes(binary: np.ndarray) -> int:
    """Area of background regions fully enclosed by the product."""
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(1 - binary, connectivity=4)
    h, w = binary.shape
    total = 0
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if x > 0 and y > 0 and x + bw < w and y + bh < h:
            total += int(area)
    return total


def _border_touch(binary: np.ndarray) -> float:
    """Largest share of any single image border covered by the product."""
    return float(
        max(binary[0].mean(), binary[-1].mean(), binary[:, 0].mean(), binary[:, -1].mean())
    )


def assess(
    rgb: np.ndarray,
    raw_alpha: np.ndarray,
    target_side: int | None = None,
    thresholds: Thresholds | None = None,
) -> QualityReport:
    """Grade one photo from its RGB pixels and the *unrefined* mask.

    The raw mask is used on purpose: refinement fills small holes and removes specks, which
    would hide exactly the problems we want the seller to know about.
    """
    t = thresholds or Thresholds()
    binary = (raw_alpha > 0.5).astype(np.uint8)
    area = int(binary.sum())
    coverage = area / binary.size
    metrics: dict[str, float] = {"coverage": round(coverage, 4)}
    flags: list[Flag] = []

    if area == 0:
        return QualityReport(Verdict.RETAKE, 0, [_flag("no_product")], metrics)

    # Size in frame
    if coverage < t.min_coverage:
        flags.append(_flag("product_too_small"))
    elif coverage < t.small_coverage:
        flags.append(_flag("product_small"))
    elif coverage > t.max_coverage:
        flags.append(_flag("background_not_found"))

    # Holes inside the product
    hole_ratio = _enclosed_holes(binary) / area
    metrics["hole_ratio"] = round(hole_ratio, 4)
    if hole_ratio > t.hole_ratio_retake:
        flags.append(_flag("holes_large"))
    elif hole_ratio > t.hole_ratio_warn:
        flags.append(_flag("holes"))

    # Cut off at the edges (only meaningful when the product isn't the whole photo)
    touch = _border_touch(binary)
    metrics["border_touch"] = round(touch, 4)
    if touch > t.edge_touch_ratio and coverage <= t.max_coverage:
        flags.append(_flag("cut_off"))

    # Fragments: significant separate blobs
    n, _labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    areas = stats[1:, cv2.CC_STAT_AREA] if n > 1 else np.array([area])
    significant = int((areas >= np.max(areas) * 0.05).sum())
    metrics["fragments"] = significant
    if significant > t.max_fragments:
        flags.append(_flag("fragmented"))

    # Resolution: longest side of the product in source pixels
    ys, xs = np.nonzero(binary)
    product_side = int(max(np.ptp(xs) + 1, np.ptp(ys) + 1))
    metrics["product_side_px"] = product_side
    if product_side < t.min_product_side_px or (target_side and target_side / product_side > 4.0):
        flags.append(_flag("low_resolution"))

    # Uncertain mask
    soft_px = int(((raw_alpha > 0.05) & (raw_alpha < 0.95)).sum())
    soft = soft_px / (area + soft_px)
    metrics["soft_ratio"] = round(soft, 4)
    if soft > t.soft_ratio:
        flags.append(_flag("uncertain_edges"))

    # Image quality inside the product
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    region = binary.astype(bool)
    # Focus is judged on the outline: plain products (a white mug) have no inner texture,
    # but every in-focus product has a crisp edge against the background.
    k = np.ones((7, 7), np.uint8)
    band = (cv2.dilate(binary, k) - cv2.erode(binary, k)).astype(bool)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(lap[band].var()) if band.sum() > 50 else 0.0
    luma = float(gray[region].mean())
    clipped = float((gray[region] >= 250).mean())
    metrics.update(sharpness=round(sharpness, 1), luma=round(luma, 1), clipped=round(clipped, 4))
    if sharpness < t.blur_variance:
        flags.append(_flag("blurry"))
    if luma < t.dark_luma:
        flags.append(_flag("too_dark"))
    if clipped > t.bright_clip_ratio:
        flags.append(_flag("overexposed"))

    penalty = sum(45 if f.severity is Severity.RETAKE else 12 for f in flags)
    score = max(0, 100 - penalty)
    if any(f.severity is Severity.RETAKE for f in flags):
        verdict = Verdict.RETAKE
    elif flags:
        verdict = Verdict.WARNING
    else:
        verdict = Verdict.OK
    return QualityReport(verdict, score, flags, metrics)

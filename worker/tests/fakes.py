"""Deterministic test doubles so the suite never downloads model weights."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw


def product_photo(
    size: tuple[int, int] = (640, 480),
    box: tuple[int, int, int, int] = (220, 140, 420, 380),
    background: tuple[int, int, int] = (235, 232, 225),
    color: tuple[int, int, int] = (200, 40, 40),
) -> Image.Image:
    """A fake phone snap: an ellipse 'product' on a slightly off-white table."""
    img = Image.new("RGB", size, background)
    ImageDraw.Draw(img).ellipse(box, fill=color)
    return img


def to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


class ThresholdSegmenter:
    """Foreground = pixels far from the top-left corner colour."""

    def __init__(self, *_: object) -> None:
        self.calls = 0

    def segment(self, image: Image.Image) -> np.ndarray:
        self.calls += 1
        arr = np.asarray(image.convert("RGB"), dtype=np.float32)
        bg = arr[0, 0]
        dist = np.linalg.norm(arr - bg, axis=2)
        return (dist > 40).astype(np.float32)

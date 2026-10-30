"""The unit of work passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class Layer:
    """An RGB image with a soft alpha mask of the same height/width.

    ``rgb`` is ``uint8 HxWx3``; ``alpha`` is ``float32 HxW`` in ``[0, 1]``.
    """

    rgb: np.ndarray
    alpha: np.ndarray

    def __post_init__(self) -> None:
        if self.rgb.shape[:2] != self.alpha.shape:
            raise ValueError(f"rgb {self.rgb.shape} and alpha {self.alpha.shape} do not match")

    @property
    def size(self) -> tuple[int, int]:
        """(width, height), PIL-style."""
        h, w = self.alpha.shape
        return w, h

    def to_rgba(self) -> Image.Image:
        a = (np.clip(self.alpha, 0, 1) * 255).astype(np.uint8)
        return Image.fromarray(np.dstack([self.rgb, a]), mode="RGBA")

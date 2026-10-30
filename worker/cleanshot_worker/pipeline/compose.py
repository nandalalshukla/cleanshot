"""Alpha compositing helpers."""

from __future__ import annotations

import numpy as np

from .layer import Layer


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    if len(v) != 6:
        raise ValueError(f"Invalid hex colour: {value!r}")
    try:
        r, g, b = (int(v[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise ValueError(f"Invalid hex colour: {value!r}") from exc
    return r, g, b


def solid(size: tuple[int, int], color: tuple[int, int, int]) -> np.ndarray:
    w, h = size
    return np.full((h, w, 3), color, dtype=np.uint8)


def over(top: Layer, background: np.ndarray) -> np.ndarray:
    """Composite ``top`` over an opaque RGB background of the same size."""
    if background.shape[:2] != top.alpha.shape:
        raise ValueError("Background size must match layer size")
    a = top.alpha[..., None]
    out = top.rgb.astype(np.float32) * a + background.astype(np.float32) * (1 - a)
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)

"""Decoding/encoding helpers. Everything inside the pipeline works on RGB uint8 / float32 arrays."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

# Register HEIF/HEIC (iPhone) support when the optional plugin is installed.
try:  # pragma: no cover - optional dependency
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass


class InvalidImageError(ValueError):
    """The uploaded bytes are not a decodable image."""


def load_image(data: bytes, max_side: int | None = None) -> Image.Image:
    """Decode bytes into an upright RGB image, optionally capping the longest side."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("File is not a supported image") from exc

    # Phone cameras store rotation in EXIF; bake it in so masks line up with what users see.
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, rgba)
    img = img.convert("RGB")

    if max_side and max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return img


def to_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


def to_image(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def cutout_rgba(rgb: np.ndarray, alpha: np.ndarray) -> Image.Image:
    """Combine RGB uint8 and alpha float [0,1] into a transparent PNG-ready image."""
    a = (np.clip(alpha, 0.0, 1.0) * 255).astype(np.uint8)
    return Image.fromarray(np.dstack([rgb, a]), mode="RGBA")


def encode(img: Image.Image, fmt: str = "PNG", quality: int = 92) -> bytes:
    buf = io.BytesIO()
    fmt = fmt.upper()
    if fmt in ("JPEG", "JPG"):
        img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    elif fmt == "WEBP":
        img.save(buf, "WEBP", quality=quality, method=4)
    else:
        img.save(buf, "PNG", optimize=True)
    return buf.getvalue()

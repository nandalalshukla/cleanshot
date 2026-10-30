"""Generated scene backgrounds.

Instead of a flat colour, the product can be placed into a generated lifestyle scene
(marble counter, wooden table, festive Diwali setup…). Two backends implement
``SceneGenerator``:

* ``DiffusionSceneGenerator`` — a small text-to-image diffusion model (``stabilityai/sd-turbo``
  by default: 1-4 denoising steps, runs on CPU in seconds and on a GPU in well under one).
  Requires the optional ``diffusion`` extra (torch + diffusers).
* ``ProceduralSceneGenerator`` — dependency-free studio backdrops (paper sweep, gradients,
  table surfaces). Used automatically when the diffusion extra isn't installed, so the
  feature degrades gracefully instead of failing.

Scenes are generated once per (prompt, seed, size) and cached, so every photo in a batch
shares the same backdrop — consistent catalogs look more professional.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import cv2
import numpy as np

log = logging.getLogger(__name__)


class SceneId(StrEnum):
    STUDIO = "studio"
    MARBLE = "marble"
    WOOD = "wood"
    LINEN = "linen"
    NATURE = "nature"
    FESTIVE = "festive"
    KITCHEN = "kitchen"
    BEACH = "beach"
    CUSTOM = "custom"


@dataclass(frozen=True)
class ScenePreset:
    id: SceneId
    label: str
    prompt: str
    # Procedural fallback look: top colour, floor colour, texture kind.
    top: tuple[int, int, int]
    floor: tuple[int, int, int]
    texture: str = "none"


_STYLE = (
    "empty surface in the foreground, nothing on it, professional product photography "
    "backdrop, shallow depth of field, soft natural light, high quality"
)

SCENES: dict[SceneId, ScenePreset] = {
    s.id: s
    for s in [
        ScenePreset(
            SceneId.STUDIO,
            "Studio",
            f"seamless light grey paper studio sweep, {_STYLE}",
            (236, 236, 238),
            (214, 214, 218),
        ),
        ScenePreset(
            SceneId.MARBLE,
            "Marble",
            f"white marble countertop, bright airy room, {_STYLE}",
            (232, 230, 226),
            (222, 220, 216),
            "marble",
        ),
        ScenePreset(
            SceneId.WOOD,
            "Wooden table",
            f"rustic oak wooden table top, warm cozy blurred interior, {_STYLE}",
            (214, 196, 172),
            (150, 104, 66),
            "wood",
        ),
        ScenePreset(
            SceneId.LINEN,
            "Linen",
            f"soft beige linen fabric backdrop, {_STYLE}",
            (230, 220, 204),
            (216, 204, 186),
            "linen",
        ),
        ScenePreset(
            SceneId.NATURE,
            "Nature",
            f"flat mossy stone in a sunlit forest, green bokeh, {_STYLE}",
            (170, 196, 150),
            (110, 120, 96),
            "noise",
        ),
        ScenePreset(
            SceneId.FESTIVE,
            "Festive",
            f"Diwali festive table, glowing diyas and marigold flowers at the edges, "
            f"warm golden bokeh lights, {_STYLE}",
            (120, 52, 32),
            (176, 98, 40),
            "bokeh",
        ),
        ScenePreset(
            SceneId.KITCHEN,
            "Kitchen",
            f"modern bright kitchen countertop, blurred kitchen background, {_STYLE}",
            (226, 230, 232),
            (196, 198, 200),
            "noise",
        ),
        ScenePreset(
            SceneId.BEACH,
            "Beach",
            f"smooth sand at golden hour, blurred sea and sky behind, {_STYLE}",
            (176, 206, 226),
            (226, 200, 160),
            "noise",
        ),
        ScenePreset(SceneId.CUSTOM, "Custom", _STYLE, (230, 230, 230), (205, 205, 205)),
    ]
}


def scene_prompt(scene: SceneId, custom_prompt: str | None) -> str:
    if scene is SceneId.CUSTOM or custom_prompt:
        text = (custom_prompt or "").strip()
        return f"{text}, {_STYLE}" if text else SCENES[SceneId.CUSTOM].prompt
    return SCENES[scene].prompt


def seed_for(key: str) -> int:
    """Stable 31-bit seed from any string (e.g. the batch id)."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


class SceneUnavailableError(RuntimeError):
    pass


class SceneGenerator(Protocol):
    backend: str
    model: str | None

    def generate(self, scene: SceneId, prompt: str, size: tuple[int, int], seed: int) -> np.ndarray:
        """Return an RGB uint8 image of exactly ``size`` (width, height)."""
        ...


def cover_resize(img: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Scale to cover ``size`` and centre-crop (like CSS ``object-fit: cover``)."""
    w, h = size
    ih, iw = img.shape[:2]
    scale = max(w / iw, h / ih)
    nw, nh = max(w, round(iw * scale)), max(h, round(ih * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    resized = cv2.resize(img, (nw, nh), interpolation=interp)
    x, y = (nw - w) // 2, (nh - h) // 2
    return resized[y : y + h, x : x + w]


# ---- procedural backend ---------------------------------------------------------------------


class ProceduralSceneGenerator:
    """Studio backdrops built from gradients and noise. Fast, deterministic, no ML deps."""

    backend = "procedural"
    model: str | None = None

    def generate(self, scene: SceneId, prompt: str, size: tuple[int, int], seed: int) -> np.ndarray:
        preset = SCENES[scene]
        w, h = size
        rng = np.random.default_rng(seed)
        y = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
        horizon = 0.62
        # Smooth wall→floor blend around the horizon (a paper "sweep").
        t = np.clip((y - (horizon - 0.12)) / 0.24, 0.0, 1.0)
        t = t * t * (3 - 2 * t)
        top = np.array(preset.top, np.float32)
        floor = np.array(preset.floor, np.float32)
        img = np.broadcast_to(top * (1 - t) + floor * t, (h, w, 3)).copy()

        small = (max(8, w // 8), max(8, h // 8))
        if preset.texture == "wood":
            grain = rng.normal(0, 1, (small[1], 4)).astype(np.float32)
            grain = cv2.resize(grain, (w, h), interpolation=cv2.INTER_CUBIC)
            img += (grain * 10.0)[..., None] * (t > 0.5)
        elif preset.texture == "marble":
            veins = rng.normal(0, 1, (small[1] // 2 + 1, small[0] // 2 + 1)).astype(np.float32)
            veins = cv2.resize(veins, (w, h), interpolation=cv2.INTER_CUBIC)
            img -= (np.abs(np.sin(veins * 3.0)) < 0.08)[..., None] * 18.0
        elif preset.texture == "bokeh":
            for _ in range(28):
                cx, cy = rng.integers(0, w), rng.integers(0, int(h * horizon))
                r = int(rng.integers(max(4, w // 60), max(6, w // 18)))
                glow = np.zeros((h, w), np.float32)
                cv2.circle(glow, (int(cx), int(cy)), r, 1.0, -1)
                glow = cv2.GaussianBlur(glow, (0, 0), r * 0.35)
                img += glow[..., None] * np.array((255, 190, 90), np.float32) * 0.55
        elif preset.texture in ("noise", "linen"):
            n = rng.normal(0, 1, (small[1], small[0])).astype(np.float32)
            n = cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
            img += n[..., None] * (6.0 if preset.texture == "noise" else 3.0)

        # Vignette for a studio-lit look.
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        d = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h * 0.55) / (h * 0.65)) ** 2)
        img *= (1.0 - 0.18 * np.clip(d - 0.5, 0, 1))[..., None]
        return np.clip(img, 0, 255).astype(np.uint8)


# ---- diffusion backend ----------------------------------------------------------------------


class DiffusionSceneGenerator:
    """Text-to-image with a small diffusion model via 🤗 diffusers.

    The model renders at ~512 px (what sd-turbo was trained on) with the canvas aspect ratio;
    the result is upscaled to the export size and lightly blurred, which reads as a natural
    shallow depth of field behind a sharp product.
    """

    backend = "diffusion"

    def __init__(
        self, model: str = "stabilityai/sd-turbo", steps: int = 2, device: str = "auto"
    ) -> None:
        try:
            import torch
            from diffusers import AutoPipelineForText2Image
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise SceneUnavailableError(
                "Install the diffusion extra: pip install 'cleanshot-worker[diffusion]'"
            ) from exc

        self.model = model
        self.steps = steps
        if device == "auto":
            device = (
                "cuda"
                if torch.cuda.is_available()
                else ("mps" if torch.backends.mps.is_available() else "cpu")
            )
        self.device = device
        dtype = torch.float16 if device == "cuda" else torch.float32
        log.info("Loading scene model %s on %s (first use downloads weights)", model, device)
        self._torch = torch
        self._pipe = AutoPipelineForText2Image.from_pretrained(model, torch_dtype=dtype)
        self._pipe.to(device)
        self._pipe.set_progress_bar_config(disable=True)
        self._lock = threading.Lock()  # diffusers pipelines are not thread-safe

    @staticmethod
    def render_size(size: tuple[int, int], base: int = 512) -> tuple[int, int]:
        """~base² pixels with the canvas aspect ratio, in multiples of 64."""
        w, h = size
        scale = (base * base / (w * h)) ** 0.5
        return max(256, round(w * scale / 64) * 64), max(256, round(h * scale / 64) * 64)

    def generate(self, scene: SceneId, prompt: str, size: tuple[int, int], seed: int) -> np.ndarray:
        gw, gh = self.render_size(size)
        with self._lock:
            generator = self._torch.Generator(device="cpu").manual_seed(seed)
            result = self._pipe(
                prompt=prompt,
                num_inference_steps=self.steps,
                guidance_scale=0.0,  # turbo models are trained without CFG
                width=gw,
                height=gh,
                generator=generator,
            )
        rgb = np.asarray(result.images[0].convert("RGB"))
        out = cover_resize(rgb, size)
        return cv2.GaussianBlur(out, (0, 0), max(1.0, size[0] / 900))


# ---- caching facade -------------------------------------------------------------------------


class SceneService:
    """Picks a backend and caches generated scenes."""

    def __init__(self, generator: SceneGenerator, cache_size: int = 32) -> None:
        self.generator = generator
        self._cache: OrderedDict[tuple[str, int, int, int], np.ndarray] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()
        self._inflight: dict[tuple[str, int, int, int], threading.Lock] = {}

    @property
    def backend(self) -> str:
        return self.generator.backend

    def render(
        self, scene: SceneId, custom_prompt: str | None, size: tuple[int, int], seed: int
    ) -> np.ndarray:
        prompt = scene_prompt(scene, custom_prompt)
        key = (f"{scene}|{prompt}", seed, *size)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            # One generation per key even when several photos ask at once.
            key_lock = self._inflight.setdefault(key, threading.Lock())
        with key_lock:
            with self._lock:
                if key in self._cache:
                    return self._cache[key]
            img = self.generator.generate(scene, prompt, size, seed)
            with self._lock:
                self._cache[key] = img
                self._cache.move_to_end(key)
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
                self._inflight.pop(key, None)
        return img


def create_scene_service(backend: str, model: str, steps: int, device: str) -> SceneService:
    """``backend``: ``auto`` (diffusion when installed), ``diffusion`` or ``procedural``.

    The diffusion model is loaded lazily on first use so start-up stays fast.
    """
    if backend == "procedural":
        return SceneService(ProceduralSceneGenerator())
    if backend == "auto":
        try:
            import diffusers  # noqa: F401
            import torch  # noqa: F401
        except ImportError:
            log.info("diffusers/torch not installed: using procedural scene backgrounds")
            return SceneService(ProceduralSceneGenerator())
    return SceneService(LazyDiffusion(model, steps, device))


class LazyDiffusion:
    """Defers loading the (large) diffusion model until the first scene is requested."""

    backend = "diffusion"

    def __init__(self, model: str, steps: int, device: str) -> None:
        self.model = model
        self._args = (model, steps, device)
        self._impl: DiffusionSceneGenerator | None = None
        self._lock = threading.Lock()

    def generate(self, scene: SceneId, prompt: str, size: tuple[int, int], seed: int) -> np.ndarray:
        with self._lock:
            if self._impl is None:
                self._impl = DiffusionSceneGenerator(*self._args)
        return self._impl.generate(scene, prompt, size, seed)

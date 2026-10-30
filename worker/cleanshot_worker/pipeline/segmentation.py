"""Salient-object segmentation backed by rembg.

Two families of models are exposed:

* ``u2netp`` (~4.7 MB) — very fast, good enough for most boxed/solid products.
* ``isnet-general-use`` / ``birefnet-general-lite`` (~170 MB+) — slower but much better edges
  for hair, fabric, fur and jewellery.

Sessions are created lazily and cached per model; ONNX Runtime sessions are safe to share
between threads, so one session serves every worker thread.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


class SegmentationModel(StrEnum):
    U2NETP = "u2netp"
    ISNET = "isnet-general-use"
    BIREFNET_LITE = "birefnet-general-lite"


@dataclass(frozen=True)
class ModelInfo:
    id: SegmentationModel
    label: str
    description: str
    approx_size_mb: int


MODEL_CATALOG: dict[SegmentationModel, ModelInfo] = {
    SegmentationModel.U2NETP: ModelInfo(
        SegmentationModel.U2NETP, "Fast", "Quick cut-outs for solid products.", 5
    ),
    SegmentationModel.ISNET: ModelInfo(
        SegmentationModel.ISNET, "Quality", "Cleaner edges for fabric and hair.", 170
    ),
    SegmentationModel.BIREFNET_LITE: ModelInfo(
        SegmentationModel.BIREFNET_LITE, "Best", "Finest detail for jewellery and fur.", 210
    ),
}


class Segmenter(Protocol):
    """Anything that can turn an RGB image into a soft foreground mask."""

    def segment(self, image: Image.Image) -> np.ndarray:
        """Return an ``HxW`` float32 alpha mask in ``[0, 1]`` aligned with ``image``."""
        ...


class RembgSegmenter:
    def __init__(self, model: SegmentationModel | str = SegmentationModel.U2NETP) -> None:
        self.model = SegmentationModel(model)
        self._session = _get_session(self.model)

    def segment(self, image: Image.Image) -> np.ndarray:
        from rembg import remove

        mask = remove(image, session=self._session, only_mask=True)
        if not isinstance(mask, Image.Image):  # pragma: no cover - rembg returns PIL for PIL input
            mask = Image.fromarray(np.asarray(mask))
        if mask.size != image.size:
            mask = mask.resize(image.size, Image.Resampling.BILINEAR)
        return np.asarray(mask.convert("L"), dtype=np.float32) / 255.0


_sessions: dict[SegmentationModel, object] = {}
_sessions_lock = threading.Lock()


def _get_session(model: SegmentationModel) -> object:
    with _sessions_lock:
        session = _sessions.get(model)
        if session is None:
            from rembg import new_session

            started = time.perf_counter()
            log.info("Loading segmentation model %s (first use downloads weights)", model.value)
            session = new_session(model.value)
            _sessions[model] = session
            log.info("Loaded %s in %.1fs", model.value, time.perf_counter() - started)
        return session


def warm_up(models: list[SegmentationModel | str]) -> None:
    """Load (and download, if needed) models ahead of time so the first request isn't slow."""
    for m in models:
        _get_session(SegmentationModel(m))


if __name__ == "__main__":  # python -m cleanshot_worker.pipeline.segmentation u2netp isnet-...
    import sys

    logging.basicConfig(level=logging.INFO)
    warm_up(sys.argv[1:] or [SegmentationModel.U2NETP])

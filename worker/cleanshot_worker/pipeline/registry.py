"""Provides segmenters by model id; swappable so tests and future backends can inject their own."""

from __future__ import annotations

import threading
from collections.abc import Callable

from .segmentation import RembgSegmenter, SegmentationModel, Segmenter

SegmenterFactory = Callable[[SegmentationModel], Segmenter]


class SegmenterRegistry:
    def __init__(self, factory: SegmenterFactory = RembgSegmenter) -> None:
        self._factory = factory
        self._cache: dict[SegmentationModel, Segmenter] = {}
        self._lock = threading.Lock()

    def get(self, model: SegmentationModel | str) -> Segmenter:
        key = SegmentationModel(model)
        with self._lock:
            if key not in self._cache:
                self._cache[key] = self._factory(key)
            return self._cache[key]

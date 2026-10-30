"""In-process work queue backed by a thread pool.

The job store is the source of truth: the queue only carries image ids, and processors
atomically claim an image before working on it, so duplicate submissions are harmless and
a restart simply re-submits whatever the store says is unfinished.

For multi-machine deployments, swap this for RQ/Celery: the processor is a plain callable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, handler: Callable[[str], None], concurrency: int = 2) -> None:
        self._handler = handler
        self._concurrency = max(1, concurrency)
        self._pool: ThreadPoolExecutor | None = None

    def start(self) -> None:
        if self._pool is None:
            self._pool = ThreadPoolExecutor(self._concurrency, thread_name_prefix="cleanshot")
            log.info("Job queue started with %d worker thread(s)", self._concurrency)

    def stop(self, wait: bool = True) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=wait, cancel_futures=True)
            self._pool = None

    def submit(self, image_id: str) -> None:
        if self._pool is None:
            raise RuntimeError("Queue is not running")
        self._pool.submit(self._run, image_id)

    def submit_many(self, image_ids: list[str]) -> None:
        for image_id in image_ids:
            self.submit(image_id)

    def _run(self, image_id: str) -> None:
        try:
            self._handler(image_id)
        except Exception:  # the handler records failures itself; never kill the pool thread
            log.exception("Unhandled error in job %s", image_id)

"""Deletes expired batches so the worker's disk doesn't fill up."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from .files import BatchFiles
from .store import JobStore

log = logging.getLogger(__name__)


def sweep(store: JobStore, batches_dir: Path, ttl_hours: float) -> int:
    cutoff = time.time() - ttl_hours * 3600
    expired = store.batches_older_than(cutoff)
    for batch_id in expired:
        BatchFiles(batches_dir, batch_id).remove()
        store.delete_batch(batch_id)
    if expired:
        log.info("Janitor removed %d expired batch(es)", len(expired))
    return len(expired)


class Janitor:
    def __init__(
        self, store: JobStore, batches_dir: Path, ttl_hours: float, interval_s: float = 3600
    ) -> None:
        self._args = (store, batches_dir, ttl_hours)
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, name="cleanshot-janitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                sweep(*self._args)
            except Exception:
                log.exception("Janitor sweep failed")
            self._stop.wait(self._interval)

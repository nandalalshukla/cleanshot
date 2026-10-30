"""Batch use-cases. The HTTP layer calls these; they coordinate the store, files and queue."""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..pipeline import image_io
from ..pipeline.options import ProcessOptions
from .files import BatchFiles
from .models import BatchRecord, BatchStatus, ImageRecord, ImageStatus
from .processor import save_preview
from .queue import JobQueue
from .store import JobStore, NotFoundError, new_id

FORMAT_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "HEIF": ".heic", "MPO": ".jpg"}


class ConflictError(Exception):
    """The request is not allowed in the batch's current state."""


class LimitError(Exception):
    """A configured limit (e.g. images per batch) would be exceeded."""


@dataclass
class BatchService:
    store: JobStore
    queue: JobQueue
    batches_dir: Path
    max_images_per_batch: int
    max_input_side: int

    def files(self, batch_id: str) -> BatchFiles:
        return BatchFiles(self.batches_dir, batch_id)

    # ---- lookups ------------------------------------------------------------------------

    def get(self, batch_id: str, client_id: str | None) -> BatchRecord:
        batch = self.store.get_batch(batch_id)
        # Client ids are not secrets; they only keep phones sharing a worker from seeing
        # each other's batches. Authentication is the API key.
        if client_id and batch.client_id and batch.client_id != client_id:
            raise NotFoundError(batch_id)
        return batch

    def get_image(self, batch_id: str, image_id: str, client_id: str | None) -> ImageRecord:
        self.get(batch_id, client_id)
        img = self.store.get_image(image_id)
        if img.batch_id != batch_id:
            raise NotFoundError(image_id)
        return img

    # ---- lifecycle ----------------------------------------------------------------------

    def create(
        self, name: str | None, options: ProcessOptions, client_id: str | None
    ) -> BatchRecord:
        name = name or time.strftime("Batch %d %b %H:%M")
        batch = self.store.create_batch(name, options.model_dump(mode="json"), client_id)
        self.files(batch.id).ensure()
        return batch

    def add_image(
        self, batch_id: str, filename: str, data: bytes, position: int | None = None
    ) -> ImageRecord:
        batch = self.store.get_batch(batch_id, with_images=False)
        if batch.status is not BatchStatus.DRAFT:
            raise ConflictError("Photos can only be added before processing starts")
        if self.store.count_images(batch_id) >= self.max_images_per_batch:
            raise LimitError(f"A batch can hold at most {self.max_images_per_batch} photos")

        image_id = new_id()
        stored_name, img = self._save_input(batch_id, image_id, data)
        return self.store.add_image(
            batch_id, image_id, filename or stored_name, stored_name, *img.size, position=position
        )

    def start(self, batch_id: str) -> BatchRecord:
        batch = self.store.get_batch(batch_id)
        if batch.status is BatchStatus.CANCELLED:
            raise ConflictError("Batch was cancelled")
        if not batch.images:
            raise ConflictError("Add at least one photo first")
        queued = self.store.set_status_where(batch_id, ImageStatus.QUEUED, (ImageStatus.UPLOADED,))
        if queued or batch.status is BatchStatus.DRAFT:
            self.store.set_batch_status(batch_id, BatchStatus.PROCESSING)
        self.queue.submit_many(queued)
        self.store.refresh_batch_status(batch_id)
        return self.store.get_batch(batch_id)

    def cancel(self, batch_id: str) -> BatchRecord:
        self.store.set_status_where(
            batch_id, ImageStatus.CANCELLED, (ImageStatus.UPLOADED, ImageStatus.QUEUED)
        )
        self.store.set_batch_status(batch_id, BatchStatus.CANCELLED)
        return self.store.get_batch(batch_id)

    def retry(self, batch_id: str, image_id: str | None = None) -> BatchRecord:
        """Re-queue failed (and cancelled) images — or one specific image."""
        batch = self.store.get_batch(batch_id)
        if batch.status is BatchStatus.DRAFT:
            raise ConflictError("Batch has not been started")
        if image_id:
            img = self.store.get_image(image_id)
            if img.batch_id != batch_id:
                raise NotFoundError(image_id)
            if img.status in (ImageStatus.QUEUED, ImageStatus.PROCESSING):
                raise ConflictError("Photo is already being processed")
            self.store.update_image(image_id, status=ImageStatus.QUEUED, error=None)
            ids = [image_id]
        else:
            ids = self.store.set_status_where(
                batch_id, ImageStatus.QUEUED, (ImageStatus.FAILED, ImageStatus.CANCELLED)
            )
        if ids:
            self.store.set_batch_status(batch_id, BatchStatus.PROCESSING)
            self.queue.submit_many(ids)
        return self.store.get_batch(batch_id)

    def replace_image(
        self, batch_id: str, image_id: str, filename: str, data: bytes
    ) -> ImageRecord:
        """Swap in a retaken photo. Started batches re-process it straight away."""
        batch = self.store.get_batch(batch_id, with_images=False)
        old = self.store.get_image(image_id)
        if old.batch_id != batch_id:
            raise NotFoundError(image_id)
        if old.status is ImageStatus.PROCESSING:
            raise ConflictError("Photo is being processed — try again in a moment")

        files = self.files(batch_id)
        files.remove_image(image_id, old.stored_name)
        stored_name, img = self._save_input(batch_id, image_id, data)
        started = batch.status is not BatchStatus.DRAFT
        self.store.update_image(
            image_id,
            filename=filename or old.filename,
            stored_name=stored_name,
            width=img.width,
            height=img.height,
            status=ImageStatus.QUEUED if started else ImageStatus.UPLOADED,
            error=None,
            outputs=[],
            quality=None,
            timings={},
        )
        if started:
            self.store.set_batch_status(batch_id, BatchStatus.PROCESSING)
            self.queue.submit(image_id)
        return self.store.get_image(image_id)

    def delete_image(self, batch_id: str, image_id: str) -> None:
        img = self.store.get_image(image_id)
        if img.batch_id != batch_id:
            raise NotFoundError(image_id)
        self.store.delete_image(image_id)
        self.files(batch_id).remove_image(image_id, img.stored_name)
        self.store.refresh_batch_status(batch_id)

    def delete(self, batch_id: str) -> None:
        self.store.set_status_where(
            batch_id, ImageStatus.CANCELLED, (ImageStatus.UPLOADED, ImageStatus.QUEUED)
        )
        self.store.delete_batch(batch_id)
        self.files(batch_id).remove()

    # ---- helpers ------------------------------------------------------------------------

    def _save_input(self, batch_id: str, image_id: str, data: bytes) -> tuple[str, Image.Image]:
        img = image_io.load_image(data, self.max_input_side)  # validates the upload
        fmt = (Image.open(io.BytesIO(data)).format or "JPEG").upper()
        stored_name = f"{image_id}{FORMAT_EXT.get(fmt, '.img')}"
        files = self.files(batch_id)
        files.ensure()
        files.input(stored_name).write_bytes(data)
        save_preview(img, files.thumb(image_id), side=480)
        return stored_name, img

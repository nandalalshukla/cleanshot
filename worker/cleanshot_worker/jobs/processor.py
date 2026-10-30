"""Processes one queued image: load → pipeline → write outputs → update the store."""

from __future__ import annotations

import contextlib
import logging
import shutil
from pathlib import Path

from PIL import Image

from ..pipeline import image_io
from ..pipeline.options import ProcessOptions
from ..pipeline.process import NoProductFoundError, process_image
from ..pipeline.quality import QualityReport, Verdict, no_product_flag
from ..pipeline.registry import SegmenterRegistry
from .files import BatchFiles
from .models import ImageStatus, OutputFile
from .store import JobStore, NotFoundError

log = logging.getLogger(__name__)

PREVIEW_SIDE = 640


def save_preview(img: Image.Image, path: Path, side: int = PREVIEW_SIDE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    preview = img.convert("RGB").copy()
    preview.thumbnail((side, side), Image.Resampling.LANCZOS)
    preview.save(path, "JPEG", quality=82)


class ImageProcessor:
    def __init__(
        self,
        store: JobStore,
        registry: SegmenterRegistry,
        batches_dir: Path,
        max_input_side: int,
    ) -> None:
        self.store = store
        self.registry = registry
        self.batches_dir = batches_dir
        self.max_input_side = max_input_side

    def __call__(self, image_id: str) -> None:
        record = self.store.claim_image(image_id)
        if record is None:
            return  # cancelled, deleted, or already handled
        try:
            batch = self.store.get_batch(record.batch_id, with_images=False)
        except NotFoundError:
            return
        files = BatchFiles(self.batches_dir, batch.id)
        out_dir = files.output_dir(image_id)

        try:
            options = ProcessOptions.model_validate(batch.options)
            img = image_io.load_image(
                files.input(record.stored_name).read_bytes(), self.max_input_side
            )
            result = process_image(img, options, self.registry.get(options.model))

            shutil.rmtree(out_dir, ignore_errors=True)
            out_dir.mkdir(parents=True, exist_ok=True)
            outputs: list[OutputFile] = []
            for rendered in result.outputs:
                name = rendered.spec.filename_suffix
                files.output(image_id, name).write_bytes(rendered.encode())
                outputs.append(
                    OutputFile(
                        rendered.spec.preset.value, name, rendered.spec.width, rendered.spec.height
                    )
                )
            save_preview(result.primary.image, files.preview(image_id))
            result.cutout.save(files.cutout(image_id), "PNG", optimize=True)

            self.store.update_image(
                image_id,
                status=ImageStatus.DONE,
                error=None,
                outputs=outputs,
                quality=result.quality.to_dict(),
                timings=result.timings,
            )
        except NoProductFoundError as exc:
            self._fail(
                image_id,
                f"{exc}. Try a photo with the product clearly in frame.",
                quality=QualityReport(Verdict.RETAKE, 0, [no_product_flag()]).to_dict(),
            )
        except image_io.InvalidImageError as exc:
            self._fail(image_id, str(exc))
        except Exception:
            log.exception("Processing failed for image %s", image_id)
            self._fail(image_id, "Processing failed unexpectedly. Please retry.")
        finally:
            files.zip.unlink(missing_ok=True)
            with contextlib.suppress(NotFoundError):  # batch deleted mid-flight
                self.store.refresh_batch_status(batch.id)

    def _fail(self, image_id: str, message: str, quality: dict | None = None) -> None:
        self.store.update_image(image_id, status=ImageStatus.FAILED, error=message, quality=quality)

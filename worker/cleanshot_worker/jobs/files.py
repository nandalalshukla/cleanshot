"""On-disk layout for a batch.

data/batches/<batch_id>/
    input/<image_id>.<ext>          original upload
    thumbs/<image_id>.jpg           small preview of the original
    output/<image_id>/<preset>.jpg  one file per export preset
    output/<image_id>/preview.jpg   small preview of the primary output
    output/<image_id>/cutout.png    transparent cut-out
    cleanshot-<batch_id>.zip        download bundle (rebuilt when stale)
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_stem(filename: str, fallback: str) -> str:
    stem = Path(filename).stem
    stem = _SAFE.sub("-", stem).strip("-._")[:60]
    return stem or fallback


@dataclass(frozen=True)
class BatchFiles:
    root: Path
    batch_id: str

    @property
    def dir(self) -> Path:
        return self.root / self.batch_id

    def input(self, stored_name: str) -> Path:
        return self.dir / "input" / stored_name

    def thumb(self, image_id: str) -> Path:
        return self.dir / "thumbs" / f"{image_id}.jpg"

    def output_dir(self, image_id: str) -> Path:
        return self.dir / "output" / image_id

    def output(self, image_id: str, filename: str) -> Path:
        return self.output_dir(image_id) / filename

    def preview(self, image_id: str) -> Path:
        return self.output_dir(image_id) / "preview.jpg"

    def cutout(self, image_id: str) -> Path:
        return self.output_dir(image_id) / "cutout.png"

    @property
    def zip(self) -> Path:
        return self.dir / f"cleanshot-{self.batch_id}.zip"

    def ensure(self) -> None:
        for sub in ("input", "thumbs", "output"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)

    def remove_image(self, image_id: str, stored_name: str) -> None:
        self.input(stored_name).unlink(missing_ok=True)
        self.thumb(image_id).unlink(missing_ok=True)
        shutil.rmtree(self.output_dir(image_id), ignore_errors=True)
        self.zip.unlink(missing_ok=True)

    def remove(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

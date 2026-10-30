"""Builds the downloadable ZIP for a batch."""

from __future__ import annotations

import csv
import io
import os
import tempfile
import zipfile
from pathlib import Path

from .files import BatchFiles, safe_stem
from .models import BatchRecord, ImageStatus


def _unique(name: str, used: set[str]) -> str:
    candidate, n = name, 2
    while candidate in used:
        candidate = f"{name}-{n}"
        n += 1
    used.add(candidate)
    return candidate


def build_zip(batch: BatchRecord, files: BatchFiles) -> Path:
    """Write ``files.zip`` with one folder per preset plus a CSV report.

    JPEG/PNG data is already compressed, so files are stored rather than deflated.
    The archive is written to a temp file and renamed so readers never see a partial ZIP.
    """
    files.dir.mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    report = io.StringIO()
    writer = csv.writer(report)
    writer.writerow(["original", "status", "outputs", "quality_flags", "error"])

    fd, tmp = tempfile.mkstemp(dir=files.dir, suffix=".zip.part")
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
            for img in batch.images:
                stem = _unique(safe_stem(img.filename, f"photo-{img.position + 1}"), used)
                written = []
                if img.status is ImageStatus.DONE:
                    for out in img.outputs:
                        src = files.output(img.id, out.filename)
                        if not src.exists():
                            continue
                        folder = Path(out.filename).stem  # e.g. amazon_2000x2000
                        arcname = f"{folder}/{stem}{Path(out.filename).suffix}"
                        zf.write(src, arcname)
                        written.append(arcname)
                flags = ";".join(f["code"] for f in (img.quality or {}).get("flags", []))
                writer.writerow(
                    [img.filename, img.status.value, " ".join(written), flags, img.error or ""]
                )
            zf.writestr("report.csv", report.getvalue(), compress_type=zipfile.ZIP_DEFLATED)
        os.replace(tmp, files.zip)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return files.zip


def ensure_zip(batch: BatchRecord, files: BatchFiles) -> Path:
    """Return a ZIP that reflects the batch's current state, rebuilding it if stale."""
    path = files.zip
    newest = max([batch.updated_at, *(i.updated_at for i in batch.images)], default=0.0)
    if path.exists() and path.stat().st_mtime >= newest:
        return path
    return build_zip(batch, files)

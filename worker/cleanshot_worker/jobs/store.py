"""SQLite-backed job store.

SQLite (WAL mode) keeps the worker dependency-free and survives restarts: images that were
queued or mid-flight when the process stopped are re-queued on start-up. Every call opens its
own short-lived connection, so the store is safe to use from the API and processing threads.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .models import BatchRecord, BatchStatus, ImageRecord, ImageStatus, OutputFile

SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id          TEXT PRIMARY KEY,
    client_id   TEXT,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL,
    options     TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batches_client ON batches(client_id, created_at);

CREATE TABLE IF NOT EXISTS images (
    id           TEXT PRIMARY KEY,
    batch_id     TEXT NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    filename     TEXT NOT NULL,
    stored_name  TEXT NOT NULL,
    status       TEXT NOT NULL,
    width        INTEGER NOT NULL DEFAULT 0,
    height       INTEGER NOT NULL DEFAULT 0,
    error        TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    outputs      TEXT NOT NULL DEFAULT '[]',
    quality      TEXT,
    timings      TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_images_batch ON images(batch_id, position);
CREATE INDEX IF NOT EXISTS idx_images_status ON images(status);
"""


def new_id() -> str:
    return uuid.uuid4().hex[:16]


class NotFoundError(KeyError):
    pass


class JobStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    # ---- batches -------------------------------------------------------------------------

    def create_batch(
        self, name: str, options: dict[str, Any], client_id: str | None
    ) -> BatchRecord:
        now = time.time()
        batch = BatchRecord(new_id(), client_id, name, BatchStatus.DRAFT, options, now, now)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?)",
                (batch.id, client_id, name, batch.status, json.dumps(options), now, now),
            )
        return batch

    def get_batch(self, batch_id: str, with_images: bool = True) -> BatchRecord:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
            if row is None:
                raise NotFoundError(batch_id)
            batch = _batch_from_row(row)
            if with_images:
                rows = conn.execute(
                    "SELECT * FROM images WHERE batch_id = ? ORDER BY position, created_at",
                    (batch_id,),
                ).fetchall()
                batch.images = [_image_from_row(r) for r in rows]
        return batch

    def list_batches(self, client_id: str | None, limit: int = 50) -> list[BatchRecord]:
        with self._conn() as conn:
            if client_id:
                rows = conn.execute(
                    "SELECT * FROM batches WHERE client_id = ? ORDER BY created_at DESC LIMIT ?",
                    (client_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM batches ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            batches = [_batch_from_row(r) for r in rows]
            for b in batches:
                img_rows = conn.execute(
                    "SELECT * FROM images WHERE batch_id = ? ORDER BY position, created_at", (b.id,)
                ).fetchall()
                b.images = [_image_from_row(r) for r in img_rows]
        return batches

    def set_batch_status(self, batch_id: str, status: BatchStatus) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE batches SET status = ?, updated_at = ? WHERE id = ?",
                (status, time.time(), batch_id),
            )

    def delete_batch(self, batch_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM batches WHERE id = ?", (batch_id,))

    def batches_older_than(self, cutoff: float) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT id FROM batches WHERE updated_at < ?", (cutoff,)).fetchall()
        return [r["id"] for r in rows]

    def refresh_batch_status(self, batch_id: str) -> None:
        """Mark a processing batch completed once every image has finished.

        Done in one statement so a concurrent retry can't be overwritten by a stale read.
        """
        unfinished = (ImageStatus.UPLOADED, ImageStatus.QUEUED, ImageStatus.PROCESSING)
        with self._conn() as conn:
            conn.execute(
                """UPDATE batches SET status = ?, updated_at = ?
                   WHERE id = ? AND status = ? AND NOT EXISTS (
                       SELECT 1 FROM images WHERE batch_id = ? AND status IN (?, ?, ?))""",
                (
                    BatchStatus.COMPLETED,
                    time.time(),
                    batch_id,
                    BatchStatus.PROCESSING,
                    batch_id,
                    *unfinished,
                ),
            )

    # ---- images --------------------------------------------------------------------------

    def add_image(
        self,
        batch_id: str,
        image_id: str,
        filename: str,
        stored_name: str,
        width: int,
        height: int,
        position: int | None = None,
    ) -> ImageRecord:
        """Insert an image. ``position`` lets clients that upload in parallel keep their order."""
        now = time.time()
        with self._conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            pos = position
            if pos is None:
                pos = conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 FROM images WHERE batch_id = ?",
                    (batch_id,),
                ).fetchone()[0]
            conn.execute(
                """INSERT INTO images (id, batch_id, position, filename, stored_name, status,
                       width, height, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    image_id,
                    batch_id,
                    pos,
                    filename,
                    stored_name,
                    ImageStatus.UPLOADED,
                    width,
                    height,
                    now,
                    now,
                ),
            )
            conn.execute("UPDATE batches SET updated_at = ? WHERE id = ?", (now, batch_id))
            conn.execute("COMMIT")
        return self.get_image(image_id)

    def get_image(self, image_id: str) -> ImageRecord:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            raise NotFoundError(image_id)
        return _image_from_row(row)

    def count_images(self, batch_id: str) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM images WHERE batch_id = ?", (batch_id,)
            ).fetchone()[0]

    def update_image(self, image_id: str, **fields: Any) -> None:
        if not fields:
            return
        encoded = {}
        for key, value in fields.items():
            if key == "outputs":
                value = json.dumps([asdict(o) for o in value])
            elif key in ("quality", "timings"):
                value = json.dumps(value) if value is not None else None
            encoded[key] = value
        encoded["updated_at"] = time.time()
        cols = ", ".join(f"{k} = ?" for k in encoded)
        with self._conn() as conn:
            conn.execute(f"UPDATE images SET {cols} WHERE id = ?", (*encoded.values(), image_id))

    def claim_image(self, image_id: str) -> ImageRecord | None:
        """Atomically move a queued image to processing. Returns None if it was not queued."""
        with self._conn() as conn:
            cur = conn.execute(
                """UPDATE images SET status = ?, attempts = attempts + 1, updated_at = ?
                   WHERE id = ? AND status = ?""",
                (ImageStatus.PROCESSING, time.time(), image_id, ImageStatus.QUEUED),
            )
            if cur.rowcount == 0:
                return None
        return self.get_image(image_id)

    def set_status_where(
        self, batch_id: str, new: ImageStatus, current: tuple[ImageStatus, ...]
    ) -> list[str]:
        marks = ",".join("?" * len(current))
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id FROM images WHERE batch_id = ? AND status IN ({marks})",
                (batch_id, *current),
            ).fetchall()
            ids = [r["id"] for r in rows]
            conn.executemany(
                "UPDATE images SET status = ?, error = NULL, updated_at = ? WHERE id = ?",
                [(new, time.time(), i) for i in ids],
            )
        return ids

    def delete_image(self, image_id: str) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM images WHERE id = ?", (image_id,))

    def unfinished_image_ids(self) -> list[str]:
        """Images that should be (re)queued after a restart."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE images SET status = ? WHERE status = ?",
                (ImageStatus.QUEUED, ImageStatus.PROCESSING),
            )
            rows = conn.execute(
                "SELECT id FROM images WHERE status = ? ORDER BY created_at",
                (ImageStatus.QUEUED,),
            ).fetchall()
        return [r["id"] for r in rows]


def _batch_from_row(row: sqlite3.Row) -> BatchRecord:
    return BatchRecord(
        id=row["id"],
        client_id=row["client_id"],
        name=row["name"],
        status=BatchStatus(row["status"]),
        options=json.loads(row["options"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _image_from_row(row: sqlite3.Row) -> ImageRecord:
    return ImageRecord(
        id=row["id"],
        batch_id=row["batch_id"],
        position=row["position"],
        filename=row["filename"],
        stored_name=row["stored_name"],
        status=ImageStatus(row["status"]),
        width=row["width"],
        height=row["height"],
        error=row["error"],
        attempts=row["attempts"],
        outputs=[OutputFile(**o) for o in json.loads(row["outputs"])],
        quality=json.loads(row["quality"]) if row["quality"] else None,
        timings=json.loads(row["timings"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

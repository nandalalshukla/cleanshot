#!/usr/bin/env python
"""Compare segmentation models side by side.

Runs every image in a folder through each model, then writes:

* ``<out>/<image>__<model>.png``  — the cut-out on a checkerboard
* ``<out>/<image>__compare.jpg``   — original + every model in one strip
* ``<out>/report.csv``             — per image/model timing and mask statistics

Usage::

    python scripts/compare_models.py photos/ --out compare/ \
        --models u2netp isnet-general-use birefnet-general-lite
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from cleanshot_worker.pipeline import image_io
from cleanshot_worker.pipeline.segmentation import RembgSegmenter, SegmentationModel

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def checkerboard(size: tuple[int, int], cell: int = 16) -> Image.Image:
    w, h = size
    board = Image.new("RGB", size, (255, 255, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, h, cell):
        for x in range((y // cell) % 2 * cell, w, cell * 2):
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(220, 220, 220))
    return board


def mask_stats(alpha: np.ndarray) -> dict[str, float]:
    fg = alpha > 0.5
    return {
        "coverage": float(fg.mean()),
        # Share of semi-transparent pixels: higher = softer, more detailed edges.
        "soft_edge_ratio": float(((alpha > 0.05) & (alpha < 0.95)).sum() / max(fg.sum(), 1)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("input", type=Path, help="Folder of product photos")
    parser.add_argument("--out", type=Path, default=Path("compare"))
    parser.add_argument(
        "--models",
        nargs="+",
        default=[SegmentationModel.U2NETP.value, SegmentationModel.ISNET.value],
        choices=[m.value for m in SegmentationModel],
    )
    parser.add_argument("--max-side", type=int, default=1600)
    args = parser.parse_args()

    paths = sorted(p for p in args.input.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not paths:
        raise SystemExit(f"No images found in {args.input}")
    args.out.mkdir(parents=True, exist_ok=True)

    segmenters = {m: RembgSegmenter(m) for m in args.models}
    rows: list[dict[str, object]] = []

    for path in paths:
        img = image_io.load_image(path.read_bytes(), args.max_side)
        rgb = image_io.to_array(img)
        tiles = [img]
        for name, seg in segmenters.items():
            started = time.perf_counter()
            alpha = seg.segment(img)
            elapsed = time.perf_counter() - started

            board = checkerboard(img.size)
            board.paste(image_io.cutout_rgba(rgb, alpha), mask=image_io.cutout_rgba(rgb, alpha))
            board.save(args.out / f"{path.stem}__{name}.png")
            tiles.append(board)
            rows.append(
                {"image": path.name, "model": name, "seconds": round(elapsed, 3)}
                | {k: round(v, 4) for k, v in mask_stats(alpha).items()}
            )
            print(f"{path.name:30s} {name:24s} {elapsed:6.2f}s")

        strip = Image.new("RGB", (img.width * len(tiles), img.height), "white")
        for i, tile in enumerate(tiles):
            strip.paste(tile, (i * img.width, 0))
        strip.thumbnail((2400, 2400))
        strip.save(args.out / f"{path.stem}__compare.jpg", quality=88)

    with (args.out / "report.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    print("\nAverage seconds per image:")
    for name in segmenters:
        times = [float(r["seconds"]) for r in rows if r["model"] == name]  # type: ignore[arg-type]
        print(f"  {name:24s} {sum(times) / len(times):.2f}s")
    print(f"\nWrote results to {args.out}/")


if __name__ == "__main__":
    main()

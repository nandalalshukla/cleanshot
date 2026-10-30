from __future__ import annotations

import io
import json

import numpy as np
import pytest
from PIL import Image

from cleanshot_worker.pipeline.framing import Alignment, frame_product, mask_bbox
from cleanshot_worker.pipeline.layer import Layer
from cleanshot_worker.pipeline.options import ProcessOptions
from cleanshot_worker.pipeline.process import NoProductFoundError, process_image
from cleanshot_worker.pipeline.refine import (
    decontaminate_edges,
    fill_small_holes,
    refine_mask,
    remove_specks,
)

from .fakes import ThresholdSegmenter, product_photo, to_bytes


def square_mask(h=100, w=100, box=(20, 30, 60, 80)) -> np.ndarray:
    m = np.zeros((h, w), np.float32)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = 1.0
    return m


def test_remove_specks_drops_tiny_blobs_only():
    m = square_mask()
    m[2:4, 2:4] = 1.0  # speck
    out = remove_specks(m, 0.02)
    assert out[3, 3] == 0
    assert out[50, 40] == 1


def test_fill_small_holes_keeps_large_openings():
    m = square_mask(200, 200, (20, 20, 180, 180))
    m[50:52, 50:52] = 0  # pin-hole
    m[90:140, 90:140] = 0  # big opening (e.g. mug handle)
    out = fill_small_holes(m, 0.002)
    assert out[51, 51] == 1
    assert out[110, 110] == 0


def test_refine_mask_softens_edges_but_keeps_interior_opaque():
    out = refine_mask(square_mask())
    assert out[55, 40] == pytest.approx(1.0)
    assert out[0, 0] == 0
    edge = out[55, 18:24]
    assert ((edge > 0) & (edge < 1)).any()


def test_decontaminate_edges_pulls_halo_towards_product_colour():
    rgb = np.full((50, 50, 3), 255, np.uint8)
    rgb[10:40, 10:40] = (200, 0, 0)
    alpha = square_mask(50, 50, (10, 10, 40, 40))
    alpha[10:40, 9] = 0.5  # half-transparent edge column with white (background) colour
    out = decontaminate_edges(Layer(rgb, alpha))
    assert out.rgb[25, 9, 1] < 200  # less white, more red


def test_mask_bbox():
    b = mask_bbox(square_mask())
    assert (b.x0, b.y0, b.x1, b.y1) == (20, 30, 60, 80)
    assert mask_bbox(np.zeros((5, 5), np.float32)) is None


@pytest.mark.parametrize("canvas", [(1000, 1000), (1080, 1350), (1200, 800)])
def test_frame_product_fills_85_percent_and_centres(canvas):
    layer = Layer(np.zeros((100, 100, 3), np.uint8), square_mask())
    framed, placement = frame_product(layer, canvas, fill=0.85)
    cw, ch = canvas
    box = placement.bbox
    # Longest relative side hits 85%, other side fits inside.
    assert max(box.width / cw, box.height / ch) == pytest.approx(0.85, abs=0.01)
    assert box.width <= cw * 0.85 + 1 and box.height <= ch * 0.85 + 1
    # Centred within a pixel.
    assert abs((box.x0 + box.x1) / 2 - cw / 2) <= 1
    assert abs((box.y0 + box.y1) / 2 - ch / 2) <= 1
    assert framed.size == canvas


def test_frame_product_bottom_alignment_sits_on_floor():
    layer = Layer(np.zeros((100, 100, 3), np.uint8), square_mask())
    _, placement = frame_product(layer, (1000, 1000), fill=0.8, alignment=Alignment.BOTTOM)
    assert placement.bbox.y1 == 1000 - 100  # margin = (1 - fill) / 2


def test_frame_product_rejects_empty_mask():
    layer = Layer(np.zeros((10, 10, 3), np.uint8), np.zeros((10, 10), np.float32))
    with pytest.raises(ValueError):
        frame_product(layer, (100, 100))


def test_process_image_produces_white_square():
    opts = ProcessOptions(presets=["custom"], custom_width=800, custom_height=800)
    result = process_image(product_photo(), opts, ThresholdSegmenter())
    assert result.primary.image.size == (800, 800)
    px = np.asarray(result.primary.image)
    assert tuple(px[5, 5]) == (255, 255, 255)
    assert px[400, 400, 0] > 150 and px[400, 400, 1] < 100  # red product in the middle


def test_process_image_raises_without_product():
    blank = Image.new("RGB", (200, 200), (240, 240, 240))
    with pytest.raises(NoProductFoundError):
        process_image(blank, ProcessOptions(), ThresholdSegmenter())


def test_process_endpoint_honours_options(client):
    res = client.post(
        "/v1/process",
        files={"file": ("p.jpg", to_bytes(product_photo()), "image/jpeg")},
        data={
            "options": json.dumps(
                {
                    "presets": ["custom"],
                    "custom_width": 600,
                    "custom_height": 900,
                    "output_format": "png",
                    "background_color": "#0f0",
                }
            )
        },
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(res.content))
    assert img.size == (600, 900)
    assert img.convert("RGB").getpixel((2, 2)) == (0, 255, 0)


def test_process_endpoint_validates_options(client):
    res = client.post(
        "/v1/process",
        files={"file": ("p.jpg", to_bytes(product_photo()), "image/jpeg")},
        data={"options": json.dumps({"fill": 5})},
    )
    assert res.status_code == 422

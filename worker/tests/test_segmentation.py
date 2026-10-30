from __future__ import annotations

import io
import os

import numpy as np
import pytest
from PIL import Image

from cleanshot_worker.pipeline import image_io
from cleanshot_worker.pipeline.segmentation import SegmentationModel

from .fakes import product_photo, to_bytes


def test_load_image_applies_exif_rotation_and_caps_size():
    img = product_photo(size=(800, 400))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° CW on display
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)

    loaded = image_io.load_image(buf.getvalue(), max_side=300)
    assert loaded.mode == "RGB"
    assert loaded.size == (150, 300)  # rotated to portrait, then capped


def test_load_image_flattens_transparency_onto_white():
    rgba = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    loaded = image_io.load_image(to_bytes(rgba, "PNG"))
    assert loaded.getpixel((5, 5)) == (255, 255, 255)


def test_load_image_rejects_garbage():
    with pytest.raises(image_io.InvalidImageError):
        image_io.load_image(b"not an image")


def test_models_endpoint_lists_catalog(client):
    res = client.get("/v1/models")
    assert res.status_code == 200
    assert {m["id"] for m in res.json()} == {m.value for m in SegmentationModel}


def test_remove_background_returns_transparent_png(client):
    res = client.post(
        "/v1/remove-background",
        files={"file": ("p.jpg", to_bytes(product_photo()), "image/jpeg")},
    )
    assert res.status_code == 200
    out = Image.open(io.BytesIO(res.content))
    assert out.mode == "RGBA"
    alpha = np.asarray(out)[..., 3]
    assert alpha[0, 0] == 0 and alpha[260, 320] == 255


def test_remove_background_rejects_non_image(client):
    res = client.post("/v1/remove-background", files={"file": ("x.jpg", b"nope", "image/jpeg")})
    assert res.status_code == 415


def test_api_key_is_enforced(settings, registry):
    from fastapi.testclient import TestClient

    from cleanshot_worker.main import create_app

    settings.api_key = "s3cret"
    with TestClient(create_app(settings, registry)) as c:
        assert c.get("/v1/models").status_code == 401
        assert c.get("/v1/models", headers={"X-API-Key": "s3cret"}).status_code == 200
        assert c.get("/health").status_code == 200  # health stays public for probes


@pytest.mark.skipif(not os.getenv("CLEANSHOT_RUN_MODEL_TESTS"), reason="downloads model weights")
@pytest.mark.parametrize("model", [SegmentationModel.U2NETP])
def test_real_rembg_model_segments_product(model):
    from cleanshot_worker.pipeline.segmentation import RembgSegmenter

    alpha = RembgSegmenter(model).segment(product_photo())
    assert alpha.shape == (480, 640)
    assert alpha[260, 320] > 0.5
    assert alpha[10, 10] < 0.5

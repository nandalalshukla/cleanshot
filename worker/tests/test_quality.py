from __future__ import annotations

import cv2
import numpy as np
import pytest

from cleanshot_worker.pipeline.quality import Verdict, assess


def textured(h=1000, w=1000, seed=0):
    """Sharp, mid-grey texture so blur/exposure checks pass by default."""
    rng = np.random.default_rng(seed)
    return rng.integers(60, 200, size=(h, w, 3), dtype=np.uint8)


def mask_box(h=1000, w=1000, box=(250, 250, 750, 750)):
    m = np.zeros((h, w), np.float32)
    x0, y0, x1, y1 = box
    m[y0:y1, x0:x1] = 1.0
    return m


def codes(report):
    return {f.code for f in report.flags}


def test_good_photo_passes():
    r = assess(textured(), mask_box())
    assert r.verdict is Verdict.OK and r.score == 100 and not r.flags


def test_empty_mask_needs_retake():
    r = assess(textured(), np.zeros((1000, 1000), np.float32))
    assert r.verdict is Verdict.RETAKE and codes(r) == {"no_product"}


def test_tiny_product_needs_retake():
    r = assess(textured(), mask_box(box=(490, 490, 540, 540)))
    assert "product_too_small" in codes(r)
    assert r.verdict is Verdict.RETAKE


def test_holes_are_flagged_by_size():
    m = mask_box()
    m[400:450, 400:450] = 0  # 1% of product → fine
    assert "holes" not in codes(assess(textured(), m))
    m[300:500, 300:500] = 0  # 16% → retake
    assert "holes_large" in codes(assess(textured(), m))
    m2 = mask_box()
    m2[400:500, 400:500] = 0  # 4% → warning
    assert "holes" in codes(assess(textured(), m2))


def test_cut_off_product():
    r = assess(textured(), mask_box(box=(0, 200, 600, 800)))
    assert "cut_off" in codes(r)


def test_background_not_found():
    r = assess(textured(), np.ones((1000, 1000), np.float32))
    assert "background_not_found" in codes(r)
    assert "cut_off" not in codes(r)


def test_blurry_dark_and_overexposed():
    flat = np.full((1000, 1000, 3), 20, np.uint8)
    assert {"blurry", "too_dark"} <= codes(assess(flat, mask_box()))


def test_plain_product_with_crisp_edge_is_not_blurry():
    img = np.full((1000, 1000, 3), 230, np.uint8)
    img[250:750, 250:750] = (120, 60, 40)  # flat colour, sharp outline
    assert "blurry" not in codes(assess(img, mask_box()))
    soft = cv2.GaussianBlur(img, (0, 0), 6)
    assert "blurry" in codes(assess(soft, mask_box()))
    white = np.full((1000, 1000, 3), 255, np.uint8)
    assert "overexposed" in codes(assess(white, mask_box()))


def test_low_resolution_and_upscale():
    small = assess(textured(400, 400), mask_box(400, 400, (100, 100, 300, 300)))
    assert "low_resolution" in codes(small)  # product only 200 px across
    # 500 px product: 3.4x upscale is acceptable, 5x is not.
    assert "low_resolution" not in codes(assess(textured(), mask_box(), target_side=1700))
    assert "low_resolution" in codes(assess(textured(), mask_box(), target_side=2500))


@pytest.mark.parametrize("n_blobs,flagged", [(2, False), (5, True)])
def test_fragmented(n_blobs, flagged):
    m = np.zeros((1000, 1000), np.float32)
    for i in range(n_blobs):
        m[100:300, 50 + i * 180 : 200 + i * 180] = 1
    assert ("fragmented" in codes(assess(textured(), m))) is flagged


def test_uncertain_edges():
    m = mask_box() * 0.6
    m[400:600, 400:600] = 1.0
    assert "uncertain_edges" in codes(assess(textured(), m))

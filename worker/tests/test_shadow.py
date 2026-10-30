from __future__ import annotations

import numpy as np

from cleanshot_worker.pipeline.framing import frame_product
from cleanshot_worker.pipeline.layer import Layer
from cleanshot_worker.pipeline.options import ProcessOptions
from cleanshot_worker.pipeline.process import process_image
from cleanshot_worker.pipeline.shadow import ShadowParams, ShadowStyle, apply_shadow, make_shadow

from .fakes import ThresholdSegmenter, product_photo


def framed_square():
    alpha = np.zeros((200, 200), np.float32)
    alpha[50:150, 60:140] = 1
    return frame_product(Layer(np.zeros((200, 200, 3), np.uint8), alpha), (800, 800), 0.8)


def test_ground_shadow_sits_under_the_product():
    framed, placement = framed_square()
    shadow = make_shadow(framed.alpha, placement, ShadowParams(ShadowStyle.GROUND, 0.4))
    assert shadow is not None and shadow.shape == (800, 800)
    base_y = placement.bbox.y1
    cx = (placement.bbox.x0 + placement.bbox.x1) // 2
    assert shadow[base_y, cx] > 0.1  # dark under the base
    assert shadow[placement.bbox.y0 - 20, cx] < 0.01  # nothing above the product
    assert shadow.max() <= 0.4 + 1e-6


def test_drop_shadow_is_offset_down_right():
    framed, placement = framed_square()
    shadow = make_shadow(framed.alpha, placement, ShadowParams(ShadowStyle.DROP, 0.5))
    b = placement.bbox
    assert shadow[b.y1 + 5, b.x1 + 5] > shadow[b.y0 - 5, b.x0 - 5]


def test_no_shadow():
    framed, placement = framed_square()
    assert make_shadow(framed.alpha, placement, ShadowParams(ShadowStyle.NONE)) is None


def test_apply_shadow_darkens_background():
    bg = np.full((4, 4, 3), 255, np.uint8)
    s = np.zeros((4, 4), np.float32)
    s[0, 0] = 0.5
    out = apply_shadow(bg, s)
    assert out[0, 0, 0] == 128 and out[3, 3, 0] == 255


def test_pipeline_adds_shadow_below_product_on_white():
    opts = ProcessOptions(presets=["meesho"], shadow="ground", shadow_opacity=0.5)
    out = process_image(product_photo(), opts, ThresholdSegmenter()).primary
    px = np.asarray(out.image).astype(int)
    b = out.placement.bbox
    below = px[min(b.y1 + 3, 999), (b.x0 + b.x1) // 2]
    assert below.mean() < 250  # visible soft shadow
    assert px[5, 5].tolist() == [255, 255, 255]  # corners stay pure white

    plain = process_image(
        product_photo(), opts.model_copy(update={"shadow": ShadowStyle.NONE}), ThresholdSegmenter()
    ).primary
    assert np.asarray(plain.image)[min(b.y1 + 3, 999), (b.x0 + b.x1) // 2].tolist() == [255] * 3

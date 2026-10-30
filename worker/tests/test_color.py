from __future__ import annotations

import numpy as np

from cleanshot_worker.pipeline.color import ColorParams, auto_color
from cleanshot_worker.pipeline.options import ProcessOptions
from cleanshot_worker.pipeline.process import process_image

from .fakes import ThresholdSegmenter, product_photo


def scene(cast=(1.0, 1.0, 1.0), exposure=1.0):
    """Grey backdrop with a mid-grey product, under coloured / dim light."""
    rgb = np.full((400, 400, 3), 200.0)
    rgb[100:300, 100:300] = 110.0
    rgb[150:250, 150:250] = 160.0
    rgb *= np.array(cast) * exposure
    alpha = np.zeros((400, 400), np.float32)
    alpha[100:300, 100:300] = 1.0
    return np.clip(rgb, 0, 255).astype(np.uint8), alpha


def cast_of(rgb, region):
    """Relative spread between channels: 0 for perfectly neutral grey."""
    px = rgb[region].reshape(-1, 3).astype(float).mean(axis=0)
    return (px.max() - px.min()) / px.mean()


def test_removes_warm_cast_using_backdrop():
    rgb, alpha = scene(cast=(1.15, 1.0, 0.75))
    out, adj = auto_color(rgb, alpha, ColorParams(vibrance=0))
    product = (slice(100, 140), slice(100, 300))  # mid-tone band of the product
    assert adj.reference == "background"
    assert cast_of(out, product) < cast_of(rgb, product) * 0.6
    assert adj.wb_gains[2] > 1.0 > adj.wb_gains[0]  # boost blue, cut red


def test_brightens_underexposed_product():
    rgb, alpha = scene(exposure=0.45)
    out, adj = auto_color(rgb, alpha)
    fg = alpha > 0.5
    assert out[fg].mean() > rgb[fg].mean() * 1.4
    assert adj.white_point < 1.0 or adj.gamma < 1.0


def test_well_exposed_neutral_photo_is_barely_changed():
    rgb, alpha = scene()
    rgb[100:300, 100:300] = np.linspace(20, 240, 200, dtype=np.uint8)[None, :, None]
    out, _ = auto_color(rgb, alpha, ColorParams(vibrance=0))
    assert np.abs(out.astype(int) - rgb.astype(int)).mean() < 6


def test_coloured_backdrop_gains_are_clamped():
    rgb, alpha = scene()
    rgb[alpha < 0.5] = (40, 90, 220)  # bright blue sheet behind the product
    _, adj = auto_color(rgb, alpha, ColorParams(max_gain=1.25))
    assert max(adj.wb_gains) / min(adj.wb_gains) <= 1.25**2 + 1e-3


def test_strength_zero_is_identity():
    rgb, alpha = scene(cast=(1.2, 1.0, 0.8))
    out, adj = auto_color(rgb, alpha, ColorParams(strength=0))
    assert out is rgb and adj.reference == "off"


def test_pipeline_toggle():
    photo = product_photo(color=(200, 60, 40), background=(240, 225, 190))  # warm backdrop
    on = process_image(photo, ProcessOptions(presets=["meesho"]), ThresholdSegmenter())
    off = process_image(
        photo, ProcessOptions(presets=["meesho"], auto_color=False), ThresholdSegmenter()
    )
    assert on.color is not None and off.color is None
    assert not np.array_equal(np.asarray(on.primary.image), np.asarray(off.primary.image))

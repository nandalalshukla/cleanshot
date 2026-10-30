from __future__ import annotations

import pytest

from cleanshot_worker.pipeline.framing import Alignment
from cleanshot_worker.pipeline.options import OutputFormat, ProcessOptions
from cleanshot_worker.pipeline.presets import PRESETS, PresetId
from cleanshot_worker.pipeline.process import process_image

from .fakes import ThresholdSegmenter, product_photo


def test_amazon_preset_is_2000_white():
    spec = ProcessOptions().render_specs()[0]
    assert (spec.preset, spec.width, spec.height) == (PresetId.AMAZON, 2000, 2000)
    assert spec.background_color == "#FFFFFF"
    assert spec.fill == 0.85
    assert spec.filename_suffix == "amazon_2000x2000.jpg"


def test_instagram_portrait_is_4_by_5():
    p = PRESETS[PresetId.INSTAGRAM_PORTRAIT]
    assert (p.width, p.height, p.aspect_label) == (1080, 1350, "4:5")


def test_overrides_win_over_preset_defaults():
    opts = ProcessOptions(
        presets=["meesho", "instagram_story"],
        background_color="#abc",
        fill=0.7,
        alignment="center",
        output_format="png",
    )
    specs = opts.render_specs()
    assert all(s.background_color == "#AABBCC" for s in specs)
    assert all(s.fill == 0.7 and s.alignment is Alignment.CENTER for s in specs)
    assert specs[1].filename_suffix == "instagram_story_1080x1920.png"
    assert specs[1].output_format is OutputFormat.PNG


def test_duplicate_presets_are_collapsed():
    assert ProcessOptions(presets=["amazon", "amazon"]).presets == [PresetId.AMAZON]


def test_invalid_colour_rejected():
    with pytest.raises(ValueError):
        ProcessOptions(background_color="red")


def test_one_photo_renders_every_selected_preset():
    opts = ProcessOptions(presets=["meesho", "instagram_portrait"])
    seg = ThresholdSegmenter()
    result = process_image(product_photo(), opts, seg)
    assert [o.image.size for o in result.outputs] == [(1000, 1000), (1080, 1350)]
    assert seg.calls == 1  # segmentation is shared across presets


def test_presets_endpoint(client):
    res = client.get("/v1/presets")
    assert res.status_code == 200
    ids = [p["id"] for p in res.json()]
    assert ids[0] == "amazon" and "custom" in ids

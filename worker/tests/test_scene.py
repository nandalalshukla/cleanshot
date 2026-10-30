from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

from cleanshot_worker.pipeline.framing import Alignment
from cleanshot_worker.pipeline.options import BackgroundMode, ProcessOptions
from cleanshot_worker.pipeline.process import process_image
from cleanshot_worker.pipeline.scene import (
    SCENES,
    DiffusionSceneGenerator,
    ProceduralSceneGenerator,
    SceneId,
    SceneService,
    cover_resize,
    create_scene_service,
    scene_prompt,
    seed_for,
)

from .fakes import ThresholdSegmenter, product_photo


class CountingGenerator:
    backend = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, scene, prompt, size, seed):
        self.calls += 1
        w, h = size
        return np.full((h, w, 3), (seed % 200, 100, 150), np.uint8)


@pytest.mark.parametrize("scene", list(SceneId))
def test_procedural_backdrops_render_every_scene(scene):
    img = ProceduralSceneGenerator().generate(scene, "", (320, 400), seed=7)
    assert img.shape == (400, 320, 3) and img.dtype == np.uint8
    assert img.std() > 1  # not a flat fill: gradient / vignette present


def test_procedural_is_deterministic_per_seed():
    gen = ProceduralSceneGenerator()
    a = gen.generate(SceneId.FESTIVE, "", (200, 200), seed=1)
    b = gen.generate(SceneId.FESTIVE, "", (200, 200), seed=1)
    c = gen.generate(SceneId.FESTIVE, "", (200, 200), seed=2)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_scene_service_caches_per_prompt_seed_and_size():
    gen = CountingGenerator()
    svc = SceneService(gen)
    svc.render(SceneId.MARBLE, None, (100, 100), 1)
    svc.render(SceneId.MARBLE, None, (100, 100), 1)
    assert gen.calls == 1
    svc.render(SceneId.MARBLE, None, (100, 100), 2)
    svc.render(SceneId.MARBLE, None, (120, 100), 1)
    svc.render(SceneId.CUSTOM, "on a pink silk sheet", (100, 100), 1)
    assert gen.calls == 4


def test_prompts():
    assert scene_prompt(SceneId.WOOD, None) == SCENES[SceneId.WOOD].prompt
    custom = scene_prompt(SceneId.CUSTOM, "on a pink silk sheet")
    assert custom.startswith("on a pink silk sheet,") and "empty surface" in custom
    assert seed_for("batch-1") == seed_for("batch-1") != seed_for("batch-2")


def test_cover_resize_fills_without_distortion():
    img = np.zeros((100, 200, 3), np.uint8)
    img[:, 90:110] = 255  # vertical stripe in the middle
    out = cover_resize(img, (300, 300))
    assert out.shape == (300, 300, 3)
    assert out[150, 150].mean() > 200  # stripe stays centred


def test_diffusion_render_size_keeps_aspect_and_multiple_of_64():
    w, h = DiffusionSceneGenerator.render_size((1080, 1350))
    assert w % 64 == 0 and h % 64 == 0
    assert abs(w / h - 1080 / 1350) < 0.1
    assert 0.8 < (w * h) / 512**2 < 1.25


def test_auto_backend_falls_back_to_procedural_without_diffusers():
    pytest.importorskip("numpy")
    try:
        import diffusers  # noqa: F401

        pytest.skip("diffusers installed")
    except ImportError:
        pass
    assert create_scene_service("auto", "m", 2, "cpu").backend == "procedural"


def test_scene_mode_composites_product_on_scene_bottom_aligned():
    gen = CountingGenerator()
    opts = ProcessOptions(
        presets=["meesho", "instagram_square"], background_mode="scene", scene="marble"
    )
    spec = opts.render_specs()[0]
    assert spec.background_mode is BackgroundMode.SCENE and spec.alignment is Alignment.BOTTOM

    result = process_image(product_photo(), opts, ThresholdSegmenter(), SceneService(gen), seed=42)
    px = np.asarray(result.primary.image)
    assert tuple(px[3, 3]) == (42, 100, 150)  # corner shows the generated scene
    assert gen.calls == 2  # one per preset size
    assert result.primary.placement.bbox.y1 > 1000 * 0.85  # standing near the bottom


def test_scene_seed_option_overrides_batch_seed():
    gen = CountingGenerator()
    opts = ProcessOptions(presets=["meesho"], background_mode="scene", scene_seed=7)
    result = process_image(product_photo(), opts, ThresholdSegmenter(), SceneService(gen), seed=99)
    assert tuple(np.asarray(result.primary.image)[3, 3]) == (7, 100, 150)


def test_scenes_catalog_endpoint(client):
    res = client.get("/v1/scenes")
    assert res.status_code == 200
    body = res.json()
    assert body["backend"] in ("procedural", "diffusion")
    assert {s["id"] for s in body["scenes"]} == {s.value for s in SceneId}


def test_scene_preview_endpoint(client):
    res = client.get("/v1/scenes/preview?scene=wood&width=256&height=320&seed=3")
    assert res.status_code == 200 and res.headers["content-type"] == "image/jpeg"
    assert Image.open(io.BytesIO(res.content)).size == (256, 320)


def test_batch_with_scene_background(client):
    from .test_batches import HEADERS, create, upload, wait_for

    batch = create(client, presets=["meesho"], background_mode="scene", scene="festive")
    upload(client, batch["id"], product_photo())
    client.post(f"/v1/batches/{batch['id']}/start", headers=HEADERS)
    done = wait_for(client, batch["id"])
    assert done["images"][0]["status"] == "done"
    assert done["options"]["background_mode"] == "scene"


def test_diffusion_generator_drives_pipeline_correctly(monkeypatch):
    """Exercise DiffusionSceneGenerator against stub torch/diffusers modules (no weights)."""
    import sys
    import types

    calls = {}

    class FakePipe:
        def to(self, device):
            calls["device"] = device

        def set_progress_bar_config(self, **_):
            pass

        def __call__(self, **kw):
            calls.update(kw)
            img = Image.new("RGB", (kw["width"], kw["height"]), (10, 120, 200))
            return types.SimpleNamespace(images=[img])

    class AutoPipe:
        @staticmethod
        def from_pretrained(model, torch_dtype):
            calls["model"], calls["dtype"] = model, torch_dtype
            return FakePipe()

    class Gen:
        def __init__(self, device):
            pass

        def manual_seed(self, seed):
            calls["seed"] = seed
            return self

    fake_torch = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
        backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=lambda: False)),
        float16="fp16",
        float32="fp32",
        Generator=Gen,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(
        sys.modules, "diffusers", types.SimpleNamespace(AutoPipelineForText2Image=AutoPipe)
    )

    gen = DiffusionSceneGenerator(model="stabilityai/sd-turbo", steps=2)
    out = gen.generate(SceneId.WOOD, "a prompt", (1080, 1350), seed=5)

    assert out.shape == (1350, 1080, 3)
    assert calls["model"] == "stabilityai/sd-turbo" and calls["device"] == "cpu"
    assert calls["dtype"] == "fp32"  # fp16 only on CUDA
    assert calls["num_inference_steps"] == 2 and calls["guidance_scale"] == 0.0
    assert calls["seed"] == 5 and calls["prompt"] == "a prompt"
    assert (calls["width"], calls["height"]) == DiffusionSceneGenerator.render_size((1080, 1350))
    assert abs(int(out[675, 540, 2]) - 200) <= 2  # upscaled generated colour

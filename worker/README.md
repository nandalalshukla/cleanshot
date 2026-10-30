# CleanShot worker

FastAPI service that does all image processing for the CleanShot app.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cleanshot-worker                 # or: uvicorn cleanshot_worker.main:create_app --factory --reload
```

Open http://localhost:8000/docs for interactive API docs.

Model weights are downloaded by rembg on first use into `~/.u2net` (override with `U2NET_HOME`).

## Segmentation models

| Model | Size | Use for |
| --- | --- | --- |
| `u2netp` (default) | ~4.7 MB | Very fast; solid, boxed or hard-edged products |
| `isnet-general-use` | ~170 MB | Cleaner edges on fabric, hair, soft goods |
| `birefnet-general-lite` | ~210 MB | Finest detail: jewellery, fur, see-through parts |

Compare them on your own photos:

```bash
python scripts/compare_models.py ~/photos --out compare/ \
  --models u2netp isnet-general-use birefnet-general-lite
```

On a laptop CPU, u2netp takes ~0.4 s per photo and isnet ~1.7 s. The script writes side-by-side
strips plus `report.csv` with timing, coverage and a soft-edge ratio per model.

## Generated scene backgrounds

Besides white/brand colours, products can be placed in a generated scene (marble, wooden
table, festive Diwali, beach… or a custom prompt). Every photo in a batch shares one scene.

```bash
pip install -e ".[diffusion]"     # torch + diffusers; enables AI scenes
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `CLEANSHOT_SCENE_BACKEND` | `auto` | `diffusion` when torch/diffusers are installed, else `procedural` |
| `CLEANSHOT_SCENE_MODEL` | `stabilityai/sd-turbo` | Any diffusers text-to-image model id |
| `CLEANSHOT_SCENE_STEPS` | `2` | Denoising steps (turbo models need 1–4) |
| `CLEANSHOT_SCENE_DEVICE` | `auto` | `cuda`, `mps` or `cpu` |

The model is loaded on first use and its weights are downloaded from Hugging Face (set
`HF_HOME` to choose the cache folder). Without the extra, the worker falls back to built-in
studio backdrops so the feature never hard-fails; `GET /v1/scenes` reports which backend is
active and the app tells the seller.

## Tests and linting

```bash
pytest                                         # fast suite, uses a fake segmenter
CLEANSHOT_RUN_MODEL_TESTS=1 pytest -k real     # also runs the real u2netp model
ruff check . && ruff format --check .
```

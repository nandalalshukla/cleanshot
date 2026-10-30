# CleanShot

**Marketplace-ready product photos from a phone snap.**

Home sellers on Meesho, Amazon, Flipkart and Instagram need white-background, centred product
photos, but photographers and manual editing cost time and money. CleanShot takes a batch of
up to 50 phone photos and returns a ZIP of listing-ready images.

```
Upload photos → queue → segmentation → alpha mask → refine edges → auto colour
  → auto-crop + centre + pad to marketplace size → white / brand colour / AI scene
  → soft shadow → quality check → download ZIP
```

| Part | Stack | Folder |
| --- | --- | --- |
| Mobile app | React Native · Expo SDK 58 · Expo Router · TanStack Query | [`app/`](app) |
| Image worker | Python 3.11+ · FastAPI · rembg (u2netp / isnet / BiRefNet-lite) · OpenCV · diffusers | [`worker/`](worker) |

## Features

| Feature | Where |
| --- | --- |
| Background removal with **u2netp** (≈4.7 MB, fast) or **isnet / BiRefNet-lite** (fine edges) | `worker/cleanshot_worker/pipeline/segmentation.py` |
| Edge refinement: speck removal, pin-hole filling, feathering, halo decontamination | `pipeline/refine.py` |
| Auto-crop, ~85% fill, centre or floor alignment | `pipeline/framing.py` |
| Marketplace presets: Amazon 2000², Flipkart 1500², Meesho 1000², Instagram 4:5 / 1:1 / story, web store, custom | `pipeline/presets.py` |
| Soft ground or drop shadow from the blurred, squashed mask | `pipeline/shadow.py` |
| **Auto colour correction**: backdrop-referenced white balance, levels, exposure, vibrance | `pipeline/color.py` |
| **Generated scenes** with a small diffusion model (sd-turbo), procedural fallback | `pipeline/scene.py` |
| **Quality check**: tiny product, holes, cut off, blur, exposure, low resolution… | `pipeline/quality.py` |
| Batch queue with crash recovery, retries, retakes, ZIP export with `report.csv` | `worker/cleanshot_worker/jobs/` |
| App: bulk pick/camera, options, upload + processing progress, retake flow, share/download | `app/src/` |

## Quick start

```bash
make setup          # worker venv + app node_modules
make worker         # http://0.0.0.0:8000  (API docs at /docs)
make app            # Expo dev server — open on your phone with Expo Go
```

In the app open **Settings** and enter the worker URL using your computer's LAN IP, e.g.
`http://192.168.1.20:8000`. Or run the worker in Docker:

```bash
docker compose up -d --build
```

## Configuration

The worker reads `CLEANSHOT_*` environment variables (see [`worker/.env.example`](worker/.env.example)):
API key, upload limits, concurrency, retention, model warm-up and the scene backend. AI scenes
need the optional extra: `pip install -e "worker[diffusion]"` or build the image with
`--build-arg EXTRAS="[diffusion]"`.

## Development

```bash
make lint           # ruff + mypy, tsc + eslint + prettier
make test           # pytest (90+ tests) + jest
```

CI (`.github/workflows/ci.yml`) runs the same checks and builds the worker image.

## Docs

* [Architecture](docs/ARCHITECTURE.md) — pipeline, job model, API
* [Worker README](worker/README.md) — models, scenes, running and benchmarking
* [App README](app/README.md) — structure, scripts, builds

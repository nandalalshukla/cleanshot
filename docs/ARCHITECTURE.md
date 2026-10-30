# Architecture

```
┌──────────────┐  HTTP/JSON + multipart  ┌──────────────────────────────┐
│  Expo app    │ ──────────────────────▶ │  FastAPI worker              │
│  (app/)      │ ◀────────────────────── │  (worker/)                   │
└──────────────┘    poll progress, ZIP   └──────────────────────────────┘
```

* **App** — picks photos, chooses export options, uploads, shows progress and results,
  downloads the ZIP and hands it to the OS share sheet.
* **Worker** — owns all image processing. Stateless HTTP layer on top of a small job store and
  a thread pool that runs the processing pipeline.

## Image pipeline (`worker/cleanshot_worker/pipeline/`)

```
image_io.load_image      EXIF rotate, flatten alpha, cap to 4096 px, HEIC via pillow-heif
segmentation             rembg session per model, shared across threads  → raw alpha
color.auto_color         WB from backdrop pixels, levels, gamma, vibrance (optional)
refine                   remove specks, fill pin-holes, choke + feather, decontaminate halo
── per preset ───────────────────────────────────────────────────────────────────────────
framing.frame_product    crop to mask bbox, scale to fill × canvas, centre / bottom-align
background               solid colour, or scene.SceneService (diffusion | procedural)
shadow                   ground (squashed + blurred mask) or drop shadow, darkens background
compose.over             alpha-composite product over background
─────────────────────────────────────────────────────────────────────────────────────────
quality.assess           grades the photo as captured from the raw mask → verdict + flags
```

Everything works on numpy arrays (`Layer` = RGB uint8 + float alpha), so stages are small
pure functions that are easy to test in isolation. `process.process_image` wires them up and
returns per-stage timings.

### Model choices

| Job | Model | Notes |
| --- | --- | --- |
| Segmentation (fast) | `u2netp` (~4.7 MB) | ~0.4 s/photo on CPU; default |
| Segmentation (quality) | `isnet-general-use`, `birefnet-general-lite` | better hair/fabric/jewellery edges |
| Scene generation | `stabilityai/sd-turbo` | 2 steps, guidance 0, ~512 px then upscaled + blurred |

`scripts/compare_models.py` benchmarks segmentation models on your own photos.

## Batch flow

```
app                                   worker
───                                   ──────
POST /v1/batches {options}      ──▶   batch (draft)
POST /v1/batches/:id/images ×N  ──▶   validate, store original + thumbnail
POST /v1/batches/:id/start      ──▶   images → queued, submitted to the thread pool
GET  /v1/batches/:id  (poll)    ◀──   progress, per-image status, preview URLs
GET  /v1/batches/:id/download   ◀──   ZIP: <preset>_<WxH>/<photo>.jpg + report.csv
```

* **Job store** — SQLite (WAL) at `data/cleanshot.sqlite3`. Images that were queued or
  in-flight when the worker stopped are re-queued on start-up.
* **Queue** — a thread pool (`CLEANSHOT_WORKER_CONCURRENCY`). Processors atomically *claim*
  an image before working on it, so duplicate submissions are harmless. The processor is a
  plain callable, so RQ/Celery can replace the pool for multi-machine setups.
* **Files** — `data/batches/<id>/{input,thumbs,output}`; the ZIP is rebuilt only when stale.
* **Janitor** — deletes batches older than `CLEANSHOT_BATCH_TTL_HOURS` (default 72).
* **Client scoping** — the app sends a random per-install `X-Client-Id` so phones sharing a
  worker only see their own batches. Authentication is the optional `X-API-Key`.

Retakes use `PUT /v1/batches/:id/images/:imageId`, which swaps the file and re-processes it.

## API reference

Interactive OpenAPI docs are served at `/docs`. All `/v1` routes require `X-API-Key` when
`CLEANSHOT_API_KEY` is set; batch routes are scoped by the optional `X-Client-Id` header.

| Method & path | Purpose |
| --- | --- |
| `GET /health` | Liveness (always public) |
| `GET /v1/presets` · `GET /v1/models` · `GET /v1/scenes` | Catalogs for the app's option pickers |
| `GET /v1/scenes/preview?scene=&prompt=&seed=` | Background-only preview image |
| `POST /v1/remove-background` · `POST /v1/process` | Single photo, synchronous |
| `POST /v1/batches` · `GET /v1/batches` · `GET/DELETE /v1/batches/:id` | Batch CRUD |
| `POST /v1/batches/:id/images` | Upload one or more photos (`position` keeps order) |
| `POST /v1/batches/:id/{start,cancel,retry}` | Lifecycle |
| `PUT/DELETE /v1/batches/:id/images/:imageId` · `POST …/retry` | Retake, remove, retry one photo |
| `GET /v1/batches/:id/images/:imageId/{original,preview,cutout,outputs/:preset}` | Files |
| `GET /v1/batches/:id/download` | ZIP of every finished output + `report.csv` |

Wire types are mirrored in `app/src/api/types.ts`; keep both sides in sync when changing
`worker/cleanshot_worker/api/schemas.py` or `pipeline/options.py`.

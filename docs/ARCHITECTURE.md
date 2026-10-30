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

Details of the pipeline, job model and API are filled in as each phase lands.

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

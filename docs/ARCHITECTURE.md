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

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

## Tests and linting

```bash
pytest                                         # fast suite, uses a fake segmenter
CLEANSHOT_RUN_MODEL_TESTS=1 pytest -k real     # also runs the real u2netp model
ruff check . && ruff format --check .
```

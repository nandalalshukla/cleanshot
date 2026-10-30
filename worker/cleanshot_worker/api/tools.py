"""Single-image synchronous endpoints, for previews and debugging. Batches use /v1/batches."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from ..config import Settings
from ..pipeline import image_io
from ..pipeline.options import ProcessOptions
from ..pipeline.presets import PRESETS
from ..pipeline.process import NoProductFoundError, process_image
from ..pipeline.registry import SegmenterRegistry
from ..pipeline.segmentation import MODEL_CATALOG, SegmentationModel
from .deps import get_registry, get_settings, read_upload, require_api_key
from .schemas import ModelOut, PresetOut

router = APIRouter(prefix="/v1", tags=["tools"], dependencies=[Depends(require_api_key)])


@router.get("/models", response_model=list[ModelOut])
def list_models() -> list[ModelOut]:
    return [ModelOut(**vars(info)) for info in MODEL_CATALOG.values()]


@router.get("/presets", response_model=list[PresetOut])
def list_presets() -> list[PresetOut]:
    return [PresetOut.from_preset(p) for p in PRESETS.values()]


@router.post(
    "/remove-background",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
async def remove_background(
    file: UploadFile = File(...),
    model: SegmentationModel = Form(SegmentationModel.U2NETP),
    settings: Settings = Depends(get_settings),
    registry: SegmenterRegistry = Depends(get_registry),
) -> Response:
    data = await read_upload(file, settings)
    try:
        img = image_io.load_image(data, settings.max_input_side)
    except image_io.InvalidImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    def _run() -> bytes:
        alpha = registry.get(model).segment(img)
        return image_io.encode(image_io.cutout_rgba(image_io.to_array(img), alpha))

    png = await run_in_threadpool(_run)
    return Response(png, media_type="image/png")


MEDIA_TYPES = {"jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def parse_options(raw: str | None) -> ProcessOptions:
    try:
        return ProcessOptions.model_validate_json(raw) if raw else ProcessOptions()
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, exc.errors(include_url=False)
        ) from exc


@router.post(
    "/process",
    response_class=Response,
    responses={200: {"content": {t: {} for t in MEDIA_TYPES.values()}}},
)
async def process_single(
    request: Request,
    file: UploadFile = File(...),
    options: str | None = Form(None, description="ProcessOptions as JSON"),
    settings: Settings = Depends(get_settings),
    registry: SegmenterRegistry = Depends(get_registry),
) -> Response:
    """Run the full pipeline on one photo and return the image for the first preset."""
    opts = parse_options(options)
    data = await read_upload(file, settings)
    try:
        img = image_io.load_image(data, settings.max_input_side)
    except image_io.InvalidImageError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc

    def _run() -> bytes:
        return process_image(
            img, opts, registry.get(opts.model), scenes=request.app.state.scenes
        ).primary.encode()

    try:
        out = await run_in_threadpool(_run)
    except NoProductFoundError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return Response(out, media_type=MEDIA_TYPES[opts.output_format.value])

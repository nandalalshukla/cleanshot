"""Single-image synchronous endpoints, for previews and debugging. Batches use /v1/batches."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool

from ..config import Settings
from ..pipeline import image_io
from ..pipeline.registry import SegmenterRegistry
from ..pipeline.segmentation import MODEL_CATALOG, SegmentationModel
from .deps import get_registry, get_settings, read_upload, require_api_key
from .schemas import ModelOut

router = APIRouter(prefix="/v1", tags=["tools"], dependencies=[Depends(require_api_key)])


@router.get("/models", response_model=list[ModelOut])
def list_models() -> list[ModelOut]:
    return [ModelOut(**vars(info)) for info in MODEL_CATALOG.values()]


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

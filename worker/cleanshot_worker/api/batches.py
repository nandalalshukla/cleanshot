"""Batch endpoints: create → upload photos → start → poll → download ZIP."""

from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from ..config import Settings
from ..jobs.archive import ensure_zip
from ..jobs.models import ImageStatus
from ..jobs.service import BatchService, ConflictError, LimitError
from ..jobs.store import NotFoundError
from ..pipeline.image_io import InvalidImageError
from .deps import get_settings, read_upload, require_api_key
from .schemas import BatchCreate, BatchOut, BatchSummary, ImageOut

router = APIRouter(prefix="/v1/batches", tags=["batches"], dependencies=[Depends(require_api_key)])

IMAGE_CACHE = {"Cache-Control": "private, max-age=300"}


def get_service(request: Request) -> BatchService:
    return request.app.state.batches


def client_id(x_client_id: str | None = Header(default=None, max_length=64)) -> str | None:
    return x_client_id or None


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    if isinstance(exc, ConflictError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, LimitError):
        return HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc))
    if isinstance(exc, InvalidImageError):
        return HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc))
    raise exc


def _file(path: Path, media_type: str) -> FileResponse:
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not available")
    return FileResponse(path, media_type=media_type, headers=IMAGE_CACHE)


# ---- batches ---------------------------------------------------------------------------------


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    body: BatchCreate,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> BatchOut:
    return BatchOut.from_record(svc.create(body.name, body.options, cid))


@router.get("", response_model=list[BatchSummary])
def list_batches(
    limit: int = 50,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> list[BatchSummary]:
    return [BatchSummary.from_record(b) for b in svc.store.list_batches(cid, min(limit, 200))]


@router.get("/{batch_id}", response_model=BatchOut)
def get_batch(
    batch_id: str, svc: BatchService = Depends(get_service), cid: str | None = Depends(client_id)
) -> BatchOut:
    try:
        return BatchOut.from_record(svc.get(batch_id, cid))
    except NotFoundError as exc:
        raise _translate(exc) from exc


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_batch(
    batch_id: str, svc: BatchService = Depends(get_service), cid: str | None = Depends(client_id)
) -> Response:
    try:
        svc.get(batch_id, cid)
        svc.delete(batch_id)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{batch_id}/start", response_model=BatchOut)
def start_batch(
    batch_id: str, svc: BatchService = Depends(get_service), cid: str | None = Depends(client_id)
) -> BatchOut:
    try:
        svc.get(batch_id, cid)
        return BatchOut.from_record(svc.start(batch_id))
    except (NotFoundError, ConflictError) as exc:
        raise _translate(exc) from exc


@router.post("/{batch_id}/cancel", response_model=BatchOut)
def cancel_batch(
    batch_id: str, svc: BatchService = Depends(get_service), cid: str | None = Depends(client_id)
) -> BatchOut:
    try:
        svc.get(batch_id, cid)
        return BatchOut.from_record(svc.cancel(batch_id))
    except NotFoundError as exc:
        raise _translate(exc) from exc


@router.post("/{batch_id}/retry", response_model=BatchOut)
def retry_failed(
    batch_id: str, svc: BatchService = Depends(get_service), cid: str | None = Depends(client_id)
) -> BatchOut:
    try:
        svc.get(batch_id, cid)
        return BatchOut.from_record(svc.retry(batch_id))
    except (NotFoundError, ConflictError) as exc:
        raise _translate(exc) from exc


@router.get(
    "/{batch_id}/download",
    response_class=FileResponse,
    responses={200: {"content": {"application/zip": {}}}},
)
async def download_zip(
    batch_id: str, svc: BatchService = Depends(get_service), cid: str | None = Depends(client_id)
) -> FileResponse:
    try:
        batch = svc.get(batch_id, cid)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    if not any(i.status is ImageStatus.DONE for i in batch.images):
        raise HTTPException(status.HTTP_409_CONFLICT, "No finished photos to download yet")
    path = await run_in_threadpool(ensure_zip, batch, svc.files(batch_id))
    return FileResponse(path, media_type="application/zip", filename=path.name)


# ---- images ----------------------------------------------------------------------------------


@router.post("/{batch_id}/images", response_model=list[ImageOut], status_code=201)
async def upload_images(
    batch_id: str,
    files: list[UploadFile] = File(..., description="One or more photos"),
    position: int | None = Form(
        None, ge=0, le=10_000, description="Order of the first file when uploading in parallel"
    ),
    svc: BatchService = Depends(get_service),
    settings: Settings = Depends(get_settings),
    cid: str | None = Depends(client_id),
) -> list[ImageOut]:
    out = []
    try:
        svc.get(batch_id, cid)
        for offset, f in enumerate(files):
            data = await read_upload(f, settings)
            pos = None if position is None else position + offset
            record = await run_in_threadpool(svc.add_image, batch_id, f.filename or "", data, pos)
            out.append(ImageOut.from_record(record))
    except (NotFoundError, ConflictError, LimitError, InvalidImageError) as exc:
        raise _translate(exc) from exc
    return out


@router.put("/{batch_id}/images/{image_id}", response_model=ImageOut)
async def replace_image(
    batch_id: str,
    image_id: str,
    file: UploadFile = File(..., description="Retaken photo"),
    svc: BatchService = Depends(get_service),
    settings: Settings = Depends(get_settings),
    cid: str | None = Depends(client_id),
) -> ImageOut:
    try:
        svc.get_image(batch_id, image_id, cid)
        data = await read_upload(file, settings)
        record = await run_in_threadpool(
            svc.replace_image, batch_id, image_id, file.filename or "", data
        )
    except (NotFoundError, ConflictError, InvalidImageError) as exc:
        raise _translate(exc) from exc
    return ImageOut.from_record(record)


@router.delete("/{batch_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_image(
    batch_id: str,
    image_id: str,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> Response:
    try:
        svc.get_image(batch_id, image_id, cid)
        svc.delete_image(batch_id, image_id)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{batch_id}/images/{image_id}/retry", response_model=ImageOut)
def retry_image(
    batch_id: str,
    image_id: str,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> ImageOut:
    try:
        svc.get_image(batch_id, image_id, cid)
        svc.retry(batch_id, image_id)
        return ImageOut.from_record(svc.store.get_image(image_id))
    except (NotFoundError, ConflictError) as exc:
        raise _translate(exc) from exc


@router.get("/{batch_id}/images/{image_id}/original", response_class=FileResponse)
def get_original(
    batch_id: str,
    image_id: str,
    full: bool = False,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> FileResponse:
    """Thumbnail of the uploaded photo (``?full=true`` for the untouched upload)."""
    try:
        img = svc.get_image(batch_id, image_id, cid)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    files = svc.files(batch_id)
    if full:
        return FileResponse(files.input(img.stored_name), headers=IMAGE_CACHE)
    return _file(files.thumb(image_id), "image/jpeg")


@router.get("/{batch_id}/images/{image_id}/preview", response_class=FileResponse)
def get_preview(
    batch_id: str,
    image_id: str,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> FileResponse:
    try:
        svc.get_image(batch_id, image_id, cid)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    return _file(svc.files(batch_id).preview(image_id), "image/jpeg")


@router.get("/{batch_id}/images/{image_id}/cutout", response_class=FileResponse)
def get_cutout(
    batch_id: str,
    image_id: str,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> FileResponse:
    try:
        svc.get_image(batch_id, image_id, cid)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    return _file(svc.files(batch_id).cutout(image_id), "image/png")


@router.get("/{batch_id}/images/{image_id}/outputs/{preset}", response_class=FileResponse)
def get_output(
    batch_id: str,
    image_id: str,
    preset: str,
    svc: BatchService = Depends(get_service),
    cid: str | None = Depends(client_id),
) -> FileResponse:
    try:
        img = svc.get_image(batch_id, image_id, cid)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    out = next((o for o in img.outputs if o.preset == preset), None)
    if out is None or img.status is not ImageStatus.DONE:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Output not available")
    path = svc.files(batch_id).output(image_id, out.filename)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Output not available")
    return FileResponse(path, headers=IMAGE_CACHE, filename=out.filename)

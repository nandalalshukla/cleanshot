"""Scene catalog and previews for generated backgrounds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..pipeline import image_io
from ..pipeline.scene import SCENES, SceneId, SceneService, SceneUnavailableError
from .deps import require_api_key

router = APIRouter(prefix="/v1/scenes", tags=["scenes"], dependencies=[Depends(require_api_key)])


class SceneOut(BaseModel):
    id: SceneId
    label: str
    prompt: str


class SceneCatalog(BaseModel):
    backend: str = Field(
        description="'diffusion' (AI-generated) or 'procedural' (studio backdrops)"
    )
    model: str | None
    scenes: list[SceneOut]


def get_scenes(request: Request) -> SceneService:
    return request.app.state.scenes


@router.get("", response_model=SceneCatalog)
def list_scenes(scenes: SceneService = Depends(get_scenes)) -> SceneCatalog:
    return SceneCatalog(
        backend=scenes.backend,
        model=scenes.generator.model,
        scenes=[SceneOut(id=s.id, label=s.label, prompt=s.prompt) for s in SCENES.values()],
    )


@router.get("/preview", response_class=Response, responses={200: {"content": {"image/jpeg": {}}}})
async def preview_scene(
    scene: SceneId = SceneId.STUDIO,
    prompt: str | None = Query(None, max_length=200),
    seed: int = Query(0, ge=0, le=2**31 - 1),
    width: int = Query(512, ge=128, le=1024),
    height: int = Query(512, ge=128, le=1024),
    scenes: SceneService = Depends(get_scenes),
) -> Response:
    """Render just the background so sellers can pick a scene before running a batch.

    A GET (not POST) so apps can load it straight into an image view and cache it.
    """
    try:
        img = await run_in_threadpool(scenes.render, scene, prompt, (width, height), seed)
    except SceneUnavailableError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return Response(
        image_io.encode(image_io.to_image(img), "JPEG", 85),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=3600"},
    )

"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import batches, health, tools
from .api import scenes as scenes_api
from .config import Settings, get_settings
from .jobs.janitor import Janitor
from .jobs.processor import ImageProcessor
from .jobs.queue import JobQueue
from .jobs.service import BatchService
from .jobs.store import JobStore
from .logging_config import configure_logging
from .pipeline.registry import SegmenterRegistry
from .pipeline.scene import SceneService, create_scene_service

log = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    segmenters: SegmenterRegistry | None = None,
    scenes: SceneService | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    settings.batches_dir.mkdir(parents=True, exist_ok=True)

    registry = segmenters or SegmenterRegistry()
    scene_service = scenes or create_scene_service(
        settings.scene_backend, settings.scene_model, settings.scene_steps, settings.scene_device
    )
    store = JobStore(settings.db_path)
    processor = ImageProcessor(
        store, registry, settings.batches_dir, settings.max_input_side, scene_service
    )
    queue = JobQueue(processor, settings.worker_concurrency)
    janitor = Janitor(store, settings.batches_dir, settings.batch_ttl_hours)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        queue.start()
        pending = store.unfinished_image_ids()
        if pending:
            log.info("Re-queuing %d unfinished image(s) from a previous run", len(pending))
            queue.submit_many(pending)
        janitor.start()
        try:
            yield
        finally:
            janitor.stop()
            queue.stop(wait=True)

    app = FastAPI(title="CleanShot Worker", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.segmenters = registry
    app.state.scenes = scene_service
    app.state.batches = BatchService(
        store=store,
        queue=queue,
        batches_dir=settings.batches_dir,
        max_images_per_batch=settings.max_images_per_batch,
        max_input_side=settings.max_input_side,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(tools.router)
    app.include_router(batches.router)
    app.include_router(scenes_api.router)
    return app

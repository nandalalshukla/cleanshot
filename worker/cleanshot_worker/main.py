"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import health, tools
from .config import Settings, get_settings
from .logging_config import configure_logging
from .pipeline.registry import SegmenterRegistry


def create_app(
    settings: Settings | None = None,
    segmenters: SegmenterRegistry | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="CleanShot Worker", version=__version__)
    app.state.settings = settings
    app.state.segmenters = segmenters or SegmenterRegistry()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(tools.router)
    return app

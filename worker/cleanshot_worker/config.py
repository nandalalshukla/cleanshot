"""Runtime configuration, loaded from environment variables (prefix ``CLEANSHOT_``)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLEANSHOT_", env_file=".env", extra="ignore")

    # HTTP
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    # Optional shared secret; when set, clients must send ``X-API-Key``.
    api_key: str | None = None

    # Storage
    data_dir: Path = Path("./data")

    # Limits
    max_upload_mb: int = 25
    max_images_per_batch: int = 50
    max_input_side: int = 4096
    """Inputs larger than this (longest side, px) are downscaled before processing."""

    # Processing
    worker_concurrency: int = 2
    default_model: str = "u2netp"
    batch_ttl_hours: int = 72
    """Finished batches older than this are removed by the janitor."""

    # Generated scene backgrounds
    scene_backend: Literal["auto", "diffusion", "procedural"] = "auto"
    """auto = diffusion when torch/diffusers are installed, else procedural backdrops."""
    scene_model: str = "stabilityai/sd-turbo"
    scene_steps: int = Field(2, ge=1, le=50)
    scene_device: str = "auto"

    log_level: str = "INFO"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "cleanshot.sqlite3"

    @property
    def batches_dir(self) -> Path:
        return self.data_dir / "batches"


@lru_cache
def get_settings() -> Settings:
    return Settings()

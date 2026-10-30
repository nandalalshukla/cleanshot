from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cleanshot_worker.config import Settings
from cleanshot_worker.main import create_app
from cleanshot_worker.pipeline.registry import SegmenterRegistry

from .fakes import ThresholdSegmenter


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", worker_concurrency=1)


@pytest.fixture
def registry() -> SegmenterRegistry:
    return SegmenterRegistry(ThresholdSegmenter)


@pytest.fixture
def client(settings: Settings, registry: SegmenterRegistry) -> Iterator[TestClient]:
    with TestClient(create_app(settings, registry)) as c:
        yield c

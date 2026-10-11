"""App fixtures use a temporary SQLite file and storage directory."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.db.migrate import upgrade_to_head
from backend.app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'beai.sqlite'}",
        storage_dir=tmp_path / "structures",
        max_upload_bytes=50 * 1024 * 1024,
        max_atom_count=200_000,
        cors_origins="http://127.0.0.1:8732",
        ca_break_threshold_angstrom=4.5,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    upgrade_to_head(settings.resolved_database_url())
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client

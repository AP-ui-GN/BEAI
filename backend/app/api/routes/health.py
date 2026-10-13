"""Liveness and capability report. Optional tools are reported, never required."""

from fastapi import APIRouter, Request

from backend.app.core.capabilities import openmm_platform_names, probe_all
from backend.app.core.config import Settings
from backend.app.db.health import alembic_head, database_status, storage_status
from backend.app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    database = database_status(request.app.state.engine, alembic_head())
    storage = storage_status(settings.resolved_storage_dir())
    ready = database["connected"] and database["reason"] is None and storage["writable"]
    return HealthResponse(
        status="ok" if ready else "degraded",
        version=settings.app_version,
        database=database,
        storage=storage,
        capabilities=probe_all(),
        openmm_platforms=openmm_platform_names(),
    )

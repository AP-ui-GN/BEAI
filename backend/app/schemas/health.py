"""Response model for ``GET /api/health``."""

from typing import Literal

from pydantic import BaseModel


class CapabilityStatus(BaseModel):
    available: bool
    version: str | None
    reason: str | None


class DatabaseStatus(BaseModel):
    connected: bool
    revision: str | None
    head: str | None
    reason: str | None


class StorageStatus(BaseModel):
    writable: bool
    reason: str | None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: DatabaseStatus
    storage: StorageStatus
    capabilities: dict[str, CapabilityStatus]

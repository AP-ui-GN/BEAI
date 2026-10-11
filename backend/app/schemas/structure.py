"""Structure upload and fetch models. Stored paths are not part of the API."""

from typing import Any

from pydantic import BaseModel


class StructureResponse(BaseModel):
    id: str
    display_filename: str
    format: str
    size_bytes: int
    sha256: str
    created_at: str
    metadata: dict[str, Any]


class StructureListResponse(BaseModel):
    structures: list[StructureResponse]

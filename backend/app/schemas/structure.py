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


class ResidueRow(BaseModel):
    chain_id: str
    resname: str
    resseq: int
    icode: str
    kind: str
    phi_degrees: float | None
    psi_degrees: float | None
    ramachandran_region: str | None
    secondary_structure: str | None
    sasa_angstrom2: float | None


class ResidueListResponse(BaseModel):
    chain_id: str | None
    residues: list[ResidueRow]

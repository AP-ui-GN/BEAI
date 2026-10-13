"""Sequence request and response models."""

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.analysis import AnalysisDetail


class SequenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


class SequenceImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accession: str


class SequenceAlignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_id: str
    right_id: str


class SequenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    header: str
    sequence: str
    length: int
    sha256: str
    created_at: str
    validation_messages: list[str]
    source: dict | None
    analysis: AnalysisDetail


class SequenceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequences: list[SequenceResponse]

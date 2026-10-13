"""AnalysisResult envelope and the analysis HTTP models."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InputRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    filename: str | None = None
    source_id: str | None = None
    sha256: str | None = None
    validation_status: str
    validation_messages: list[str] = Field(default_factory=list)


class MethodRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    software: str
    version: str | None
    parameters: dict[str, Any]


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: Any
    unit: str | None
    origin: Literal[
        "experimental_record",
        "database_reported",
        "calculated",
        "ml_prediction",
        "user_supplied",
    ]
    method: str
    uncertainty: float | None = None
    source: str | None = None


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    identifier: str | None = None
    url: str | None = None
    retrieved_at: str | None = None
    license: str | None = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str
    category: Literal[
        "established",
        "observational",
        "computational_prediction",
        "hypothesis",
        "unclassified",
    ]
    sources: list[EvidenceSource]


class SkippedStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    reason: str


class ErrorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class Reproducibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    software_versions: dict[str, str]
    random_seed: int | None = None
    config_hash: str
    platform: str


class AnalysisResult(BaseModel):
    """Shared result envelope. Absent measurements are null, not zero."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: str
    kind: str
    created_at: str
    status: Literal["pending", "running", "succeeded", "partial", "failed", "cancelled"]
    inputs: list[InputRecord]
    methods: list[MethodRecord]
    measurements: list[Measurement]
    evidence: list[Evidence]
    limitations: list[str]
    warnings: list[str]
    skipped_stages: list[SkippedStage]
    errors: list[ErrorItem]
    reproducibility: Reproducibility
    details: dict[str, Any] = Field(default_factory=dict)


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["structure_overview"]


class AnalysisErrorBody(BaseModel):
    code: str
    message: str


class AnalysisSummary(BaseModel):
    id: str
    kind: str
    status: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    structure_id: str | None
    structure_filename: str | None
    sequence_id: str | None = None
    compound_id: str | None = None
    error: AnalysisErrorBody | None


class AnalysisDetail(AnalysisSummary):
    result: AnalysisResult | None


class AnalysisListResponse(BaseModel):
    analyses: list[AnalysisSummary]

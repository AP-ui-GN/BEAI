"""HTTP models for the model registry. Views are built from stored rows and live hardware."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DependencySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["python", "executable"]
    name: str = Field(min_length=1, max_length=200)


class HardwareNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_ram_bytes: int = Field(gt=0)
    device: Literal["cpu", "cuda", "mps"]


class ModelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=64)
    task: str = Field(min_length=1, max_length=200)
    source_url: str = Field(min_length=8)
    licence: str = Field(min_length=1)
    dependencies: list[DependencySpec]
    hardware: HardwareNeed
    input_format: str = Field(min_length=1)
    output_format: str = Field(min_length=1)
    benchmark: dict[str, Any] | None = None
    known_limitations: str = Field(min_length=1)
    checksum_sha256: str | None = None
    weights_relative: str | None = None
    loader_key: Literal["registry_only", "embedding_stub", "esm2_8m"] = "registry_only"
    token_limit: int | None = Field(default=None, gt=0)

    @field_validator("source_url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        if not value.startswith(("https://", "http://")):
            raise ValueError("source_url must start with http:// or https://")
        return value


class DependencyStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    name: str
    available: bool
    version: str | None
    reason: str | None


class AcceleratorStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool
    version: str | None
    reason: str | None


class HardwareReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ram_total_bytes: int
    ram_available_bytes: int
    cuda: AcceleratorStatus
    mps: AcceleratorStatus


class CompatibilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    compatible: bool
    reasons: list[str]


class TrainingJobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    progress: float | None
    created_at: str


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    version: str
    task: str
    source_url: str
    licence: str
    dependencies: list[DependencyStatus]
    hardware_requirements: HardwareNeed
    hardware_compatibility: CompatibilityReport
    input_format: str
    output_format: str
    benchmark: dict[str, Any] | None
    known_limitations: str
    checksum_sha256: str | None
    weights_relative: str | None
    loader_key: str
    token_limit: int | None
    can_download: bool
    status: Literal["disabled", "incompatible", "ready", "loaded"]
    status_reason: str | None
    loaded: bool
    weights_loaded: bool
    load_note: str | None
    training_jobs: list[TrainingJobSummary]
    created_at: str
    card_markdown: str


class ModelListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hardware: HardwareReport
    models: list[ModelResponse]


class DownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    downloaded: list[str]
    checksum_sha256: str
    size_bytes: int

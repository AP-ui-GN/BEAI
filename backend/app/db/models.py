"""SQLite tables for uploaded structures and analysis rows."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Structure(Base):
    """A structure file stored under a server-generated name."""

    __tablename__ = "structures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    display_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class SafetyLookup(Base):
    """Retrieved safety evidence. The payload is source text, not advice."""

    __tablename__ = "safety_lookups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompoundRecord(Base):
    """A sanitized molecule. Canonical SMILES are RDKit's, with the RDKit version in the analysis."""

    __tablename__ = "compounds"
    __table_args__ = (Index("ix_compounds_inchikey", "inchikey", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    input_smiles: Mapped[str] = mapped_column(String, nullable=False)
    canonical_smiles: Mapped[str] = mapped_column(String, nullable=False)
    inchikey: Mapped[str] = mapped_column(String(27), nullable=False)
    source_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SequenceRecord(Base):
    """A validated protein sequence. Gaps are removed before storage."""

    __tablename__ = "sequences"
    __table_args__ = (Index("ix_sequences_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    header: Mapped[str] = mapped_column(String(500), nullable=False)
    sequence: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class Job(Base):
    """In-process work item. Progress is null unless the handler can measure it."""

    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    structure_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class RegisteredModel(Base):
    """A model registry row. Weights are not stored in this table and are not loaded at startup."""

    __tablename__ = "registered_models"
    __table_args__ = (Index("ix_registered_models_name_version", "name", "version", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    task: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    licence: Mapped[str] = mapped_column(String, nullable=False)
    dependencies_json: Mapped[list] = mapped_column(JSON, nullable=False)
    hardware_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_format: Mapped[str] = mapped_column(String, nullable=False)
    output_format: Mapped[str] = mapped_column(String, nullable=False)
    benchmark_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    known_limitations: Mapped[str] = mapped_column(String, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weights_relative: Mapped[str | None] = mapped_column(String, nullable=True)
    loader_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Analysis(Base):
    """One analysis run. Milestone 1 writes these from the request, not a job worker."""

    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_structure_id", "structure_id"),
        Index("ix_analyses_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    structure_id: Mapped[str | None] = mapped_column(
        ForeignKey("structures.id"),
        nullable=True,
    )
    sequence_id: Mapped[str | None] = mapped_column(
        ForeignKey("sequences.id"),
        nullable=True,
    )
    compound_id: Mapped[str | None] = mapped_column(
        ForeignKey("compounds.id"),
        nullable=True,
    )
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

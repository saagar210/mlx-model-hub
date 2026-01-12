"""SQLModel database models."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Column, Index
from sqlmodel import Field, Relationship, SQLModel

from .enums import JobStatus, ModelVersionStatus, TaskType

if TYPE_CHECKING:
    pass


def utc_now() -> datetime:
    """Get current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class ModelBase(SQLModel):
    """Base model fields."""

    name: str = Field(index=True, unique=True, max_length=255)
    task_type: TaskType = Field(default=TaskType.TEXT_GENERATION)
    description: str | None = Field(default=None, max_length=2000)
    base_model: str = Field(max_length=500)  # HuggingFace model ID
    tags: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Model(ModelBase, table=True):
    """Registered model in the hub."""

    __tablename__ = "models"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    mlflow_experiment_id: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Relationships
    versions: list["ModelVersion"] = Relationship(
        back_populates="model",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    training_jobs: list["TrainingJob"] = Relationship(
        back_populates="model",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ModelVersionBase(SQLModel):
    """Base model version fields."""

    version: str = Field(max_length=50)  # semver format
    status: ModelVersionStatus = Field(default=ModelVersionStatus.TRAINING)
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))
    artifact_path: str | None = Field(default=None, max_length=1000)


class ModelVersion(ModelVersionBase, table=True):
    """Specific version of a model with trained weights."""

    __tablename__ = "model_versions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_id: uuid.UUID = Field(foreign_key="models.id", index=True)
    mlflow_run_id: str | None = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=utc_now)

    # Relationships
    model: Model = Relationship(back_populates="versions")


class DatasetBase(SQLModel):
    """Base dataset fields."""

    name: str = Field(index=True, unique=True, max_length=255)
    path: str = Field(max_length=1000)
    checksum: str = Field(max_length=64)  # SHA256
    schema_info: dict = Field(default_factory=dict, sa_column=Column(JSON))


class Dataset(DatasetBase, table=True):
    """Registered dataset for training."""

    __tablename__ = "datasets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)

    # Relationships
    training_jobs: list["TrainingJob"] = Relationship(back_populates="dataset")


class TrainingJobBase(SQLModel):
    """Base training job fields."""

    status: JobStatus = Field(default=JobStatus.QUEUED, index=True)
    config: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: str | None = Field(default=None, max_length=5000)


class TrainingJob(TrainingJobBase, table=True):
    """Training job for fine-tuning a model."""

    __tablename__ = "training_jobs"
    __table_args__ = (
        # Index for finding stale jobs by heartbeat
        Index("ix_training_jobs_heartbeat_at", "heartbeat_at"),
        # Index for looking up jobs by model version
        Index("ix_training_jobs_model_version_id", "model_version_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_id: uuid.UUID = Field(foreign_key="models.id", index=True)
    dataset_id: uuid.UUID = Field(foreign_key="datasets.id", index=True)
    model_version_id: uuid.UUID | None = Field(default=None, foreign_key="model_versions.id")
    created_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    heartbeat_at: datetime | None = Field(default=None)

    # Relationships
    model: Model = Relationship(back_populates="training_jobs")
    dataset: Dataset = Relationship(back_populates="training_jobs")

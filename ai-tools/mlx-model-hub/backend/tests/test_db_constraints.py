"""Tests for database constraint enforcement."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from mlx_hub.db.enums import JobStatus, ModelVersionStatus, TaskType
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob


class TestDatabaseConstraints:
    """Test database constraint enforcement."""

    @pytest.mark.asyncio
    async def test_model_name_unique(self, db_session: AsyncSession):
        """Model names must be unique."""
        model1 = Model(
            name="test-model",
            base_model="meta-llama/Llama-3.2-1B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model1)
        await db_session.commit()

        model2 = Model(
            name="test-model",  # Duplicate name
            base_model="meta-llama/Llama-3.2-3B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_model_version_requires_valid_model(self, db_session: AsyncSession):
        """ModelVersion must reference existing Model."""
        # Create a version with non-existent model_id
        version = ModelVersion(
            model_id=uuid.uuid4(),  # Non-existent model
            version="1.0.0",
            status=ModelVersionStatus.TRAINING,
        )
        db_session.add(version)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_training_job_requires_valid_model(self, db_session: AsyncSession):
        """TrainingJob must reference existing Model."""
        # Create a dataset first
        dataset = Dataset(
            name="test-dataset",
            path="/data/train.jsonl",
            checksum="abc123",
        )
        db_session.add(dataset)
        await db_session.commit()
        await db_session.refresh(dataset)

        job = TrainingJob(
            model_id=uuid.uuid4(),  # Non-existent model
            dataset_id=dataset.id,
            status=JobStatus.QUEUED,
            config={"lora_rank": 16},
        )
        db_session.add(job)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_training_job_requires_valid_dataset(self, db_session: AsyncSession):
        """TrainingJob must reference existing Dataset."""
        # Create a model first
        model = Model(
            name="test-model",
            base_model="meta-llama/Llama-3.2-1B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)

        job = TrainingJob(
            model_id=model.id,
            dataset_id=uuid.uuid4(),  # Non-existent dataset
            status=JobStatus.QUEUED,
            config={"lora_rank": 16},
        )
        db_session.add(job)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_dataset_name_unique(self, db_session: AsyncSession):
        """Dataset names must be unique."""
        dataset1 = Dataset(
            name="training-data",
            path="/data/train.jsonl",
            checksum="abc123",
        )
        db_session.add(dataset1)
        await db_session.commit()

        dataset2 = Dataset(
            name="training-data",  # Duplicate
            path="/data/train2.jsonl",
            checksum="def456",
        )
        db_session.add(dataset2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_model_creates_with_defaults(self, db_session: AsyncSession):
        """Model should create with default values."""
        model = Model(
            name="default-test",
            base_model="meta-llama/Llama-3.2-1B",
        )
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)

        assert model.id is not None
        assert model.task_type == TaskType.TEXT_GENERATION
        assert model.created_at is not None
        assert model.tags == {}

    @pytest.mark.asyncio
    async def test_training_job_creates_with_defaults(self, db_session: AsyncSession):
        """TrainingJob should create with default values."""
        # Create required model and dataset
        model = Model(
            name="job-test-model",
            base_model="meta-llama/Llama-3.2-1B",
        )
        dataset = Dataset(
            name="job-test-dataset",
            path="/data/train.jsonl",
            checksum="abc123",
        )
        db_session.add(model)
        db_session.add(dataset)
        await db_session.commit()
        await db_session.refresh(model)
        await db_session.refresh(dataset)

        job = TrainingJob(
            model_id=model.id,
            dataset_id=dataset.id,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        assert job.id is not None
        assert job.status == JobStatus.QUEUED
        assert job.config == {}
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None

    @pytest.mark.asyncio
    async def test_model_version_creates_with_model(self, db_session: AsyncSession):
        """ModelVersion should link correctly to Model."""
        model = Model(
            name="version-test-model",
            base_model="meta-llama/Llama-3.2-1B",
        )
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)

        version = ModelVersion(
            model_id=model.id,
            version="1.0.0",
            status=ModelVersionStatus.READY,
            artifact_path="/models/test/v1.0.0/adapter.safetensors",
        )
        db_session.add(version)
        await db_session.commit()
        await db_session.refresh(version)

        assert version.id is not None
        assert version.model_id == model.id
        assert version.created_at is not None

    @pytest.mark.asyncio
    async def test_cascade_delete_model_versions(self, db_session: AsyncSession):
        """Deleting a Model should cascade to its versions."""
        model = Model(
            name="cascade-test",
            base_model="meta-llama/Llama-3.2-1B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)

        version = ModelVersion(
            model_id=model.id,
            version="1.0.0",
            status=ModelVersionStatus.READY,
        )
        db_session.add(version)
        await db_session.commit()
        version_id = version.id

        # Delete model
        await db_session.delete(model)
        await db_session.commit()

        # Version should be deleted too
        result = await db_session.execute(
            select(ModelVersion).where(ModelVersion.id == version_id)
        )
        assert result.scalars().first() is None

    @pytest.mark.asyncio
    async def test_cascade_delete_training_jobs(self, db_session: AsyncSession):
        """Deleting a Model should cascade to its training jobs."""
        model = Model(
            name="job-cascade-test",
            base_model="meta-llama/Llama-3.2-1B",
        )
        dataset = Dataset(
            name="job-cascade-dataset",
            path="/data/train.jsonl",
            checksum="abc123",
        )
        db_session.add(model)
        db_session.add(dataset)
        await db_session.commit()
        await db_session.refresh(model)
        await db_session.refresh(dataset)

        job = TrainingJob(
            model_id=model.id,
            dataset_id=dataset.id,
        )
        db_session.add(job)
        await db_session.commit()
        job_id = job.id

        # Delete model
        await db_session.delete(model)
        await db_session.commit()

        # Job should be deleted too
        result = await db_session.execute(
            select(TrainingJob).where(TrainingJob.id == job_id)
        )
        assert result.scalars().first() is None

    @pytest.mark.asyncio
    async def test_json_fields_store_correctly(self, db_session: AsyncSession):
        """JSON fields should store and retrieve complex data."""
        tags = {"framework": "mlx", "size": "1B", "quantization": "4bit"}
        model = Model(
            name="json-test",
            base_model="meta-llama/Llama-3.2-1B",
            tags=tags,
        )
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)

        assert model.tags == tags
        assert model.tags["framework"] == "mlx"

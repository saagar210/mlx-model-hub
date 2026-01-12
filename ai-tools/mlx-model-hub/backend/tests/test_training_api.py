"""Integration tests for /training API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from mlx_hub.config import Settings, get_settings
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob  # noqa: F401
from mlx_hub.db.session import get_session
from mlx_hub.main import app


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create temporary storage directories."""
    storage = tmp_path / "storage"
    (storage / "models").mkdir(parents=True)
    (storage / "datasets").mkdir(parents=True)

    # Create a test dataset file
    test_file = storage / "datasets" / "train.jsonl"
    test_file.write_text('{"messages": [{"role": "user", "content": "test"}]}\n')

    return storage


@pytest.fixture
def test_settings(temp_storage_dir: Path) -> Settings:
    """Create test settings."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        storage_base_path=temp_storage_dir,
        storage_models_path=temp_storage_dir / "models",
        storage_datasets_path=temp_storage_dir / "datasets",
        debug=True,
    )


@pytest_asyncio.fixture
async def test_client(test_settings: Settings, temp_storage_dir: Path):
    """Create test client with isolated database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(SQLModel.metadata.create_all)

    async def override_get_session():
        async with async_session_factory() as session:
            await session.execute(text("PRAGMA foreign_keys=ON"))
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def override_get_settings():
        return test_settings

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = override_get_settings

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def model_and_dataset(test_client: AsyncClient, temp_storage_dir: Path):
    """Create a model and dataset for testing jobs."""
    # Create model
    model_response = await test_client.post(
        "/api/models",
        json={
            "name": "test-model",
            "base_model": "meta-llama/Llama-3.2-1B",
        },
    )
    model_id = model_response.json()["id"]

    # Create dataset
    test_file = temp_storage_dir / "datasets" / "train.jsonl"
    dataset_response = await test_client.post(
        "/api/datasets",
        json={
            "name": "test-dataset",
            "path": str(test_file),
        },
    )
    dataset_id = dataset_response.json()["id"]

    return {"model_id": model_id, "dataset_id": dataset_id}


class TestTrainingJobsAPI:
    """Integration tests for /api/training endpoints."""

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_create_training_job_success(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """POST /api/training/jobs should create a new job."""
        response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
                "config": {"lora_rank": 32, "epochs": 5},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["model_id"] == model_and_dataset["model_id"]
        assert data["dataset_id"] == model_and_dataset["dataset_id"]
        assert data["status"] == "queued"
        assert data["config"]["lora_rank"] == 32
        assert data["config"]["epochs"] == 5
        assert "id" in data
        assert data["error_message"] is None

        # Worker should have been triggered
        mock_trigger.assert_called_once()

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_create_training_job_default_config(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """POST /api/training/jobs should use default config if not provided."""
        response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["config"]["lora_rank"] == 16
        assert data["config"]["lora_alpha"] == 32
        assert data["config"]["epochs"] == 3

    @pytest.mark.asyncio
    async def test_create_training_job_model_not_found(
        self, test_client: AsyncClient, model_and_dataset: dict
    ):
        """POST /api/training/jobs should reject non-existent model."""
        fake_model_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": fake_model_id,
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )

        assert response.status_code == 404
        assert "Model" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_training_job_dataset_not_found(
        self, test_client: AsyncClient, model_and_dataset: dict
    ):
        """POST /api/training/jobs should reject non-existent dataset."""
        fake_dataset_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": fake_dataset_id,
            },
        )

        assert response.status_code == 404
        assert "Dataset" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_list_training_jobs_empty(
        self, mock_trigger, test_client: AsyncClient
    ):
        """GET /api/training/jobs should return empty list initially."""
        response = await test_client.get("/api/training/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_list_training_jobs_filter_by_status(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """GET /api/training/jobs should filter by status."""
        # Create a job
        await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )

        # Filter by queued
        response = await test_client.get("/api/training/jobs?job_status=queued")
        assert response.status_code == 200
        assert response.json()["total"] == 1

        # Filter by running (should be empty)
        response = await test_client.get("/api/training/jobs?job_status=running")
        assert response.status_code == 200
        assert response.json()["total"] == 0

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_get_training_job_by_id(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """GET /api/training/jobs/{id} should return specific job."""
        create_response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )
        job_id = create_response.json()["id"]

        response = await test_client.get(f"/api/training/jobs/{job_id}")

        assert response.status_code == 200
        assert response.json()["id"] == job_id

    @pytest.mark.asyncio
    async def test_get_training_job_not_found(self, test_client: AsyncClient):
        """GET /api/training/jobs/{id} should return 404 for non-existent job."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.get(f"/api/training/jobs/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_cancel_queued_job(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """POST /api/training/jobs/{id}/cancel should cancel queued job."""
        create_response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )
        job_id = create_response.json()["id"]

        response = await test_client.post(f"/api/training/jobs/{job_id}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["completed_at"] is not None

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_get_job_queue(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """GET /api/training/queue should return queued jobs in FIFO order."""
        # Create multiple jobs
        for i in range(3):
            await test_client.post(
                "/api/training/jobs",
                json={
                    "model_id": model_and_dataset["model_id"],
                    "dataset_id": model_and_dataset["dataset_id"],
                    "config": {"job_number": i},
                },
            )

        response = await test_client.get("/api/training/queue")

        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 3
        # Should be in FIFO order
        assert jobs[0]["config"]["job_number"] == 0
        assert jobs[1]["config"]["job_number"] == 1
        assert jobs[2]["config"]["job_number"] == 2

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_get_active_job_none(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """GET /api/training/active should return None when no job running."""
        # Create a queued job
        await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )

        response = await test_client.get("/api/training/active")

        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.asyncio
    @patch("mlx_hub.api.training.trigger_worker_check", new_callable=AsyncMock)
    async def test_get_job_version_not_completed(
        self, mock_trigger, test_client: AsyncClient, model_and_dataset: dict
    ):
        """GET /api/training/jobs/{id}/version should show status for non-completed job."""
        create_response = await test_client.post(
            "/api/training/jobs",
            json={
                "model_id": model_and_dataset["model_id"],
                "dataset_id": model_and_dataset["dataset_id"],
            },
        )
        job_id = create_response.json()["id"]

        response = await test_client.get(f"/api/training/jobs/{job_id}/version")

        assert response.status_code == 200
        data = response.json()
        assert data["model_version_id"] is None
        assert data["status"] == "queued"

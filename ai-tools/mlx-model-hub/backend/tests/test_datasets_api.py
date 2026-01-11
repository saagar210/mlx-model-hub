"""Integration tests for /datasets API endpoints."""

from pathlib import Path

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
def temp_dataset_dir(tmp_path: Path) -> Path:
    """Create a temporary dataset directory with test files."""
    datasets_dir = tmp_path / "storage" / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)

    # Create test dataset file
    test_file = datasets_dir / "train.jsonl"
    test_file.write_text('{"messages": [{"role": "user", "content": "Hello"}]}\n')

    return datasets_dir


@pytest.fixture
def test_settings(temp_dataset_dir: Path) -> Settings:
    """Create test settings with temp directories."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        storage_base_path=temp_dataset_dir.parent,
        storage_models_path=temp_dataset_dir.parent / "models",
        storage_datasets_path=temp_dataset_dir,
        debug=True,
    )


@pytest_asyncio.fixture
async def test_client(test_settings: Settings, temp_dataset_dir: Path):
    """Create test client with isolated database."""
    # Create in-memory SQLite engine
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

    # Create tables
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(SQLModel.metadata.create_all)

    # Override dependencies
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

    # Cleanup
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


class TestDatasetsAPI:
    """Integration tests for /api/datasets endpoints."""

    @pytest.mark.asyncio
    async def test_create_dataset_success(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """POST /api/datasets should create a new dataset."""
        test_file = temp_dataset_dir / "train.jsonl"

        response = await test_client.post(
            "/api/datasets",
            json={
                "name": "my-training-data",
                "path": str(test_file),
                "schema_info": {"format": "jsonl", "columns": ["messages"]},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "my-training-data"
        assert data["path"] == str(test_file)
        assert len(data["checksum"]) == 64  # SHA256 hex
        assert data["schema_info"]["format"] == "jsonl"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_dataset_file_not_found(self, test_client: AsyncClient):
        """POST /api/datasets should reject non-existent file."""
        response = await test_client.post(
            "/api/datasets",
            json={
                "name": "missing-data",
                "path": "/nonexistent/file.jsonl",
            },
        )

        assert response.status_code == 400
        assert "must be within" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_dataset_path_traversal_blocked(
        self, test_client: AsyncClient, tmp_path: Path
    ):
        """POST /api/datasets should block path traversal attacks."""
        # Create a file outside the allowed directory
        outside_file = tmp_path / "outside.jsonl"
        outside_file.write_text('{"test": true}')

        response = await test_client.post(
            "/api/datasets",
            json={
                "name": "sneaky-data",
                "path": str(outside_file),
            },
        )

        assert response.status_code == 400
        assert "must be within" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_dataset_duplicate_name(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """POST /api/datasets should reject duplicate names."""
        test_file = temp_dataset_dir / "train.jsonl"

        # Create first dataset
        await test_client.post(
            "/api/datasets",
            json={"name": "dup-test", "path": str(test_file)},
        )

        # Try to create duplicate
        response = await test_client.post(
            "/api/datasets",
            json={"name": "dup-test", "path": str(test_file)},
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_dataset_duplicate_checksum(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """POST /api/datasets should detect duplicate content."""
        test_file = temp_dataset_dir / "train.jsonl"

        # Create first dataset
        await test_client.post(
            "/api/datasets",
            json={"name": "original", "path": str(test_file)},
        )

        # Create a copy with same content
        copy_file = temp_dataset_dir / "train_copy.jsonl"
        copy_file.write_text(test_file.read_text())

        # Try to create with different name but same content
        response = await test_client.post(
            "/api/datasets",
            json={"name": "duplicate-content", "path": str(copy_file)},
        )

        assert response.status_code == 409
        assert "same content" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_datasets_empty(self, test_client: AsyncClient):
        """GET /api/datasets should return empty list initially."""
        response = await test_client.get("/api/datasets")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_datasets_pagination(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """GET /api/datasets should support pagination."""
        # Create multiple datasets
        for i in range(15):
            test_file = temp_dataset_dir / f"data_{i:02d}.jsonl"
            test_file.write_text(f'{{"id": {i}}}\n')
            await test_client.post(
                "/api/datasets",
                json={"name": f"dataset-{i:02d}", "path": str(test_file)},
            )

        # Get first page
        response = await test_client.get("/api/datasets?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 15
        assert data["page"] == 1

        # Get second page
        response = await test_client.get("/api/datasets?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["page"] == 2

    @pytest.mark.asyncio
    async def test_get_dataset_by_id(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """GET /api/datasets/{id} should return specific dataset."""
        test_file = temp_dataset_dir / "train.jsonl"

        create_response = await test_client.post(
            "/api/datasets",
            json={"name": "get-test", "path": str(test_file)},
        )
        dataset_id = create_response.json()["id"]

        response = await test_client.get(f"/api/datasets/{dataset_id}")

        assert response.status_code == 200
        assert response.json()["name"] == "get-test"

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, test_client: AsyncClient):
        """GET /api/datasets/{id} should return 404 for non-existent dataset."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.get(f"/api/datasets/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_dataset(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """DELETE /api/datasets/{id} should delete the dataset."""
        test_file = temp_dataset_dir / "train.jsonl"

        create_response = await test_client.post(
            "/api/datasets",
            json={"name": "delete-test", "path": str(test_file)},
        )
        dataset_id = create_response.json()["id"]

        # Delete
        response = await test_client.delete(f"/api/datasets/{dataset_id}")
        assert response.status_code == 204

        # Verify deleted
        response = await test_client.get(f"/api/datasets/{dataset_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_verify_dataset_valid(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """POST /api/datasets/{id}/verify should verify unchanged file."""
        test_file = temp_dataset_dir / "train.jsonl"

        create_response = await test_client.post(
            "/api/datasets",
            json={"name": "verify-test", "path": str(test_file)},
        )
        dataset_id = create_response.json()["id"]

        response = await test_client.post(f"/api/datasets/{dataset_id}/verify")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["stored_checksum"] == data["current_checksum"]

    @pytest.mark.asyncio
    async def test_verify_dataset_modified(
        self, test_client: AsyncClient, temp_dataset_dir: Path
    ):
        """POST /api/datasets/{id}/verify should detect modified file."""
        test_file = temp_dataset_dir / "train.jsonl"

        create_response = await test_client.post(
            "/api/datasets",
            json={"name": "modify-test", "path": str(test_file)},
        )
        dataset_id = create_response.json()["id"]
        original_checksum = create_response.json()["checksum"]

        # Modify the file
        test_file.write_text('{"modified": true}\n')

        response = await test_client.post(f"/api/datasets/{dataset_id}/verify")

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert data["stored_checksum"] == original_checksum
        assert data["current_checksum"] != original_checksum

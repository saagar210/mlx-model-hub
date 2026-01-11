"""Integration tests for /models API endpoints."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob  # noqa: F401
from mlx_hub.db.session import get_session
from mlx_hub.main import app


@pytest_asyncio.fixture
async def test_client():
    """Create test client with isolated database."""
    # Create in-memory SQLite engine for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Create session factory
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys=ON"))
        await conn.run_sync(SQLModel.metadata.create_all)

    # Override get_session dependency
    async def override_get_session():
        async with async_session_factory() as session:
            await session.execute(text("PRAGMA foreign_keys=ON"))
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    # Create test client
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    # Clean up
    app.dependency_overrides.clear()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


class TestModelsAPI:
    """Integration tests for /api/models endpoints."""

    @pytest.mark.asyncio
    async def test_create_model_success(self, test_client: AsyncClient):
        """POST /api/models should create a new model."""
        response = await test_client.post(
            "/api/models",
            json={
                "name": "test-llama",
                "task_type": "text-generation",
                "description": "Test model for unit tests",
                "base_model": "meta-llama/Llama-3.2-1B",
                "tags": {"test": True},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-llama"
        assert data["task_type"] == "text-generation"
        assert data["base_model"] == "meta-llama/Llama-3.2-1B"
        assert data["description"] == "Test model for unit tests"
        assert data["tags"] == {"test": True}
        assert "id" in data
        assert "created_at" in data
        assert data["version_count"] == 0

    @pytest.mark.asyncio
    async def test_create_model_minimal(self, test_client: AsyncClient):
        """POST /api/models should work with minimal required fields."""
        response = await test_client.post(
            "/api/models",
            json={
                "name": "minimal-model",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "minimal-model"
        assert data["task_type"] == "text-generation"  # default
        assert data["description"] is None
        assert data["tags"] == {}

    @pytest.mark.asyncio
    async def test_create_model_duplicate_name(self, test_client: AsyncClient):
        """POST /api/models should reject duplicate names."""
        # Create first model
        await test_client.post(
            "/api/models",
            json={
                "name": "duplicate-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )

        # Try to create duplicate
        response = await test_client.post(
            "/api/models",
            json={
                "name": "duplicate-test",
                "base_model": "meta-llama/Llama-3.2-3B",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_models_empty(self, test_client: AsyncClient):
        """GET /api/models should return empty list when no models exist."""
        response = await test_client.get("/api/models")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_models_pagination(self, test_client: AsyncClient):
        """GET /api/models should return paginated results."""
        # Create multiple models
        for i in range(25):
            await test_client.post(
                "/api/models",
                json={
                    "name": f"pagination-test-{i:02d}",
                    "base_model": "meta-llama/Llama-3.2-1B",
                },
            )

        # Get first page
        response = await test_client.get("/api/models?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["page_size"] == 10

        # Get second page
        response = await test_client.get("/api/models?page=2&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["page"] == 2

        # Get third page
        response = await test_client.get("/api/models?page=3&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["page"] == 3

    @pytest.mark.asyncio
    async def test_list_models_filter_by_task_type(self, test_client: AsyncClient):
        """GET /api/models should filter by task_type."""
        # Create models with different task types
        await test_client.post(
            "/api/models",
            json={
                "name": "text-gen-model",
                "base_model": "meta-llama/Llama-3.2-1B",
                "task_type": "text-generation",
            },
        )
        await test_client.post(
            "/api/models",
            json={
                "name": "chat-model",
                "base_model": "meta-llama/Llama-3.2-1B",
                "task_type": "chat",
            },
        )

        # Filter by text-generation
        response = await test_client.get("/api/models?task_type=text-generation")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "text-gen-model"

        # Filter by chat
        response = await test_client.get("/api/models?task_type=chat")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "chat-model"

    @pytest.mark.asyncio
    async def test_get_model_by_id(self, test_client: AsyncClient):
        """GET /api/models/{id} should return specific model."""
        # Create model
        create_response = await test_client.post(
            "/api/models",
            json={
                "name": "get-by-id-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )
        model_id = create_response.json()["id"]

        # Get by ID
        response = await test_client.get(f"/api/models/{model_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == model_id
        assert data["name"] == "get-by-id-test"

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, test_client: AsyncClient):
        """GET /api/models/{id} should return 404 for non-existent model."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.get(f"/api/models/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_model(self, test_client: AsyncClient):
        """PATCH /api/models/{id} should update model fields."""
        # Create model
        create_response = await test_client.post(
            "/api/models",
            json={
                "name": "update-test",
                "base_model": "meta-llama/Llama-3.2-1B",
                "description": "Original description",
            },
        )
        model_id = create_response.json()["id"]

        # Update model
        response = await test_client.patch(
            f"/api/models/{model_id}",
            json={
                "description": "Updated description",
                "tags": {"updated": True},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["tags"] == {"updated": True}

    @pytest.mark.asyncio
    async def test_delete_model(self, test_client: AsyncClient):
        """DELETE /api/models/{id} should delete the model."""
        # Create model
        create_response = await test_client.post(
            "/api/models",
            json={
                "name": "delete-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )
        model_id = create_response.json()["id"]

        # Delete model
        response = await test_client.delete(f"/api/models/{model_id}")
        assert response.status_code == 204

        # Verify model is deleted
        response = await test_client.get(f"/api/models/{model_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_model_not_found(self, test_client: AsyncClient):
        """DELETE /api/models/{id} should return 404 for non-existent model."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.delete(f"/api/models/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_model_versions_empty(self, test_client: AsyncClient):
        """GET /api/models/{id}/versions should return empty list initially."""
        # Create model
        create_response = await test_client.post(
            "/api/models",
            json={
                "name": "versions-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )
        model_id = create_response.json()["id"]

        # Get versions
        response = await test_client.get(f"/api/models/{model_id}/versions")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_model_history_no_mlflow(self, test_client: AsyncClient):
        """GET /api/models/{id}/history should return empty when no MLflow experiment."""
        # Create model
        create_response = await test_client.post(
            "/api/models",
            json={
                "name": "history-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )
        model_id = create_response.json()["id"]

        # Get history
        response = await test_client.get(f"/api/models/{model_id}/history")
        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["experiment_id"] is None

    @pytest.mark.asyncio
    async def test_health_check(self, test_client: AsyncClient):
        """GET /health should return healthy status."""
        response = await test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "version" in data

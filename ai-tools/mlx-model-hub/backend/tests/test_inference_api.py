"""Integration tests for /inference API endpoints."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from mlx_hub.api.inference import get_engine
from mlx_hub.config import Settings, get_settings
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob  # noqa: F401
from mlx_hub.db.session import get_session
from mlx_hub.inference import reset_model_cache
from mlx_hub.inference.cache import CachedModel
from mlx_hub.inference.engine import GenerationResult, InferenceEngine
from mlx_hub.main import app


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create temporary storage directories."""
    storage = tmp_path / "storage"
    (storage / "models").mkdir(parents=True)
    (storage / "datasets").mkdir(parents=True)
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
async def test_client(test_settings: Settings, mock_engine: MagicMock):
    """Create test client with isolated database and mocked inference engine."""
    db_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async_session_factory = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with db_engine.begin() as conn:
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

    def override_get_engine():
        return mock_engine

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_engine] = override_get_engine

    # Reset cache before each test
    reset_model_cache()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
    reset_model_cache()

    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_engine.dispose()


@pytest_asyncio.fixture
async def test_model(test_client: AsyncClient) -> dict:
    """Create a test model."""
    response = await test_client.post(
        "/api/models",
        json={
            "name": "test-inference-model",
            "base_model": "meta-llama/Llama-3.2-1B",
        },
    )
    return response.json()


def mock_cached_model() -> CachedModel:
    """Create a mock cached model."""
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    mock_tokenizer.encode = MagicMock(return_value=[1, 2, 3, 4, 5])

    return CachedModel(
        model_id="test-model",
        model=mock_model,
        tokenizer=mock_tokenizer,
        adapter_path=None,
        estimated_memory_gb=4.0,
    )


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create a mock inference engine for testing."""
    engine = MagicMock(spec=InferenceEngine)
    engine.load_model = AsyncMock(return_value=mock_cached_model())
    engine.generate = AsyncMock(
        return_value=GenerationResult(
            text="Hello! I am an AI assistant.",
            tokens_generated=10,
            time_to_first_token=0.05,
            total_time=0.5,
            tokens_per_second=20.0,
        )
    )
    engine.unload_model = MagicMock(return_value=True)
    engine.get_cache_stats = MagicMock(
        return_value={
            "cached_models": 2,
            "max_models": 3,
            "total_memory_gb": 8.0,
            "max_memory_gb": 36.0,
            "models": ["model-1", "model-2"],
        }
    )
    engine.cache = MagicMock()
    engine.cache.clear = MagicMock()
    return engine


class TestInferenceAPI:
    """Integration tests for /api/inference endpoints."""

    @pytest.mark.asyncio
    async def test_inference_model_not_found(self, test_client: AsyncClient):
        """POST /api/inference should return 404 for non-existent model."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await test_client.post(
            "/api/inference",
            json={
                "model_id": fake_id,
                "prompt": "Hello, world!",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_inference_stream_redirect(
        self, test_client: AsyncClient, test_model: dict
    ):
        """POST /api/inference with stream=True should return 400."""
        response = await test_client.post(
            "/api/inference",
            json={
                "model_id": test_model["id"],
                "prompt": "Hello!",
                "stream": True,
            },
        )

        assert response.status_code == 400
        assert "stream" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_inference_success(
        self, test_client: AsyncClient, test_model: dict
    ):
        """POST /api/inference should return generated text."""
        response = await test_client.post(
            "/api/inference",
            json={
                "model_id": test_model["id"],
                "prompt": "Hello!",
                "max_tokens": 100,
                "temperature": 0.7,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Hello! I am an AI assistant."
        assert data["model_id"] == test_model["id"]
        assert data["tokens_generated"] == 10
        assert data["time_to_first_token"] == 0.05
        assert data["tokens_per_second"] == 20.0

    @pytest.mark.asyncio
    async def test_inference_with_version(
        self, test_client: AsyncClient, test_model: dict
    ):
        """POST /api/inference with version_id should load adapter."""
        # This test would need a ModelVersion to exist
        # For now, test that non-existent version returns 404
        fake_version_id = "00000000-0000-0000-0000-000000000001"

        response = await test_client.post(
            "/api/inference",
            json={
                "model_id": test_model["id"],
                "version_id": fake_version_id,
                "prompt": "Hello!",
            },
        )

        assert response.status_code == 404
        assert "version" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, test_client: AsyncClient):
        """GET /api/inference/cache should return cache statistics."""
        response = await test_client.get("/api/inference/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["cached_models"] == 2
        assert data["max_models"] == 3
        assert data["total_memory_gb"] == 8.0
        assert len(data["models"]) == 2

    @pytest.mark.asyncio
    async def test_unload_model_success(self, test_client: AsyncClient):
        """DELETE /api/inference/cache/{key} should unload model."""
        response = await test_client.delete("/api/inference/cache/test-model")

        assert response.status_code == 200
        assert "unloaded" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_unload_model_not_found(
        self, test_client: AsyncClient, mock_engine: MagicMock
    ):
        """DELETE /api/inference/cache/{key} should return 404 if not cached."""
        # Override the mock to return False for this test
        mock_engine.unload_model.return_value = False

        response = await test_client.delete("/api/inference/cache/not-cached")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_clear_cache(
        self, test_client: AsyncClient, mock_engine: MagicMock
    ):
        """DELETE /api/inference/cache should clear all cached models."""
        response = await test_client.delete("/api/inference/cache")

        assert response.status_code == 200
        assert "cleared" in response.json()["message"].lower()
        mock_engine.cache.clear.assert_called_once()


class TestModelCache:
    """Tests for the model cache."""

    def test_cache_put_get(self):
        """Cache should store and retrieve models."""
        from mlx_hub.inference.cache import ModelCache

        cache = ModelCache(max_memory_gb=100, max_models=5)

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()

        cached = cache.put(
            key="test-model",
            model=mock_model,
            tokenizer=mock_tokenizer,
            estimated_memory_gb=4.0,
        )

        assert cached is not None
        assert cached.model_id == "test-model"

        retrieved = cache.get("test-model")
        assert retrieved is not None
        assert retrieved.model == mock_model

    def test_cache_lru_eviction(self):
        """Cache should evict LRU models when full."""
        from mlx_hub.inference.cache import ModelCache

        cache = ModelCache(max_memory_gb=100, max_models=2)

        # Add 3 models, first should be evicted
        for i in range(3):
            cache.put(
                key=f"model-{i}",
                model=MagicMock(),
                tokenizer=MagicMock(),
                estimated_memory_gb=1.0,
            )

        assert len(cache) == 2
        assert cache.get("model-0") is None  # Evicted
        assert cache.get("model-1") is not None
        assert cache.get("model-2") is not None

    def test_cache_memory_limit_eviction(self):
        """Cache should evict models when memory limit exceeded."""
        from mlx_hub.inference.cache import ModelCache

        cache = ModelCache(max_memory_gb=10, max_models=10)

        # Add models until memory exceeded
        cache.put("model-1", MagicMock(), MagicMock(), estimated_memory_gb=4.0)
        cache.put("model-2", MagicMock(), MagicMock(), estimated_memory_gb=4.0)

        # This should cause eviction of model-1
        cache.put("model-3", MagicMock(), MagicMock(), estimated_memory_gb=4.0)

        stats = cache.stats()
        assert stats["total_memory_gb"] <= 10

    def test_cache_stats(self):
        """Cache should report accurate statistics."""
        from mlx_hub.inference.cache import ModelCache

        cache = ModelCache(max_memory_gb=36, max_models=3)

        cache.put("model-1", MagicMock(), MagicMock(), estimated_memory_gb=4.0)
        cache.put("model-2", MagicMock(), MagicMock(), estimated_memory_gb=6.0)

        stats = cache.stats()
        assert stats["cached_models"] == 2
        assert stats["max_models"] == 3
        assert stats["total_memory_gb"] == 10.0
        assert stats["max_memory_gb"] == 36

    def test_cache_remove(self):
        """Cache should remove specific models."""
        from mlx_hub.inference.cache import ModelCache

        cache = ModelCache(max_memory_gb=100, max_models=5)

        cache.put("model-1", MagicMock(), MagicMock(), estimated_memory_gb=4.0)

        assert cache.remove("model-1") is True
        assert cache.get("model-1") is None
        assert cache.remove("model-1") is False  # Already removed

    def test_cache_clear(self):
        """Cache should clear all models."""
        from mlx_hub.inference.cache import ModelCache

        cache = ModelCache(max_memory_gb=100, max_models=5)

        cache.put("model-1", MagicMock(), MagicMock(), estimated_memory_gb=4.0)
        cache.put("model-2", MagicMock(), MagicMock(), estimated_memory_gb=4.0)

        cache.clear()

        assert len(cache) == 0
        stats = cache.stats()
        assert stats["total_memory_gb"] == 0.0

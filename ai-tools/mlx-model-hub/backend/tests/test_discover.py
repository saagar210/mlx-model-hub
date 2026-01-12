"""Tests for model discovery API endpoints."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mlx_hub.services.huggingface import (
    HuggingFaceService,
    ModelMetadata,
    ModelFile,
    SearchResult,
)


# Test fixtures
@pytest.fixture
def mock_model_metadata():
    """Create a mock model metadata."""
    return ModelMetadata(
        model_id="mlx-community/Llama-3.2-3B-4bit",
        author="mlx-community",
        model_name="Llama-3.2-3B-4bit",
        downloads=50000,
        likes=100,
        tags=["mlx", "llama", "4bit", "text-generation"],
        pipeline_tag="text-generation",
        library_name="mlx",
        created_at="2024-01-01T00:00:00Z",
        last_modified="2024-06-01T00:00:00Z",
        total_size_bytes=2 * 1024 * 1024 * 1024,  # 2GB
        estimated_memory_gb=2.4,
        quantization="4-bit",
        files=[
            ModelFile(filename="model.safetensors", size_bytes=2 * 1024 * 1024 * 1024, lfs=True),
            ModelFile(filename="config.json", size_bytes=1024, lfs=False),
        ],
    )


@pytest.fixture
def mock_search_result(mock_model_metadata):
    """Create a mock search result."""
    return SearchResult(
        models=[mock_model_metadata],
        total_count=1,
        page=1,
        page_size=20,
    )


class TestHuggingFaceService:
    """Tests for HuggingFaceService."""

    def test_detect_quantization_4bit(self):
        """Test 4-bit quantization detection."""
        service = HuggingFaceService()

        assert service._detect_quantization("mlx-community/Model-4bit", []) == "4-bit"
        assert service._detect_quantization("some-model", ["4bit"]) == "4-bit"

    def test_detect_quantization_8bit(self):
        """Test 8-bit quantization detection."""
        service = HuggingFaceService()

        assert service._detect_quantization("mlx-community/Model-8bit", []) == "8-bit"

    def test_detect_quantization_fp16(self):
        """Test FP16 detection."""
        service = HuggingFaceService()

        assert service._detect_quantization("mlx-community/Model-fp16", []) == "FP16"

    def test_detect_quantization_none(self):
        """Test no quantization detected."""
        service = HuggingFaceService()

        assert service._detect_quantization("mlx-community/Model", []) is None

    def test_estimate_memory_quantized(self):
        """Test memory estimation for quantized model."""
        service = HuggingFaceService()
        metadata = ModelMetadata(
            model_id="test",
            author="test",
            model_name="test",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            total_size_bytes=2 * 1024 * 1024 * 1024,  # 2GB
            quantization="4-bit",
        )

        memory = service._estimate_memory(metadata)
        # 2GB * 1.2 (4-bit multiplier) = 2.4GB
        assert 2.3 < memory < 2.5

    def test_estimate_memory_full_precision(self):
        """Test memory estimation for full precision model."""
        service = HuggingFaceService()
        metadata = ModelMetadata(
            model_id="test",
            author="test",
            model_name="test",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            total_size_bytes=2 * 1024 * 1024 * 1024,  # 2GB
            quantization=None,
        )

        memory = service._estimate_memory(metadata)
        # 2GB * 1.5 (full precision multiplier) = 3.0GB
        assert 2.9 < memory < 3.1

    def test_check_memory_compatibility_compatible(self):
        """Test memory compatibility check - compatible."""
        service = HuggingFaceService()
        metadata = ModelMetadata(
            model_id="test",
            author="test",
            model_name="test",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            estimated_memory_gb=4.0,
        )

        result = service.check_memory_compatibility(metadata, available_memory_gb=16.0)

        assert result["status"] == "compatible"
        assert result["warning"] is None

    def test_check_memory_compatibility_tight(self):
        """Test memory compatibility check - tight."""
        service = HuggingFaceService()
        metadata = ModelMetadata(
            model_id="test",
            author="test",
            model_name="test",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            estimated_memory_gb=15.0,
        )

        result = service.check_memory_compatibility(metadata, available_memory_gb=16.0)

        assert result["status"] == "tight"
        assert result["warning"] is not None

    def test_check_memory_compatibility_incompatible(self):
        """Test memory compatibility check - incompatible."""
        service = HuggingFaceService()
        metadata = ModelMetadata(
            model_id="test",
            author="test",
            model_name="test",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            estimated_memory_gb=32.0,
        )

        result = service.check_memory_compatibility(metadata, available_memory_gb=16.0)

        assert result["status"] == "incompatible"
        assert result["warning"] is not None

    def test_model_metadata_properties(self, mock_model_metadata):
        """Test ModelMetadata properties."""
        assert mock_model_metadata.is_mlx is True
        assert mock_model_metadata.is_quantized is True
        assert mock_model_metadata.size_gb == pytest.approx(2.0, rel=0.01)


@pytest.fixture
def mock_hf_service(mock_model_metadata, mock_search_result):
    """Create a mock HuggingFace service."""
    service = MagicMock(spec=HuggingFaceService)
    service.search_models = AsyncMock(return_value=mock_search_result)
    service.get_model_info = AsyncMock(return_value=mock_model_metadata)
    service.check_memory_compatibility = MagicMock(return_value={
        "status": "compatible",
        "message": "Model fits",
        "warning": None,
        "required_memory_gb": 2.4,
        "available_memory_gb": 16.0,
        "total_memory_gb": 32.0,
    })
    return service


class TestDiscoverAPI:
    """Tests for discover API endpoints."""

    @pytest.mark.asyncio
    async def test_search_models(self, async_client, mock_hf_service):
        """Test search models endpoint."""
        from mlx_hub.main import app
        from mlx_hub.services.huggingface import get_huggingface_service

        app.dependency_overrides[get_huggingface_service] = lambda: mock_hf_service
        try:
            response = await async_client.get(
                "/api/discover/search",
                params={"query": "llama", "page": 1, "page_size": 20}
            )

            assert response.status_code == 200
            data = response.json()
            assert "models" in data
            assert "total_count" in data
        finally:
            app.dependency_overrides.pop(get_huggingface_service, None)

    @pytest.mark.asyncio
    async def test_get_model_info(self, async_client, mock_hf_service):
        """Test get model info endpoint."""
        from mlx_hub.main import app
        from mlx_hub.services.huggingface import get_huggingface_service

        app.dependency_overrides[get_huggingface_service] = lambda: mock_hf_service
        try:
            response = await async_client.get(
                "/api/discover/models/mlx-community/Llama-3.2-3B-4bit"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["model_id"] == "mlx-community/Llama-3.2-3B-4bit"
            assert data["quantization"] == "4-bit"
        finally:
            app.dependency_overrides.pop(get_huggingface_service, None)

    @pytest.mark.asyncio
    async def test_get_model_info_not_found(self, async_client):
        """Test get model info endpoint - not found."""
        from mlx_hub.main import app
        from mlx_hub.services.huggingface import get_huggingface_service

        mock_service = MagicMock(spec=HuggingFaceService)
        mock_service.get_model_info = AsyncMock(return_value=None)

        app.dependency_overrides[get_huggingface_service] = lambda: mock_service
        try:
            response = await async_client.get(
                "/api/discover/models/nonexistent/model"
            )

            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_huggingface_service, None)

    @pytest.mark.asyncio
    async def test_check_compatibility(self, async_client, mock_hf_service):
        """Test check compatibility endpoint."""
        from mlx_hub.main import app
        from mlx_hub.services.huggingface import get_huggingface_service

        app.dependency_overrides[get_huggingface_service] = lambda: mock_hf_service
        try:
            response = await async_client.get(
                "/api/discover/models/mlx-community/Llama-3.2-3B-4bit/compatibility"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "compatible"
            assert data["required_memory_gb"] == 2.4
        finally:
            app.dependency_overrides.pop(get_huggingface_service, None)

    @pytest.mark.asyncio
    async def test_get_popular_models(self, async_client, mock_hf_service):
        """Test get popular models endpoint."""
        from mlx_hub.main import app
        from mlx_hub.services.huggingface import get_huggingface_service

        app.dependency_overrides[get_huggingface_service] = lambda: mock_hf_service
        try:
            response = await async_client.get("/api/discover/popular?limit=10")

            assert response.status_code == 200
            data = response.json()
            assert "models" in data
        finally:
            app.dependency_overrides.pop(get_huggingface_service, None)

    @pytest.mark.asyncio
    async def test_get_recent_models(self, async_client, mock_hf_service):
        """Test get recent models endpoint."""
        from mlx_hub.main import app
        from mlx_hub.services.huggingface import get_huggingface_service

        app.dependency_overrides[get_huggingface_service] = lambda: mock_hf_service
        try:
            response = await async_client.get("/api/discover/recent?limit=10")

            assert response.status_code == 200
            data = response.json()
            assert "models" in data
        finally:
            app.dependency_overrides.pop(get_huggingface_service, None)

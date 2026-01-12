"""Tests for HuggingFace service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mlx_hub.services.huggingface import (
    HuggingFaceService,
    ModelFile,
    ModelMetadata,
    SearchResult,
    get_huggingface_service,
)


class TestModelMetadata:
    """Tests for ModelMetadata dataclass."""

    def test_is_mlx_with_mlx_tag(self):
        """Model with mlx tag should be identified as MLX."""
        metadata = ModelMetadata(
            model_id="mlx-community/test",
            author="mlx-community",
            model_name="test",
            downloads=100,
            likes=10,
            tags=["mlx", "text-generation"],
            pipeline_tag="text-generation",
            library_name=None,
            created_at=None,
            last_modified=None,
        )
        assert metadata.is_mlx is True

    def test_is_mlx_with_library_name(self):
        """Model with mlx library should be identified as MLX."""
        metadata = ModelMetadata(
            model_id="test/model",
            author="test",
            model_name="model",
            downloads=100,
            likes=10,
            tags=["text-generation"],
            pipeline_tag="text-generation",
            library_name="mlx",
            created_at=None,
            last_modified=None,
        )
        assert metadata.is_mlx is True

    def test_is_not_mlx(self):
        """Model without mlx markers should not be identified as MLX."""
        metadata = ModelMetadata(
            model_id="test/model",
            author="test",
            model_name="model",
            downloads=100,
            likes=10,
            tags=["pytorch", "text-generation"],
            pipeline_tag="text-generation",
            library_name="transformers",
            created_at=None,
            last_modified=None,
        )
        assert metadata.is_mlx is False

    def test_is_quantized_with_quantization(self):
        """Model with quantization should be identified."""
        metadata = ModelMetadata(
            model_id="test/model-4bit",
            author="test",
            model_name="model-4bit",
            downloads=100,
            likes=10,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            quantization="4-bit",
        )
        assert metadata.is_quantized is True

    def test_is_not_quantized(self):
        """Model without quantization should not be identified."""
        metadata = ModelMetadata(
            model_id="test/model",
            author="test",
            model_name="model",
            downloads=100,
            likes=10,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
        )
        assert metadata.is_quantized is False

    def test_size_gb_calculation(self):
        """Size in GB should be calculated correctly."""
        metadata = ModelMetadata(
            model_id="test/model",
            author="test",
            model_name="model",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            total_size_bytes=5 * 1024**3,  # 5 GB
        )
        assert metadata.size_gb == 5.0


class TestQuantizationDetection:
    """Tests for quantization detection logic."""

    @pytest.fixture
    def service(self):
        """Create HuggingFace service."""
        return HuggingFaceService()

    def test_detect_4bit(self, service):
        """Should detect 4-bit quantization."""
        result = service._detect_quantization("mlx-community/Llama-3.2-3B-4bit", [])
        assert result == "4-bit"

    def test_detect_8bit(self, service):
        """Should detect 8-bit quantization."""
        result = service._detect_quantization("test/model-8bit", [])
        assert result == "8-bit"

    def test_detect_q4_k_m(self, service):
        """Should detect Q4_K_M quantization."""
        result = service._detect_quantization("test/model-q4_k_m", [])
        assert result == "Q4_K_M"

    def test_detect_fp16(self, service):
        """Should detect FP16."""
        result = service._detect_quantization("test/model-fp16", [])
        assert result == "FP16"

    def test_detect_bf16(self, service):
        """Should detect BF16."""
        result = service._detect_quantization("test/model-bf16", [])
        assert result == "BF16"

    def test_detect_from_tags(self, service):
        """Should detect quantization from tags."""
        result = service._detect_quantization("test/model", ["4-bit", "mlx"])
        assert result == "4-bit"

    def test_no_quantization(self, service):
        """Should return None when no quantization detected."""
        result = service._detect_quantization("test/model", ["mlx"])
        assert result is None


class TestModelIdValidation:
    """Tests for model ID validation in HuggingFace service."""

    @pytest.fixture
    def service(self):
        """Create HuggingFace service."""
        return HuggingFaceService()

    def test_valid_model_id(self, service):
        """Valid model IDs should pass."""
        assert service._validate_model_id("mlx-community/Llama-3.2-3B") is True
        assert service._validate_model_id("meta-llama/Llama-2-7b") is True

    def test_invalid_model_id_no_slash(self, service):
        """Model IDs without slash should fail."""
        assert service._validate_model_id("just-model-name") is False

    def test_invalid_model_id_empty(self, service):
        """Empty model IDs should fail."""
        assert service._validate_model_id("") is False

    def test_invalid_model_id_path_traversal(self, service):
        """Path traversal attempts should fail."""
        assert service._validate_model_id("../etc/passwd") is False
        assert service._validate_model_id("owner/../other") is False


class TestMemoryCompatibility:
    """Tests for memory compatibility checking."""

    @pytest.fixture
    def service(self):
        """Create HuggingFace service."""
        return HuggingFaceService()

    def test_compatible_model(self, service):
        """Small model should be compatible."""
        metadata = ModelMetadata(
            model_id="test/small",
            author="test",
            model_name="small",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            estimated_memory_gb=4.0,
        )

        result = service.check_memory_compatibility(metadata, available_memory_gb=32.0)

        assert result["status"] == "compatible"
        assert result["required_memory_gb"] == 4.0
        assert result["available_memory_gb"] == 32.0

    def test_tight_fit_model(self, service):
        """Model that barely fits should be marked as tight."""
        metadata = ModelMetadata(
            model_id="test/medium",
            author="test",
            model_name="medium",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            estimated_memory_gb=28.0,
        )

        result = service.check_memory_compatibility(metadata, available_memory_gb=32.0)

        assert result["status"] == "tight"
        assert result["warning"] is not None

    def test_incompatible_model(self, service):
        """Model too large should be incompatible."""
        metadata = ModelMetadata(
            model_id="test/large",
            author="test",
            model_name="large",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            estimated_memory_gb=64.0,
        )

        result = service.check_memory_compatibility(metadata, available_memory_gb=32.0)

        assert result["status"] == "incompatible"
        assert result["warning"] is not None


class TestMemoryEstimation:
    """Tests for memory estimation logic."""

    @pytest.fixture
    def service(self):
        """Create HuggingFace service."""
        return HuggingFaceService()

    def test_estimate_memory_quantized_4bit(self, service):
        """4-bit quantized model should have lower multiplier."""
        metadata = ModelMetadata(
            model_id="test/model",
            author="test",
            model_name="model",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            total_size_bytes=4 * 1024**3,  # 4 GB
            quantization="4-bit",
        )

        estimated = service._estimate_memory(metadata)

        # 4GB * 1.2 = 4.8 GB
        assert estimated == pytest.approx(4.8, rel=0.1)

    def test_estimate_memory_full_precision(self, service):
        """Full precision model should have higher multiplier."""
        metadata = ModelMetadata(
            model_id="test/model",
            author="test",
            model_name="model",
            downloads=0,
            likes=0,
            tags=[],
            pipeline_tag=None,
            library_name=None,
            created_at=None,
            last_modified=None,
            total_size_bytes=4 * 1024**3,  # 4 GB
            quantization=None,
        )

        estimated = service._estimate_memory(metadata)

        # 4GB * 1.5 = 6.0 GB
        assert estimated == pytest.approx(6.0, rel=0.1)


class TestGlobalServiceInstance:
    """Tests for global service instance management."""

    def test_get_service_returns_instance(self):
        """get_huggingface_service should return an instance."""
        service = get_huggingface_service()
        assert isinstance(service, HuggingFaceService)

    def test_get_service_returns_same_instance(self):
        """get_huggingface_service should return cached instance."""
        service1 = get_huggingface_service()
        service2 = get_huggingface_service()
        assert service1 is service2


class TestDownloadValidation:
    """Tests for download path validation."""

    @pytest.fixture
    def service(self):
        """Create HuggingFace service."""
        return HuggingFaceService()

    @pytest.mark.asyncio
    async def test_download_invalid_model_id(self, service):
        """Download with invalid model ID should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid model ID"):
            await service.download_model("invalid-no-slash")

    @pytest.mark.asyncio
    async def test_download_path_traversal_blocked(self, service, tmp_path, monkeypatch):
        """Download with path traversal should raise ValueError."""
        # Set up storage path
        storage_path = tmp_path / "models"
        storage_path.mkdir()

        monkeypatch.setenv("STORAGE_MODELS_PATH", str(storage_path))

        from mlx_hub.config import get_settings

        get_settings.cache_clear()

        with pytest.raises(ValueError, match="Output directory must be under"):
            await service.download_model(
                "valid/model-id",
                output_dir="/tmp/evil-path",
            )

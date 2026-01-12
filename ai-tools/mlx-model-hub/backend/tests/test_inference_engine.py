"""Tests for inference engine module."""

import pytest
from unittest.mock import MagicMock, patch

from mlx_hub.inference.engine import (
    GenerationConfig,
    GenerationResult,
    InferenceEngine,
    get_inference_engine,
)


class TestGenerationConfig:
    """Tests for GenerationConfig dataclass."""

    def test_default_values(self):
        """Config should have sensible defaults."""
        config = GenerationConfig()

        assert config.max_tokens == 256
        assert config.temperature == 0.7
        assert config.top_p == 0.9
        assert config.top_k == 50
        assert config.repetition_penalty == 1.1
        assert config.stop_sequences == []

    def test_from_dict_with_all_fields(self):
        """from_dict should create config from complete dictionary."""
        d = {
            "max_tokens": 512,
            "temperature": 0.5,
            "top_p": 0.95,
            "top_k": 100,
            "repetition_penalty": 1.2,
            "stop_sequences": ["<end>", "###"],
        }
        config = GenerationConfig.from_dict(d)

        assert config.max_tokens == 512
        assert config.temperature == 0.5
        assert config.top_p == 0.95
        assert config.top_k == 100
        assert config.repetition_penalty == 1.2
        assert config.stop_sequences == ["<end>", "###"]

    def test_from_dict_with_partial_fields(self):
        """from_dict should use defaults for missing fields."""
        d = {"max_tokens": 1024}
        config = GenerationConfig.from_dict(d)

        assert config.max_tokens == 1024
        assert config.temperature == 0.7  # default
        assert config.top_p == 0.9  # default

    def test_from_dict_ignores_unknown_keys(self):
        """from_dict should ignore unknown fields."""
        d = {
            "max_tokens": 512,
            "unknown_field": "ignored",
            "another_unknown": 999,
        }
        config = GenerationConfig.from_dict(d)

        assert config.max_tokens == 512
        assert not hasattr(config, "unknown_field")

    def test_from_dict_empty(self):
        """from_dict with empty dict should use all defaults."""
        config = GenerationConfig.from_dict({})

        assert config.max_tokens == 256
        assert config.temperature == 0.7


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_to_dict(self):
        """to_dict should include all fields."""
        result = GenerationResult(
            text="Hello, world!",
            tokens_generated=3,
            time_to_first_token=0.05,
            total_time=0.2,
            tokens_per_second=15.0,
        )

        d = result.to_dict()

        assert d["text"] == "Hello, world!"
        assert d["tokens_generated"] == 3
        assert d["time_to_first_token"] == 0.05
        assert d["total_time"] == 0.2
        assert d["tokens_per_second"] == 15.0

    def test_to_dict_keys(self):
        """to_dict should have expected keys."""
        result = GenerationResult(
            text="test",
            tokens_generated=1,
            time_to_first_token=0.01,
            total_time=0.1,
            tokens_per_second=10.0,
        )

        expected_keys = {
            "text",
            "tokens_generated",
            "time_to_first_token",
            "total_time",
            "tokens_per_second",
        }
        assert set(result.to_dict().keys()) == expected_keys


class TestInferenceEngine:
    """Tests for InferenceEngine class."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Clear settings cache before and after tests."""
        from mlx_hub.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    @pytest.fixture
    def mock_cache(self):
        """Create mock model cache."""
        cache = MagicMock()
        cache.get.return_value = None
        cache.stats.return_value = {"size": 0, "memory_gb": 0.0}
        return cache

    def test_engine_init(self, monkeypatch, tmp_path):
        """Engine should initialize with settings and cache."""
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.inference.engine.get_model_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_get_cache.return_value = mock_cache

            from mlx_hub.config import get_settings

            get_settings.cache_clear()

            engine = InferenceEngine()

            assert engine.settings is not None
            assert engine.cache == mock_cache

    def test_get_cache_stats(self, monkeypatch, tmp_path):
        """get_cache_stats should return cache statistics."""
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.inference.engine.get_model_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.stats.return_value = {
                "size": 2,
                "memory_gb": 8.5,
                "models": ["model-a", "model-b"],
            }
            mock_get_cache.return_value = mock_cache

            from mlx_hub.config import get_settings

            get_settings.cache_clear()

            engine = InferenceEngine()
            stats = engine.get_cache_stats()

            assert stats["size"] == 2
            assert stats["memory_gb"] == 8.5
            mock_cache.stats.assert_called_once()

    def test_unload_model_found(self, monkeypatch, tmp_path):
        """unload_model should return True if model was removed."""
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.inference.engine.get_model_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.remove.return_value = True
            mock_get_cache.return_value = mock_cache

            from mlx_hub.config import get_settings

            get_settings.cache_clear()

            engine = InferenceEngine()
            result = engine.unload_model("test-key")

            assert result is True
            mock_cache.remove.assert_called_once_with("test-key")

    def test_unload_model_not_found(self, monkeypatch, tmp_path):
        """unload_model should return False if model not in cache."""
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.inference.engine.get_model_cache") as mock_get_cache:
            mock_cache = MagicMock()
            mock_cache.remove.return_value = False
            mock_get_cache.return_value = mock_cache

            from mlx_hub.config import get_settings

            get_settings.cache_clear()

            engine = InferenceEngine()
            result = engine.unload_model("nonexistent-key")

            assert result is False


class TestGlobalEngineInstance:
    """Tests for global engine instance management."""

    @pytest.fixture(autouse=True)
    def reset_global_engine(self):
        """Reset global engine before and after tests."""
        import mlx_hub.inference.engine as engine_module

        original = engine_module._inference_engine
        engine_module._inference_engine = None
        yield
        engine_module._inference_engine = original

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self):
        """Clear settings cache."""
        from mlx_hub.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()

    def test_get_inference_engine_creates_instance(self, monkeypatch, tmp_path):
        """get_inference_engine should create engine on first call."""
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.inference.engine.get_model_cache"):
            from mlx_hub.config import get_settings

            get_settings.cache_clear()

            engine = get_inference_engine()
            assert isinstance(engine, InferenceEngine)

    def test_get_inference_engine_returns_same_instance(self, monkeypatch, tmp_path):
        """get_inference_engine should return cached instance."""
        monkeypatch.setenv("STORAGE_BASE_PATH", str(tmp_path))

        with patch("mlx_hub.inference.engine.get_model_cache"):
            from mlx_hub.config import get_settings

            get_settings.cache_clear()

            engine1 = get_inference_engine()
            engine2 = get_inference_engine()
            assert engine1 is engine2

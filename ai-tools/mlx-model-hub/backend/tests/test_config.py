"""Tests for configuration management."""

from pathlib import Path

from mlx_hub.config import Settings, get_settings


class TestSettings:
    """Test configuration management."""

    def test_settings_load_defaults(self):
        """Settings should load with sensible defaults."""
        settings = Settings()

        assert settings.app_name == "MLX Model Hub"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000

    def test_settings_load_from_env(self, monkeypatch):
        """Settings should load from environment variables."""
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PORT", "9000")

        # Clear cache to reload settings
        get_settings.cache_clear()
        settings = Settings()

        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.port == 9000

    def test_settings_database_url_format(self):
        """Database URL should be valid asyncpg format."""
        settings = Settings()

        assert "postgresql+asyncpg://" in settings.database_url

    def test_storage_directories_created(self, tmp_path: Path):
        """Storage directories should be created on initialization."""
        settings = Settings(
            storage_base_path=tmp_path / "storage",
            storage_models_path=tmp_path / "storage/models",
            storage_datasets_path=tmp_path / "storage/datasets",
        )
        settings.ensure_directories()

        assert settings.storage_base_path.exists()
        assert settings.storage_models_path.exists()
        assert settings.storage_datasets_path.exists()

    def test_mlx_memory_limit_reasonable(self):
        """MLX memory limit should be within hardware constraints."""
        settings = Settings()

        # Should be less than 48GB total, leaving headroom
        assert settings.mlx_memory_limit_gb <= 36
        assert settings.mlx_memory_limit_gb > 0

    def test_get_settings_cached(self):
        """get_settings should return cached instance."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_mlflow_tracking_uri_default(self):
        """MLflow tracking URI should have sensible default."""
        settings = Settings()

        assert settings.mlflow_tracking_uri == "http://localhost:5001"

    def test_mlx_quantization_options(self):
        """MLX quantization should accept valid options."""
        settings_4bit = Settings(mlx_default_quantization="4bit")
        settings_8bit = Settings(mlx_default_quantization="8bit")
        settings_none = Settings(mlx_default_quantization="none")

        assert settings_4bit.mlx_default_quantization == "4bit"
        assert settings_8bit.mlx_default_quantization == "8bit"
        assert settings_none.mlx_default_quantization == "none"

"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "MLX Model Hub"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://mlxhub:mlxhub@localhost:5432/mlxhub"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5001"

    # Storage - use absolute paths for production, relative for development
    storage_base_path: Path = Path("./storage")
    storage_models_path: Path = Path("./storage/models")
    storage_datasets_path: Path = Path("./storage/datasets")

    # MLX
    mlx_memory_limit_gb: int = 36
    mlx_default_quantization: Literal["4bit", "8bit", "none"] = "4bit"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    # Observability
    otlp_endpoint: str | None = None  # Optional OTLP endpoint for tracing

    def ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
        self.storage_models_path.mkdir(parents=True, exist_ok=True)
        self.storage_datasets_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings

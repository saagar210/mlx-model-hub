"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
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

    # Security - API Key Authentication
    api_key: str | None = None  # Set via MLX_HUB_API_KEY env var
    api_key_header: str = "X-API-Key"
    require_auth: bool = False  # Set to True in production

    # CORS - allowed origins (comma-separated in env)
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]

    # Rate Limiting
    rate_limit_requests: int = 100  # requests per minute
    rate_limit_burst: int = 20  # burst allowance

    # Database
    database_url: str = "postgresql+asyncpg://mlxhub:mlxhub@localhost:5432/mlxhub"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5001"

    # Inference Server (unified-mlx-app)
    inference_server_url: str = "http://localhost:8080"
    inference_auto_register: bool = True

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

    @field_validator("api_key", mode="before")
    @classmethod
    def generate_api_key_if_needed(cls, v: str | None) -> str | None:
        """Generate a secure API key if not provided and auth is required."""
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse comma-separated CORS origins from env."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    def ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
        self.storage_models_path.mkdir(parents=True, exist_ok=True)
        self.storage_datasets_path.mkdir(parents=True, exist_ok=True)

    def validate_production_settings(self) -> list[str]:
        """Validate settings for production readiness.

        Returns a list of warnings/errors.
        """
        warnings = []

        if self.debug:
            warnings.append("DEBUG mode is enabled - disable for production")

        if self.require_auth and not self.api_key:
            warnings.append(
                "AUTH required but no API_KEY set - generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        if "localhost" in self.database_url or "127.0.0.1" in self.database_url:
            warnings.append("Database URL points to localhost - use production database")

        if "*" in self.cors_origins:
            warnings.append("CORS allows all origins - restrict for production")

        return warnings


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings

"""Base configuration classes for KAS ecosystem.

Provides mixin classes for common configuration patterns that can be
inherited by both KAS and LocalCrew settings classes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseMixin(BaseSettings):
    """Mixin for database connection settings.

    Provides standard PostgreSQL connection pool configuration.
    Can be used with different database URLs per application.
    """

    database_url: str = "postgresql://user:pass@localhost:5432/db"
    db_pool_min: int = 2
    db_pool_max: int = 10
    db_command_timeout: float = 60.0


class LoggingMixin(BaseSettings):
    """Mixin for logging configuration.

    Provides standard log level setting used across applications.
    """

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False  # Use JSON format (for production)
    log_correlation_id: bool = True  # Add correlation IDs to logs


class OllamaMixin(BaseSettings):
    """Mixin for Ollama LLM service configuration.

    Shared settings for connecting to Ollama for embeddings and inference.
    """

    ollama_url: str = "http://localhost:11434"
    ollama_timeout: float = 30.0


class SecurityMixin(BaseSettings):
    """Mixin for API security settings.

    Provides common security configuration for rate limiting and API keys.
    """

    api_key: str = ""  # Optional API key for external access
    api_key_header: str = "X-API-Key"
    rate_limit_requests: int = 100  # Requests per minute
    rate_limit_window: int = 60  # Window in seconds
    require_api_key: bool = False  # Set to True for production

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate API key to prevent header injection."""
        if not v:
            return v
        cleaned = v.strip()
        if any(char in cleaned for char in ["\n", "\r", "\0"]):
            raise ValueError("API key contains invalid characters")
        return cleaned


class BaseAppSettings(DatabaseMixin, LoggingMixin, SecurityMixin):
    """Base settings class combining common mixins.

    Applications should inherit from this and add their own settings.
    The model_config should be overridden to set the appropriate env_prefix.

    Example:
        class KASSettings(BaseAppSettings):
            model_config = SettingsConfigDict(
                env_prefix="KNOWLEDGE_",
                env_file=".env",
            )
            # KAS-specific settings...
            vault_path: str = "~/Obsidian"
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application metadata
    app_name: str = "App"
    app_version: str = "0.1.0"
    debug: bool = False

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000


class KASIntegrationMixin(BaseSettings):
    """Mixin for KAS integration settings.

    Use this in applications that need to connect to KAS.
    """

    kas_enabled: bool = False
    kas_base_url: str = "http://localhost:8000"
    kas_api_key: str | None = None
    kas_timeout: float = 10.0

    @field_validator("kas_api_key")
    @classmethod
    def validate_kas_api_key(cls, v: str | None) -> str | None:
        """Validate KAS API key to prevent header injection."""
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        if any(char in cleaned for char in ["\n", "\r", "\0"]):
            raise ValueError("KAS API key contains invalid characters")
        return cleaned

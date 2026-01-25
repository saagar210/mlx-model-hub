"""Configuration settings for Knowledge Seeder."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Knowledge Seeder configuration."""

    model_config = SettingsConfigDict(
        env_prefix="SEEDER_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Knowledge Engine API (for when it's ready)
    api_base_url: str = Field(
        default="http://localhost:8000",
        description="Knowledge Engine API base URL",
    )
    api_timeout: float = Field(
        default=120.0,
        description="API request timeout in seconds",
    )

    # State database
    state_db_path: Path = Field(
        default=Path("~/.knowledge-seeder/state.db").expanduser(),
        description="Path to SQLite state database",
    )

    # Rate limiting
    rate_limit_requests: int = Field(
        default=30,
        description="Maximum requests per minute",
    )
    rate_limit_delay: float = Field(
        default=2.0,
        description="Delay between requests in seconds",
    )

    # Extraction settings
    extraction_timeout: float = Field(
        default=30.0,
        description="Content extraction timeout in seconds",
    )
    max_content_length: int = Field(
        default=500_000,
        description="Maximum content length in characters",
    )
    min_content_length: int = Field(
        default=100,
        description="Minimum content length for valid extraction",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed operations",
    )
    retry_delay: float = Field(
        default=5.0,
        description="Initial delay between retries in seconds",
    )

    # User agent for HTTP requests
    user_agent: str = Field(
        default="KnowledgeSeeder/0.1.0 (+https://github.com/knowledge-seeder)",
        description="User agent string for HTTP requests",
    )

    def ensure_state_dir(self) -> None:
        """Ensure the state database directory exists."""
        self.state_db_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_state_dir()
    return settings

"""Configuration management using Pydantic Settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Obsidian
    obsidian_vault: Path = Path.home() / "Obsidian"

    # Git
    git_repos: Path = Path.home() / "claude-code"

    # KAS (Knowledge Activation System)
    kas_api_url: str = "http://localhost:8000"

    # Vector store
    qdrant_url: str = "http://localhost:6333"

    # Embeddings
    embedding_model: str = "nomic-embed-text"


def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

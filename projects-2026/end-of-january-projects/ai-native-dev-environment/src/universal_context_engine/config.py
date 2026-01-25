"""Configuration settings for Universal Context Engine."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Data storage
    uce_data_dir: Path = Path.home() / ".local" / "share" / "universal-context"

    # Ollama configuration
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_chat_model: str = "qwen2.5:14b"

    # Redis configuration
    redis_url: str = "redis://localhost:6379"

    # KAS API
    kas_base_url: str = "http://localhost:8000"

    # LocalCrew API
    localcrew_base_url: str = "http://localhost:8001"

    # ChromaDB settings
    chroma_collection_prefix: str = "uce"

    # Embedding settings
    embedding_dimension: int = 768  # nomic-embed-text dimension

    @property
    def chromadb_path(self) -> Path:
        """Path to ChromaDB persistent storage."""
        return self.uce_data_dir / "chromadb"

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        self.uce_data_dir.mkdir(parents=True, exist_ok=True)
        self.chromadb_path.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

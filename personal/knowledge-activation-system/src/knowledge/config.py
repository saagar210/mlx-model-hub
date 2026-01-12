"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://knowledge:localdev@localhost:5432/knowledge"
    db_pool_min: int = 2
    db_pool_max: int = 10
    db_command_timeout: float = 60.0

    # Ollama
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    rerank_model: str = "mxbai-rerank-base-v1"
    ollama_timeout: float = 30.0
    embedding_max_concurrent: int = 5  # Max concurrent embedding requests

    # OpenRouter (Phase 3)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    primary_model: str = "deepseek/deepseek-chat"
    fallback_model: str = "anthropic/claude-3.5-sonnet"
    llm_timeout: float = 60.0  # Overall timeout for LLM generation

    # Obsidian
    vault_path: str = "~/Obsidian"
    knowledge_folder: str = "Knowledge"

    # Search
    rrf_k: int = 60
    search_limit: int = 10
    bm25_candidates: int = 50
    vector_candidates: int = 50

    # Confidence thresholds
    confidence_low: float = 0.3
    confidence_high: float = 0.7

    # API Security
    api_key: str = ""  # Optional API key for external access
    api_key_header: str = "X-API-Key"
    rate_limit_requests: int = 100  # Requests per minute
    rate_limit_window: int = 60  # Window in seconds
    require_api_key: bool = False  # Set to True for production

    # Daily Review Scheduler
    review_enabled: bool = True  # Enable daily review reminders
    review_time_hour: int = 9  # Hour for daily review (0-23)
    review_time_minute: int = 0  # Minute for daily review (0-59)
    review_timezone: str = "America/Los_Angeles"  # Timezone for scheduling

    @property
    def vault_dir(self) -> Path:
        """Expanded vault path."""
        return Path(self.vault_path).expanduser()

    @property
    def knowledge_dir(self) -> Path:
        """Full path to knowledge folder within vault."""
        return self.vault_dir / self.knowledge_folder


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

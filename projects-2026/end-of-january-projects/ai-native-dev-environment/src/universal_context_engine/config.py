"""Configuration settings for Universal Context Engine."""

import re
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# Patterns that may indicate sensitive data (case-insensitive matching)
# Uses word boundaries (\b) to avoid false positives like "authentication"
SENSITIVE_PATTERNS = [
    r"\b(api[_-]?key|apikey)\b",
    r"\b(secret|password|passwd|pwd)\b",
    r"\bbearer\s+[a-zA-Z0-9_\-\.]{20,}",  # Bearer token (must be 20+ alphanumeric chars)
    r"\bauth[_-]?token\b",  # auth_token specifically
    r"\b(private[_-]?key)\b",
    r"\bcredentials?\s*[=:]",  # credentials = or credentials:
    r"\b(aws[_-]?access)\b",
    r"\b(database[_-]?url|db[_-]?url)\b",
    r"sk-[a-zA-Z0-9]{32,}",  # OpenAI API keys
    r"ghp_[a-zA-Z0-9]{36,}",  # GitHub tokens
    r"ghr_[a-zA-Z0-9]{36,}",  # GitHub refresh tokens
]

# Compiled regex for performance (case-insensitive)
_sensitive_regex = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)


def contains_sensitive_data(content: str) -> bool:
    """Check if content contains potentially sensitive data patterns.

    Args:
        content: The content to check.

    Returns:
        True if sensitive patterns detected, False otherwise.
    """
    return bool(_sensitive_regex.search(content))


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

    # Dashboard settings
    dashboard_host: str = "127.0.0.1"  # Bind to localhost only for security
    dashboard_port: int = 8002
    cors_allowed_origins: list[str] = ["http://localhost:8002", "http://127.0.0.1:8002"]

    # ChromaDB settings
    chroma_collection_prefix: str = "uce"

    # Embedding settings
    embedding_dimension: int = 768  # nomic-embed-text dimension

    # Production mode (disables destructive operations like reset)
    production_mode: bool = False

    # Data retention settings (in days, 0 = no retention)
    context_retention_days: int = 90  # Keep context items for 90 days
    feedback_retention_days: int = 180  # Keep feedback for 180 days
    session_retention_days: int = 30  # Keep session data for 30 days

    # Data hygiene
    warn_on_sensitive_data: bool = True  # Warn when saving potentially sensitive content
    max_content_length: int = 50000  # Max characters per content item

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

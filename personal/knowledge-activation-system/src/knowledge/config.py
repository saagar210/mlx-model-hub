"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # =========================================================================
    # Database (P12: Connection Pool Management)
    # =========================================================================
    database_url: str = "postgresql://knowledge:localdev@localhost:5432/knowledge"
    db_pool_min: int = 2
    db_pool_max: int = 10
    db_pool_max_inactive_time: float = 300.0  # 5 minutes - idle connection cleanup
    db_pool_timeout: float = 30.0  # Connection acquire timeout
    db_command_timeout: float = 60.0  # Query execution timeout
    db_retry_attempts: int = 3  # Number of retry attempts on connection failure
    db_retry_delay: float = 1.0  # Base delay between retries (exponential backoff)
    db_health_check_interval: float = 30.0  # Health check interval in seconds

    # =========================================================================
    # Ollama / Embeddings
    # =========================================================================
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    rerank_model: str = "mxbai-rerank-base-v1"
    ollama_timeout: float = 30.0
    embedding_max_concurrent: int = 5  # Max concurrent embedding requests
    embedding_batch_size: int = 10  # Batch size for embedding generation
    embedding_max_retries: int = 3  # Retry attempts for embedding failures

    # =========================================================================
    # OpenRouter / LLM
    # =========================================================================
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    primary_model: str = "deepseek/deepseek-chat"
    fallback_model: str = "anthropic/claude-3.5-sonnet"
    llm_timeout: float = 60.0  # Overall timeout for LLM generation

    # =========================================================================
    # Obsidian
    # =========================================================================
    vault_path: str = "~/Obsidian"
    knowledge_folder: str = "Knowledge"

    # =========================================================================
    # Search (P13: Configuration Externalization)
    # =========================================================================
    rrf_k: int = 60  # RRF fusion constant
    search_default_limit: int = 10  # Default search result limit
    search_max_limit: int = 100  # Maximum allowed search limit
    bm25_candidates: int = 50  # BM25 candidate pool size
    vector_candidates: int = 50  # Vector search candidate pool size

    # Confidence thresholds
    confidence_low: float = 0.3
    confidence_high: float = 0.7

    # =========================================================================
    # Chunking
    # =========================================================================
    chunk_size_default: int = 512  # Default chunk size in tokens
    chunk_overlap_default: int = 50  # Default chunk overlap
    chunk_size_youtube: int = 1000  # Chunk size for YouTube content
    chunk_size_bookmark: int = 500  # Chunk size for bookmark content

    # =========================================================================
    # Ingestion
    # =========================================================================
    ingest_batch_size: int = 50  # Batch size for bulk ingestion
    ingest_timeout: float = 120.0  # Timeout for ingestion operations
    url_fetch_timeout: float = 30.0  # Timeout for URL fetching
    max_content_size: int = 10 * 1024 * 1024  # 10MB max content size
    max_chunk_text_size: int = 10000  # Max characters per chunk
    max_tags_count: int = 50  # Maximum number of tags per content

    # =========================================================================
    # Review / FSRS
    # =========================================================================
    review_enabled: bool = True  # Enable daily review reminders
    review_time_hour: int = 9  # Hour for daily review (0-23)
    review_time_minute: int = 0  # Minute for daily review (0-59)
    review_timezone: str = "America/Los_Angeles"  # Timezone for scheduling
    review_cards_per_session: int = 20  # Cards per review session
    review_minimum_interval_hours: int = 4  # Minimum interval between reviews

    # =========================================================================
    # API Security (P17: Authentication)
    # =========================================================================
    api_key: str = ""  # Optional API key for external access
    api_key_header: str = "X-API-Key"
    require_api_key: bool = False  # Set to True for production

    # =========================================================================
    # Rate Limiting (P18)
    # =========================================================================
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100  # Requests per minute
    rate_limit_window: int = 60  # Window in seconds
    rate_limit_burst: int = 200  # Burst allowance

    # =========================================================================
    # API Configuration
    # =========================================================================
    api_request_timeout: float = 30.0  # Request timeout
    api_max_request_size: int = 10 * 1024 * 1024  # 10MB max request body
    api_version: str = "v1"  # Current API version

    # =========================================================================
    # Logging (P15: Logging Infrastructure)
    # =========================================================================
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"  # json for prod, console for dev
    log_include_request_id: bool = True

    # =========================================================================
    # Observability (P24-P25)
    # =========================================================================
    metrics_enabled: bool = True
    tracing_enabled: bool = False
    tracing_otlp_endpoint: str | None = None
    tracing_sample_rate: float = 1.0

    # =========================================================================
    # Circuit Breaker (P26)
    # =========================================================================
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 30.0
    circuit_breaker_half_open_max_calls: int = 3

    # =========================================================================
    # Redis Caching
    # =========================================================================
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True
    cache_ttl_search: int = 300  # 5 minutes for search results
    cache_ttl_embedding: int = 86400  # 24 hours for embeddings
    cache_ttl_rerank: int = 600  # 10 minutes for rerank results
    cache_max_size: int = 10000  # Max cached items per type

    # =========================================================================
    # Search Tuning
    # =========================================================================
    search_bm25_weight: float = 0.5  # Weight for BM25 in hybrid search
    search_vector_weight: float = 0.5  # Weight for vector in hybrid search
    search_enable_query_expansion: bool = True  # Enable synonym expansion

    # =========================================================================
    # Validation
    # =========================================================================
    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        """Validate setting combinations."""
        if self.db_pool_min > self.db_pool_max:
            raise ValueError("db_pool_min cannot exceed db_pool_max")
        if self.search_default_limit > self.search_max_limit:
            raise ValueError("search_default_limit cannot exceed search_max_limit")
        if self.db_retry_attempts < 1:
            raise ValueError("db_retry_attempts must be at least 1")
        if self.rate_limit_burst < self.rate_limit_requests:
            raise ValueError("rate_limit_burst should be >= rate_limit_requests")
        return self

    # =========================================================================
    # Properties
    # =========================================================================
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


def clear_settings_cache() -> None:
    """Clear the settings cache (useful for testing)."""
    get_settings.cache_clear()

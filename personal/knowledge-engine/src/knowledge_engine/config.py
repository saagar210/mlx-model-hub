"""Configuration management with Pydantic Settings.

Designed for cost-optimization: defaults to free local services (Ollama, self-hosted DBs).
Can be upgraded to paid services by changing environment variables.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class EmbeddingProvider(str, Enum):
    """Embedding provider options."""

    OLLAMA = "ollama"  # Free, local
    VOYAGE = "voyage"  # Paid, best quality


class LLMProvider(str, Enum):
    """LLM provider options."""

    OLLAMA = "ollama"  # Free, local
    ANTHROPIC = "anthropic"  # Paid, best quality
    OPENROUTER = "openrouter"  # Mixed free/paid tiers


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ============================================================
    # EMBEDDING CONFIGURATION (default: Ollama - FREE)
    # ============================================================
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OLLAMA

    # Ollama embeddings (FREE - default)
    ollama_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "nomic-embed-text"  # 768 dims, good quality
    ollama_embed_dimensions: int = 768

    # Voyage AI embeddings (PAID - upgrade path)
    voyage_api_key: SecretStr | None = None
    voyage_model: str = "voyage-3-large"
    voyage_dimensions: int = 1024
    voyage_batch_size: int = 128

    # ============================================================
    # RERANKING CONFIGURATION (default: Ollama - FREE)
    # ============================================================
    rerank_enabled: bool = True
    rerank_provider: Literal["ollama", "cohere", "none"] = "ollama"

    # Ollama reranking (FREE - default)
    ollama_rerank_model: str = "qllama/bge-reranker-v2-m3"

    # Cohere reranking (PAID - upgrade path)
    cohere_api_key: SecretStr | None = None
    cohere_rerank_model: str = "rerank-english-v3.5"
    cohere_rerank_top_n: int = 10

    # ============================================================
    # LLM CONFIGURATION (default: Ollama - FREE)
    # ============================================================
    llm_provider: LLMProvider = LLMProvider.OLLAMA

    # Ollama LLM (FREE - default)
    ollama_llm_model: str = "llama3.2"  # or mistral, etc.

    # Anthropic LLM (PAID - upgrade path)
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"  # Update to valid model ID when using
    anthropic_max_tokens: int = 4096

    # OpenRouter (MIXED - some free models)
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str = "deepseek/deepseek-chat"  # Very cheap

    # ============================================================
    # VECTOR DATABASE (default: self-hosted Qdrant - FREE)
    # ============================================================
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None  # Only for Qdrant Cloud
    qdrant_collection_prefix: str = "ke"

    # ============================================================
    # GRAPH DATABASE (default: disabled - FREE, enable for Neo4j)
    # ============================================================
    graph_enabled: bool = False  # Start without graph, add later
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("localdev")
    neo4j_database: str = "neo4j"
    neo4j_max_connection_pool_size: int = 50

    # ============================================================
    # METADATA STORE (PostgreSQL - FREE self-hosted)
    # ============================================================
    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://knowledge_engine:localdev@localhost:5432/knowledge_engine"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ============================================================
    # CACHE (Redis - FREE self-hosted, optional)
    # ============================================================
    redis_enabled: bool = False  # Optional, not required to start
    redis_url: str = "redis://localhost:6379/0"
    redis_ttl_seconds: int = 3600

    # ============================================================
    # SEARCH CONFIGURATION
    # ============================================================
    search_vector_candidates: int = 100
    search_graph_hops: int = 2
    search_bm25_candidates: int = 50
    search_rrf_k: int = 60
    search_default_limit: int = 10

    # ============================================================
    # SECURITY
    # ============================================================
    require_api_key: bool = False  # Disabled for local dev
    api_key_header: str = "X-API-Key"
    jwt_secret: SecretStr = SecretStr("change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ============================================================
    # OBSERVABILITY (optional)
    # ============================================================
    otlp_endpoint: str | None = None
    metrics_enabled: bool = False  # Disable by default for simplicity

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> Environment:
        """Convert string to Environment enum."""
        if isinstance(v, Environment):
            return v
        return Environment(v.lower())

    def validate_production_security(self) -> list[str]:
        """
        Validate security settings for production deployment.

        Returns a list of warnings. Should be called during app startup.
        """
        warnings = []

        if self.is_production:
            # Check JWT secret
            if self.jwt_secret.get_secret_value() == "change-me-in-production":
                warnings.append(
                    "CRITICAL: JWT_SECRET must be changed from default for production!"
                )

            # Check Neo4j password if graph is enabled
            if self.graph_enabled:
                if self.neo4j_password.get_secret_value() == "localdev":
                    warnings.append(
                        "WARNING: NEO4J_PASSWORD should be changed from default for production"
                    )

            # Check database URL for default password
            if "localdev" in self.database_url.get_secret_value():
                warnings.append(
                    "WARNING: DATABASE_URL contains default password - change for production"
                )

        return warnings

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment == Environment.DEVELOPMENT

    @property
    def embedding_dimensions(self) -> int:
        """Get embedding dimensions based on provider."""
        if self.embedding_provider == EmbeddingProvider.OLLAMA:
            return self.ollama_embed_dimensions
        return self.voyage_dimensions


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

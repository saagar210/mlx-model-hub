"""
SIA Configuration Management

Uses Pydantic Settings for type-safe configuration with environment variable support.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_DATABASE_")

    url: str = Field(
        default="postgresql://sia:sia_dev_password@localhost:5432/sia",
        description="PostgreSQL connection URL",
    )
    pool_size: int = Field(default=10, ge=1, le=100)
    pool_max_overflow: int = Field(default=20, ge=0, le=100)
    echo: bool = Field(default=False, description="Echo SQL statements")


class OllamaConfig(BaseSettings):
    """Ollama LLM configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_OLLAMA_")

    base_url: str = Field(default="http://localhost:11434")
    model: str = Field(default="qwen2.5:7b")
    timeout: int = Field(default=120, description="Request timeout in seconds")


class EmbeddingConfig(BaseSettings):
    """Embedding model configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_EMBEDDING_")

    model: str = Field(default="nomic-embed-text:v1.5")
    dimensions: int = Field(default=768)


class RerankConfig(BaseSettings):
    """Reranking model configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_RERANK_")

    model: str = Field(default="mxbai-rerank-large-v2")


class CloudLLMConfig(BaseSettings):
    """Cloud LLM fallback configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_")

    # OpenRouter
    openrouter_api_key: str | None = Field(default=None)
    openrouter_model: str = Field(default="qwen/qwen-2.5-7b-instruct:free")

    # DeepSeek
    deepseek_api_key: str | None = Field(default=None)
    deepseek_model: str = Field(default="deepseek-chat")

    # Anthropic
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-3-haiku-20240307")

    # LLM Gateway (AI Command Center)
    llm_gateway_url: str = Field(default="http://localhost:4000/v1")
    use_llm_gateway: bool = Field(default=False)


class APIConfig(BaseSettings):
    """API server configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_API_")

    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8080, ge=1, le=65535)
    reload: bool = Field(default=True)
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v


class ObservabilityConfig(BaseSettings):
    """Observability configuration (Langfuse, logging)."""

    model_config = SettingsConfigDict(env_prefix="SIA_")

    # Langfuse
    langfuse_public_key: str | None = Field(default=None)
    langfuse_secret_key: str | None = Field(default=None)
    langfuse_host: str = Field(default="http://localhost:3001")

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


class ExecutionConfig(BaseSettings):
    """Execution limits and defaults."""

    model_config = SettingsConfigDict(env_prefix="SIA_")

    max_execution_time_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=3, ge=0)
    default_temperature: float = Field(default=0.7, ge=0, le=2)
    default_max_tokens: int = Field(default=4096, ge=1)


class SandboxConfig(BaseSettings):
    """Sandbox configuration for code evolution."""

    model_config = SettingsConfigDict(env_prefix="SIA_SANDBOX_")

    enabled: bool = Field(default=True)
    timeout_seconds: int = Field(default=60, ge=1)
    memory_mb: int = Field(default=512, ge=64)


class DSPyConfig(BaseSettings):
    """DSPy optimization configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_DSPY_")

    trials: int = Field(default=20, ge=1)
    min_improvement: float = Field(default=0.1, ge=0, le=1)


class AutoImproveConfig(BaseSettings):
    """Auto-improvement configuration."""

    model_config = SettingsConfigDict(env_prefix="SIA_AUTO_IMPROVE_")

    success_threshold: float = Field(default=0.8, ge=0, le=1)
    min_samples: int = Field(default=50, ge=1)


class SIAConfig(BaseSettings):
    """
    Main configuration class that aggregates all sub-configurations.

    Usage:
        config = get_config()
        print(config.database.url)
        print(config.ollama.model)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sub-configurations
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    cloud_llm: CloudLLMConfig = Field(default_factory=CloudLLMConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    dspy: DSPyConfig = Field(default_factory=DSPyConfig)
    auto_improve: AutoImproveConfig = Field(default_factory=AutoImproveConfig)


@lru_cache
def get_config() -> SIAConfig:
    """
    Get the cached configuration instance.

    Returns:
        SIAConfig: The application configuration.
    """
    return SIAConfig()


def reload_config() -> SIAConfig:
    """
    Reload configuration (clears cache and returns fresh config).

    Returns:
        SIAConfig: Fresh configuration instance.
    """
    get_config.cache_clear()
    return get_config()

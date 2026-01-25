"""UCE configuration settings."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "Universal Context Engine"
    app_version: str = "0.1.0"
    debug: bool = False

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://uce:uce@localhost:5434/universal_context"
    db_pool_size: int = 10
    db_pool_max_overflow: int = 5

    # Neo4j (optional, for full graph features)
    neo4j_uri: str | None = Field(default="bolt://localhost:7687")
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None

    # Ollama
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768
    rerank_model: str = "mxbai-rerank-large-v2"

    # Search
    search_default_limit: int = 20
    search_rrf_k: int = 60
    search_decay_half_life_hours: int = 168  # 1 week

    # Source databases
    kas_db_url: str = "postgresql://knowledge:localdev@localhost:5433/knowledge"
    kas_api_url: str = "http://localhost:8000"
    localcrew_db_url: str = "postgresql://localcrew:localcrew@localhost:5433/localcrew"

    # Git
    git_repo_paths: list[str] = Field(
        default_factory=lambda: [
            "~/claude-code/projects-2026",
            "~/claude-code/personal",
        ]
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8100

    # Sync
    sync_interval_seconds: int = 300  # 5 minutes default
    sync_enabled: bool = True

    model_config = {
        "env_prefix": "UCE_",
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()

"""Tests for configuration management."""

import pytest

from knowledge_engine.config import (
    EmbeddingProvider,
    Environment,
    LLMProvider,
    Settings,
    get_settings,
)


def test_default_settings():
    """Test default settings are FREE tier."""
    settings = Settings()

    # FREE tier defaults
    assert settings.environment == Environment.DEVELOPMENT
    assert settings.embedding_provider == EmbeddingProvider.OLLAMA
    assert settings.llm_provider == LLMProvider.OLLAMA
    assert settings.rerank_provider == "ollama"
    assert settings.graph_enabled is False
    assert settings.redis_enabled is False


def test_ollama_defaults():
    """Test Ollama model defaults."""
    settings = Settings()

    assert settings.ollama_embed_model == "nomic-embed-text"
    assert settings.ollama_embed_dimensions == 768
    assert settings.ollama_rerank_model == "qllama/bge-reranker-v2-m3"
    assert settings.ollama_llm_model == "llama3.2"


def test_embedding_dimensions():
    """Test embedding dimensions based on provider."""
    # Ollama provider (default)
    settings = Settings(embedding_provider="ollama")
    assert settings.embedding_dimensions == 768

    # Voyage provider
    settings = Settings(embedding_provider="voyage")
    assert settings.embedding_dimensions == 1024


def test_environment_parsing():
    """Test environment enum parsing."""
    settings = Settings(environment="production")
    assert settings.environment == Environment.PRODUCTION
    assert settings.is_production is True
    assert settings.is_development is False

    settings = Settings(environment="development")
    assert settings.is_development is True


def test_get_settings_cached():
    """Test settings are cached."""
    get_settings.cache_clear()  # Clear cache for test
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_free_tier_no_api_keys():
    """Test FREE tier works without API keys."""
    settings = Settings()

    # Should not raise, API keys are optional in FREE tier
    assert settings.voyage_api_key is None
    assert settings.cohere_api_key is None
    assert settings.anthropic_api_key is None

"""Tests for configuration module."""

import pytest

from sia.config import (
    SIAConfig,
    DatabaseConfig,
    OllamaConfig,
    get_config,
    reload_config,
)


def test_database_config_defaults():
    """Test database configuration defaults."""
    config = DatabaseConfig()
    assert "postgresql" in config.url
    assert config.pool_size == 10
    assert config.pool_max_overflow == 20


def test_ollama_config_defaults():
    """Test Ollama configuration defaults."""
    config = OllamaConfig()
    assert config.base_url == "http://localhost:11434"
    assert "qwen" in config.model.lower()


def test_sia_config_loads():
    """Test that main config loads successfully."""
    config = SIAConfig()
    assert config.database is not None
    assert config.ollama is not None
    assert config.api is not None


def test_get_config_cached():
    """Test that get_config returns cached instance."""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2


def test_reload_config():
    """Test that reload_config returns fresh instance."""
    config1 = get_config()
    config2 = reload_config()
    # They should be equal but not the same instance
    assert config1 == config2

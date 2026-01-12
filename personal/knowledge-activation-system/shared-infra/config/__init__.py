"""Shared configuration module for KAS ecosystem.

This module provides a common base for settings across KAS and LocalCrew,
reducing duplication while allowing project-specific overrides.

Usage in KAS:
    from shared_infra.config import BaseAppSettings

    class Settings(BaseAppSettings):
        model_config = SettingsConfigDict(env_prefix="KNOWLEDGE_")
        # KAS-specific settings...

Usage in LocalCrew:
    from shared_infra.config import BaseAppSettings

    class Settings(BaseAppSettings):
        # LocalCrew-specific settings (no prefix)
        mlx_model_id: str = "..."
"""

from shared_infra.config.base import (
    BaseAppSettings,
    DatabaseMixin,
    LoggingMixin,
    OllamaMixin,
    SecurityMixin,
)

__all__ = [
    "BaseAppSettings",
    "DatabaseMixin",
    "LoggingMixin",
    "OllamaMixin",
    "SecurityMixin",
]

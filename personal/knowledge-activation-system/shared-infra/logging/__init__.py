"""Unified logging configuration for KAS ecosystem.

Provides consistent structured logging across all applications using structlog.
Features:
- Correlation IDs for cross-service tracing
- JSON output for production, rich console for development
- Context preservation across async operations

Usage:
    from shared_infra.logging import configure_logging, get_logger

    # Configure once at startup
    configure_logging(log_level="INFO", json_output=False)

    # Get logger in modules
    logger = get_logger(__name__)
    logger.info("message", key="value")

    # Add correlation ID for request tracing
    from shared_infra.logging import bind_correlation_id
    bind_correlation_id("req-123")
"""

from shared_infra.logging.config import (
    bind_correlation_id,
    clear_context,
    configure_logging,
    get_correlation_id,
    get_logger,
)

__all__ = [
    "bind_correlation_id",
    "clear_context",
    "configure_logging",
    "get_correlation_id",
    "get_logger",
]

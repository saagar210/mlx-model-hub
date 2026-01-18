"""Structured logging infrastructure for KAS (P15: Logging Infrastructure)."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import Processor

# Context variable for request ID tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get current request ID from context."""
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set request ID in context."""
    request_id_var.set(request_id)


def clear_request_id() -> None:
    """Clear request ID from context."""
    request_id_var.set(None)


def add_request_id(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add request ID to log event if available."""
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def configure_logging(
    level: str = "INFO",
    log_format: str = "json",
    include_request_id: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ("json" or "console")
        include_request_id: Whether to include request ID in logs
    """
    # Convert level string to logging level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors for all log entries
    shared_processors: list[Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Add request ID processor if enabled
    if include_request_id:
        shared_processors.insert(0, add_request_id)  # type: ignore[arg-type]

    # Add contextvars processor for bound context
    shared_processors.insert(0, structlog.contextvars.merge_contextvars)

    if log_format == "json":
        # JSON output for production
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        # Pretty console output for development
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Bound logger instance
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to the current logging context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Remove keys from the current logging context."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


class LoggingContext:
    """Context manager for temporary logging context."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self._token: Any = None

    def __enter__(self) -> LoggingContext:
        bind_context(**self.kwargs)
        return self

    def __exit__(self, *args: Any) -> None:
        unbind_context(*self.kwargs.keys())


# Convenience functions for common log patterns
def log_operation_start(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    **kwargs: Any,
) -> None:
    """Log the start of an operation."""
    logger.info(f"{operation}_started", operation=operation, **kwargs)


def log_operation_success(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """Log successful completion of an operation."""
    extra = {"operation": operation, **kwargs}
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    logger.info(f"{operation}_completed", **extra)


def log_operation_failure(
    logger: structlog.stdlib.BoundLogger,
    operation: str,
    error: Exception,
    duration_ms: float | None = None,
    **kwargs: Any,
) -> None:
    """Log failure of an operation."""
    extra = {
        "operation": operation,
        "error_type": type(error).__name__,
        "error_message": str(error),
        **kwargs,
    }
    if duration_ms is not None:
        extra["duration_ms"] = round(duration_ms, 2)
    logger.error(f"{operation}_failed", **extra, exc_info=True)

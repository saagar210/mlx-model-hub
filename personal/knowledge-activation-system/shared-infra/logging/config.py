"""Structlog configuration for unified logging.

Provides consistent structured logging with:
- Correlation IDs for distributed tracing
- JSON or rich console output
- Async-safe context variables
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable for correlation ID (async-safe)
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    """Get the current correlation ID."""
    return _correlation_id.get()


def bind_correlation_id(correlation_id: str | None = None) -> str:
    """
    Bind a correlation ID to the current context.

    Args:
        correlation_id: ID to use, or None to generate a new one

    Returns:
        The correlation ID that was bound
    """
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())[:8]
    _correlation_id.set(correlation_id)
    return correlation_id


def clear_context() -> None:
    """Clear the correlation ID context."""
    _correlation_id.set(None)


def add_correlation_id(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Processor to add correlation ID to log events."""
    correlation_id = get_correlation_id()
    if correlation_id:
        event_dict["correlation_id"] = correlation_id
    return event_dict


def add_app_context(app_name: str) -> structlog.types.Processor:
    """Create processor to add app name to log events."""

    def processor(
        logger: structlog.types.WrappedLogger,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        event_dict["app"] = app_name
        return event_dict

    return processor


def configure_logging(
    log_level: str = "INFO",
    json_output: bool = False,
    app_name: str = "app",
) -> None:
    """
    Configure structlog for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        json_output: Use JSON format (True for prod, False for dev)
        app_name: Application name to include in logs
    """
    # Shared processors
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_id,
        add_app_context(app_name),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Rich console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Middleware helper for FastAPI
class CorrelationIdMiddleware:
    """
    FastAPI middleware to manage correlation IDs.

    Automatically binds correlation ID from request header or generates new one.

    Usage:
        from fastapi import FastAPI
        from shared_infra.logging import CorrelationIdMiddleware

        app = FastAPI()
        app.add_middleware(CorrelationIdMiddleware, header_name="X-Correlation-ID")
    """

    def __init__(
        self,
        app: Any,
        header_name: str = "X-Correlation-ID",
    ) -> None:
        self.app = app
        self.header_name = header_name

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get or generate correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = headers.get(
            self.header_name.lower().encode(),
            None,
        )

        if correlation_id:
            correlation_id = correlation_id.decode()
        else:
            correlation_id = bind_correlation_id()

        # Bind to context
        bind_correlation_id(correlation_id)

        # Add to response headers
        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append(
                    (self.header_name.encode(), correlation_id.encode())
                )
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            clear_context()

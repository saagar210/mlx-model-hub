"""Structured logging for Universal Context Engine."""

import logging
import sys
from datetime import UTC, datetime
from functools import wraps
from typing import Any, Callable

# Configure structured logger
logger = logging.getLogger("uce")
logger.setLevel(logging.INFO)

# Console handler with structured format
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(
    logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
logger.addHandler(handler)


def log_exception(
    component: str,
    operation: str,
    error: Exception,
    context: dict[str, Any] | None = None,
) -> None:
    """Log an exception with structured context.

    Args:
        component: Component name (e.g., "context_store", "adapter")
        operation: Operation that failed (e.g., "search", "save")
        error: The exception
        context: Additional context for debugging
    """
    logger.error(
        f"{component}.{operation} failed: {type(error).__name__}: {error}",
        extra={
            "component": component,
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


def log_operation(
    component: str,
    operation: str,
    success: bool,
    latency_ms: float,
    context: dict[str, Any] | None = None,
) -> None:
    """Log an operation completion.

    Args:
        component: Component name
        operation: Operation name
        success: Whether it succeeded
        latency_ms: Execution time in milliseconds
        context: Additional context
    """
    level = logging.INFO if success else logging.WARNING
    status = "succeeded" if success else "failed"
    logger.log(
        level,
        f"{component}.{operation} {status} in {latency_ms:.1f}ms",
        extra={
            "component": component,
            "operation": operation,
            "success": success,
            "latency_ms": latency_ms,
            "context": context or {},
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


class ToolError(Exception):
    """Structured error for MCP tools."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


def create_error_response(
    error: Exception,
    tool_name: str,
) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        error: The exception
        tool_name: Name of the tool that failed

    Returns:
        Structured error response dict
    """
    if isinstance(error, ToolError):
        return {
            "success": False,
            "error": {
                "code": error.error_code,
                "message": error.message,
                "tool": tool_name,
                "details": error.details,
            },
        }

    # Map common exceptions to error codes
    error_code = "INTERNAL_ERROR"
    if "connection" in str(error).lower() or "connect" in type(error).__name__.lower():
        error_code = "SERVICE_UNAVAILABLE"
    elif "timeout" in str(error).lower():
        error_code = "TIMEOUT"
    elif "not found" in str(error).lower():
        error_code = "NOT_FOUND"
    elif isinstance(error, ValueError):
        error_code = "INVALID_INPUT"

    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": str(error),
            "tool": tool_name,
            "type": type(error).__name__,
        },
    }


def with_error_boundary(tool_name: str) -> Callable:
    """Decorator to add error boundary to MCP tools.

    Catches all exceptions and returns structured error responses
    instead of raising unhandled exceptions.

    Args:
        tool_name: Name of the tool for error context

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> dict[str, Any]:
            import time
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000
                log_operation("tool", tool_name, success=True, latency_ms=latency_ms)
                return result
            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                log_exception("tool", tool_name, e, context={"args": str(args)[:200], "kwargs": str(kwargs)[:200]})
                log_operation("tool", tool_name, success=False, latency_ms=latency_ms)
                return create_error_response(e, tool_name)
        return wrapper
    return decorator

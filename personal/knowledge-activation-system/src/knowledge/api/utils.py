"""Shared utilities for API routes."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from fastapi import HTTPException

from knowledge.logging import get_logger
from knowledge.security import is_production, sanitize_error_message

P = ParamSpec("P")
T = TypeVar("T")


def handle_exceptions(operation_name: str) -> Callable[
    [Callable[P, Coroutine[Any, Any, T]]],
    Callable[P, Coroutine[Any, Any, T]],
]:
    """
    Decorator for consistent exception handling in API routes.

    Catches all exceptions except HTTPException, logs them, and returns
    a sanitized error response.

    Args:
        operation_name: Name for logging (e.g., "search", "content_create")

    Usage:
        @router.post("/search")
        @handle_exceptions("search")
        async def search(request: SearchRequest) -> SearchResponse:
            # Implementation without try/except
            ...
    """
    logger = get_logger(__name__)

    def decorator(
        func: Callable[P, Coroutine[Any, Any, T]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                # Re-raise HTTP exceptions as-is (they're already proper responses)
                raise
            except Exception as e:
                logger.exception(f"{operation_name}_failed")
                raise HTTPException(
                    status_code=500,
                    detail=sanitize_error_message(e, production=is_production()),
                ) from e

        # Preserve signature and globals for FastAPI dependency injection
        # FastAPI uses get_type_hints() which needs access to the original
        # function's namespace to resolve forward reference annotations
        wrapper.__signature__ = inspect.signature(func)  # type: ignore[attr-defined]
        wrapper.__globals__.update(func.__globals__)  # type: ignore[attr-defined]
        return wrapper

    return decorator

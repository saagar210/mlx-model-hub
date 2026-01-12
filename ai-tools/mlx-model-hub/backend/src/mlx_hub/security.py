"""Security middleware and utilities.

Provides API key authentication and rate limiting.
"""

import logging
import re
from typing import Callable

from fastapi import Request, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from mlx_hub.config import get_settings

logger = logging.getLogger(__name__)

# Rate limiter instance
limiter = Limiter(key_func=get_remote_address)

# API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/health",
    "/health/live",
    "/health/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}


def is_public_endpoint(path: str) -> bool:
    """Check if an endpoint is public (no auth required)."""
    # Exact matches
    if path in PUBLIC_ENDPOINTS:
        return True

    # Health endpoints
    if path.startswith("/health"):
        return True

    return False


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check API key for protected endpoints."""
        settings = get_settings()

        # Skip auth if not required
        if not settings.require_auth:
            return await call_next(request)

        # Skip auth for public endpoints
        if is_public_endpoint(request.url.path):
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get(settings.api_key_header)

        if not api_key:
            logger.warning(f"Missing API key for {request.url.path}")
            return Response(
                content='{"detail": "Missing API key"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        # Validate API key (constant-time comparison)
        import secrets

        if not settings.api_key or not secrets.compare_digest(api_key, settings.api_key):
            logger.warning(f"Invalid API key for {request.url.path}")
            return Response(
                content='{"detail": "Invalid API key"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
            )

        return await call_next(request)


def validate_model_id(model_id: str) -> bool:
    """Validate a HuggingFace model ID to prevent injection attacks.

    Valid model IDs follow the pattern: owner/model-name
    where owner and model-name contain only alphanumeric characters,
    hyphens, underscores, and periods.
    """
    if not model_id or len(model_id) > 256:
        return False

    # Must have exactly one slash
    if model_id.count("/") != 1:
        return False

    # Pattern: alphanumeric, hyphen, underscore, period
    pattern = r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$"
    return bool(re.match(pattern, model_id))


def validate_path_safety(path: str, allowed_base: str) -> bool:
    """Validate a path doesn't escape the allowed base directory.

    Prevents path traversal attacks.
    """
    from pathlib import Path

    try:
        # Resolve both paths to absolute
        base = Path(allowed_base).resolve()
        target = Path(path).resolve()

        # Check target is under base
        return str(target).startswith(str(base))
    except (ValueError, OSError):
        return False


def sanitize_output_path(output_dir: str | None, model_id: str) -> str | None:
    """Sanitize and validate an output directory path.

    Returns None if the path is invalid or unsafe.
    """
    from pathlib import Path

    settings = get_settings()

    if output_dir is None:
        return None

    # Convert to Path and resolve
    try:
        path = Path(output_dir).resolve()
    except (ValueError, OSError):
        return None

    # Must be under storage_models_path
    allowed_base = settings.storage_models_path.resolve()

    if not str(path).startswith(str(allowed_base)):
        logger.warning(f"Path traversal attempt blocked: {output_dir}")
        return None

    return str(path)

"""Security middleware for the API."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, Response
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from knowledge.config import get_settings


# Simple in-memory rate limiter (use Redis for production)
class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self) -> None:
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_id: str, max_requests: int, window_seconds: int) -> bool:
        """Check if request is allowed under rate limit."""
        now = time.time()
        window_start = now - window_seconds

        # Clean old requests
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id] if req_time > window_start
        ]

        # Check rate limit
        if len(self.requests[client_id]) >= max_requests:
            return False

        # Record this request
        self.requests[client_id].append(now)
        return True

    def get_remaining(self, client_id: str, max_requests: int, window_seconds: int) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        window_start = now - window_seconds
        current_requests = len(
            [req_time for req_time in self.requests[client_id] if req_time > window_start]
        )
        return max(0, max_requests - current_requests)


# Global rate limiter instance
rate_limiter = RateLimiter()

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for API key validation and rate limiting."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security checks."""
        settings = get_settings()

        # Get client identifier (IP or API key)
        client_ip = request.client.host if request.client else "unknown"
        api_key = request.headers.get(settings.api_key_header)

        # API key validation (if required)
        if settings.require_api_key:
            # Skip auth for health check and docs
            if request.url.path not in ["/", "/health", "/docs", "/openapi.json", "/redoc"]:
                if not api_key:
                    raise HTTPException(
                        status_code=401,
                        detail="API key required",
                        headers={"WWW-Authenticate": "ApiKey"},
                    )
                if api_key != settings.api_key:
                    raise HTTPException(
                        status_code=403,
                        detail="Invalid API key",
                    )

        # Use API key as client ID if provided, otherwise use IP
        client_id = api_key if api_key else client_ip

        # Rate limiting
        if not rate_limiter.is_allowed(
            client_id, settings.rate_limit_requests, settings.rate_limit_window
        ):
            remaining = rate_limiter.get_remaining(
                client_id, settings.rate_limit_requests, settings.rate_limit_window
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(settings.rate_limit_requests),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(settings.rate_limit_window),
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        remaining = rate_limiter.get_remaining(
            client_id, settings.rate_limit_requests, settings.rate_limit_window
        )
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(settings.rate_limit_window)

        return response


def verify_api_key(api_key: str | None = None) -> bool:
    """Dependency to verify API key if required."""
    settings = get_settings()

    if not settings.require_api_key:
        return True

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True

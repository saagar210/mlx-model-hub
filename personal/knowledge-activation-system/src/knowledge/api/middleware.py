"""API Middleware (P18: Rate Limiting, P19: API Versioning, P24: Metrics).

Provides:
- Token bucket rate limiting with burst support
- API key validation with timing attack prevention
- Request correlation IDs for distributed tracing
- Automatic cleanup for memory management
- API version headers (P19)
- Prometheus metrics collection (P24)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException, Request, Response
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

from knowledge.config import get_settings
from knowledge.exceptions import RateLimitError
from knowledge.logging import get_logger
from knowledge.security import secure_compare, set_request_id, clear_request_id

logger = get_logger(__name__)


# =============================================================================
# Token Bucket Rate Limiter (P18)
# =============================================================================


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    tokens: float
    last_refill: float
    rate_limit: int  # Custom rate limit for this bucket (per minute)


@dataclass
class RateLimitInfo:
    """Rate limit information for headers."""

    limit: int
    remaining: int
    reset: int  # Unix timestamp when tokens fully refill


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter with burst support.

    Uses the token bucket algorithm which allows for:
    - Smooth rate limiting over time
    - Burst capacity for legitimate traffic spikes
    - Per-client rate limits (e.g., per API key)

    For production with multiple instances, use Redis-backed rate limiting.
    """

    def __init__(
        self,
        requests_per_minute: int = 100,
        burst_size: int | None = None,
        max_clients: int = 10000,
        cleanup_interval: int = 300,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Default rate limit
            burst_size: Maximum burst capacity (default: requests_per_minute * 2)
            max_clients: Maximum clients to track before forced cleanup
            cleanup_interval: Seconds between cleanup runs
        """
        self.requests_per_minute = requests_per_minute
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.burst_size = burst_size or requests_per_minute * 2
        self.buckets: dict[str, TokenBucket] = {}
        self._max_clients = max_clients
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()
        self._lock = asyncio.Lock()

    def _get_or_create_bucket(
        self,
        client_id: str,
        rate_limit: int | None = None,
    ) -> TokenBucket:
        """Get or create a token bucket for a client."""
        if client_id not in self.buckets:
            custom_rate = rate_limit or self.requests_per_minute
            custom_burst = (rate_limit * 2) if rate_limit else self.burst_size
            self.buckets[client_id] = TokenBucket(
                tokens=float(custom_burst),
                last_refill=time.time(),
                rate_limit=custom_rate,
            )
        return self.buckets[client_id]

    async def acquire(
        self,
        client_id: str,
        rate_limit: int | None = None,
    ) -> tuple[bool, RateLimitInfo]:
        """
        Try to acquire a token for a request.

        Args:
            client_id: Client identifier (API key or IP)
            rate_limit: Optional custom rate limit for this client

        Returns:
            Tuple of (allowed, rate_limit_info)
        """
        async with self._lock:
            # Periodic cleanup
            self._maybe_cleanup()

            bucket = self._get_or_create_bucket(client_id, rate_limit)
            now = time.time()

            # Calculate tokens per second for this bucket
            effective_rate = bucket.rate_limit / 60.0
            effective_burst = bucket.rate_limit * 2

            # Refill tokens based on elapsed time
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                effective_burst,
                bucket.tokens + elapsed * effective_rate
            )
            bucket.last_refill = now

            # Calculate reset time (when tokens would be full)
            tokens_needed = effective_burst - bucket.tokens
            reset_seconds = tokens_needed / effective_rate if effective_rate > 0 else 0
            reset_time = int(now + reset_seconds)

            # Try to consume a token
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return True, RateLimitInfo(
                    limit=bucket.rate_limit,
                    remaining=int(bucket.tokens),
                    reset=reset_time,
                )
            else:
                # Calculate retry-after (time until 1 token available)
                retry_after = (1 - bucket.tokens) / effective_rate if effective_rate > 0 else 60
                return False, RateLimitInfo(
                    limit=bucket.rate_limit,
                    remaining=0,
                    reset=int(now + retry_after),
                )

    def get_info(self, client_id: str) -> RateLimitInfo | None:
        """Get current rate limit info for a client without consuming tokens."""
        if client_id not in self.buckets:
            return None

        bucket = self.buckets[client_id]
        now = time.time()

        # Calculate current tokens (with refill)
        effective_rate = bucket.rate_limit / 60.0
        effective_burst = bucket.rate_limit * 2
        elapsed = now - bucket.last_refill
        current_tokens = min(effective_burst, bucket.tokens + elapsed * effective_rate)

        # Calculate reset time
        tokens_needed = effective_burst - current_tokens
        reset_seconds = tokens_needed / effective_rate if effective_rate > 0 else 0

        return RateLimitInfo(
            limit=bucket.rate_limit,
            remaining=int(current_tokens),
            reset=int(now + reset_seconds),
        )

    def _maybe_cleanup(self) -> None:
        """Periodically clean up stale buckets."""
        now = time.time()

        needs_cleanup = (
            now - self._last_cleanup > self._cleanup_interval
            or len(self.buckets) > self._max_clients
        )

        if not needs_cleanup:
            return

        # Remove buckets that haven't been used recently (full tokens = idle)
        stale_clients = []
        for client_id, bucket in self.buckets.items():
            # Calculate current tokens
            effective_rate = bucket.rate_limit / 60.0
            effective_burst = bucket.rate_limit * 2
            elapsed = now - bucket.last_refill
            current_tokens = bucket.tokens + elapsed * effective_rate

            # If tokens are full and haven't been touched in cleanup interval
            if current_tokens >= effective_burst and elapsed > self._cleanup_interval:
                stale_clients.append(client_id)

        for client_id in stale_clients:
            del self.buckets[client_id]

        self._last_cleanup = now

        if stale_clients:
            logger.debug(
                "rate_limiter_cleanup",
                removed_clients=len(stale_clients),
                remaining_clients=len(self.buckets),
            )


# Global rate limiter instance
rate_limiter = TokenBucketRateLimiter()

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class SecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for API key validation and rate limiting."""

    # Paths to skip for rate limiting and auth
    SKIP_PATHS = {"/", "/health", "/ready", "/docs", "/openapi.json", "/redoc", "/api/v1/health"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through security checks."""
        settings = get_settings()

        # Set request correlation ID for distributed tracing
        incoming_request_id = request.headers.get("X-Request-ID")
        request_id = set_request_id(incoming_request_id)

        try:
            # Get client identifier (IP or API key)
            client_ip = request.client.host if request.client else "unknown"
            api_key = request.headers.get(settings.api_key_header)

            # Skip security checks for certain paths
            if request.url.path in self.SKIP_PATHS:
                response = await call_next(request)
                response.headers["X-Request-ID"] = request_id
                return response

            # API key validation (if required)
            if settings.require_api_key:
                if not api_key:
                    logger.warning(
                        "api_key_required",
                        path=request.url.path,
                        client_ip=client_ip,
                    )
                    raise HTTPException(
                        status_code=401,
                        detail="API key required",
                        headers={"WWW-Authenticate": "ApiKey"},
                    )
                # Use constant-time comparison to prevent timing attacks
                if not settings.api_key or not secure_compare(api_key, settings.api_key):
                    logger.warning(
                        "api_key_invalid",
                        path=request.url.path,
                        client_ip=client_ip,
                    )
                    raise HTTPException(
                        status_code=403,
                        detail="Invalid API key",
                    )

            # Use API key as client ID if provided, otherwise use IP
            client_id = api_key[:16] if api_key else client_ip

            # Rate limiting (if enabled)
            rate_info = None
            if settings.rate_limit_enabled:
                allowed, rate_info = await rate_limiter.acquire(
                    client_id,
                    rate_limit=settings.rate_limit_requests,
                )

                if not allowed:
                    retry_after = max(1, rate_info.reset - int(time.time()))
                    logger.warning(
                        "rate_limit_exceeded",
                        client_id=client_id[:8] + "..." if len(client_id) > 8 else client_id,
                        path=request.url.path,
                        retry_after=retry_after,
                    )
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded",
                        headers={
                            "X-RateLimit-Limit": str(rate_info.limit),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(rate_info.reset),
                            "Retry-After": str(retry_after),
                        },
                    )

            # Process request
            response = await call_next(request)

            # Add rate limit headers to response
            if rate_info:
                response.headers["X-RateLimit-Limit"] = str(rate_info.limit)
                response.headers["X-RateLimit-Remaining"] = str(rate_info.remaining)
                response.headers["X-RateLimit-Reset"] = str(rate_info.reset)

            response.headers["X-Request-ID"] = request_id
            return response

        finally:
            clear_request_id()


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

    # Use constant-time comparison to prevent timing attacks
    if not settings.api_key or not secure_compare(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


# =============================================================================
# Metrics Middleware (P24)
# =============================================================================


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting Prometheus metrics.

    Records:
    - Total request count by method, endpoint, status
    - Request duration by method, endpoint
    - Requests in progress gauge
    """

    # Skip paths for metrics (health checks are too noisy)
    SKIP_PATHS = {"/health/live", "/health/ready", "/metrics"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Record metrics for each request."""
        from knowledge.metrics import (
            http_request_duration_seconds,
            http_requests_in_progress,
            http_requests_total,
        )

        # Skip metrics collection for certain paths
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Normalize endpoint path (replace IDs with placeholders)
        endpoint = self._normalize_path(request.url.path)
        method = request.method

        # Track in-progress requests
        http_requests_in_progress.labels(method=method).inc()

        start_time = time.time()
        status_code = 500  # Default if exception

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            http_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status=str(status_code),
            ).inc()

            http_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            http_requests_in_progress.labels(method=method).dec()

    def _normalize_path(self, path: str) -> str:
        """
        Normalize path to reduce cardinality.

        Replaces:
        - UUIDs with {id}
        - Numbers with {id}
        """
        import re

        # Replace UUIDs
        path = re.sub(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            "{id}",
            path,
        )
        # Replace numeric IDs
        path = re.sub(r"/\d+(?=/|$)", "/{id}", path)
        return path


# =============================================================================
# API Version Middleware (P19)
# =============================================================================


class APIVersionMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API version headers and deprecation warnings.

    Adds X-API-Version header to all responses and supports
    future deprecation warnings for version transitions.
    """

    def __init__(self, app: Any, version: str = "v1") -> None:
        super().__init__(app)
        self.version = version

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add API version headers to response."""
        response = await call_next(request)

        # Add version header
        response.headers["X-API-Version"] = self.version

        # Add deprecation warning for old API paths (future use)
        path = request.url.path
        if path.startswith("/v0/") or path.startswith("/api/v0/"):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2027-01-01T00:00:00Z"
            response.headers["X-Deprecation-Notice"] = (
                "This API version is deprecated. Please migrate to /api/v1/."
            )

        return response

"""API middleware for production hardening."""

from __future__ import annotations

import logging
import time
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware for request timing and logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid4())[:8]
        request.state.request_id = request_id

        # Start timing
        start_time = time.time()

        # Get endpoint path (normalize path params)
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            logger.exception("[%s] Request failed: %s", request_id, e)
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time

            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=path,
                status_code=str(status_code)
            ).inc()

            REQUEST_LATENCY.labels(
                method=method,
                endpoint=path
            ).observe(duration)

            # Log request
            logger.info(
                "[%s] %s %s -> %s (%.3fs)",
                request_id,
                method,
                path,
                status_code,
                duration
            )

        # Add headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration:.3f}s"

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware."""

    def __init__(self, app: FastAPI, calls_per_minute: int = 60) -> None:
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.requests: dict[str, list[float]] = {}
        self.window = 60.0  # 1 minute window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client identifier (IP address or API key)
        client_id = request.client.host if request.client else "unknown"

        # Check rate limit
        now = time.time()
        if client_id not in self.requests:
            self.requests[client_id] = []

        # Clean old requests
        self.requests[client_id] = [
            ts for ts in self.requests[client_id]
            if now - ts < self.window
        ]

        # Check if rate limited
        if len(self.requests[client_id]) >= self.calls_per_minute:
            logger.warning("Rate limit exceeded for client: %s", client_id)
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"}
            )

        # Record request
        self.requests[client_id].append(now)

        return await call_next(request)


def add_production_middleware(app: FastAPI, rate_limit: bool = False) -> None:
    """Add production middleware to FastAPI app."""
    # Request timing should be added last (first in middleware stack)
    app.add_middleware(RequestTimingMiddleware)

    if rate_limit:
        app.add_middleware(RateLimitMiddleware, calls_per_minute=60)

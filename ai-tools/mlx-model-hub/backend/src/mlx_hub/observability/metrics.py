"""Prometheus metrics for MLX Model Hub."""

import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Application info
APP_INFO = Info("mlx_hub", "MLX Model Hub application information")
APP_INFO.info({
    "version": "0.1.0",
    "description": "Local-first MLX Model Hub for Apple Silicon",
})

# HTTP metrics (RED - Rate, Errors, Duration)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["method", "endpoint"],
)

# Inference metrics
INFERENCE_REQUESTS_TOTAL = Counter(
    "inference_requests_total",
    "Total inference requests",
    ["model_id", "status"],
)

INFERENCE_TIME_TO_FIRST_TOKEN = Histogram(
    "inference_ttft_seconds",
    "Time to first token in seconds",
    ["model_id"],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
)

INFERENCE_TOKENS_PER_SECOND = Histogram(
    "inference_tokens_per_second",
    "Tokens generated per second",
    ["model_id"],
    buckets=[5, 10, 15, 20, 25, 30, 40, 50, 75, 100],
)

INFERENCE_TOKENS_GENERATED = Counter(
    "inference_tokens_generated_total",
    "Total tokens generated",
    ["model_id"],
)

# Model cache metrics
MODEL_CACHE_SIZE = Gauge(
    "model_cache_size",
    "Number of models in cache",
)

MODEL_CACHE_MEMORY_GB = Gauge(
    "model_cache_memory_gb",
    "Memory used by model cache in GB",
)

MODEL_CACHE_HITS = Counter(
    "model_cache_hits_total",
    "Model cache hits",
)

MODEL_CACHE_MISSES = Counter(
    "model_cache_misses_total",
    "Model cache misses",
)

MODEL_CACHE_EVICTIONS = Counter(
    "model_cache_evictions_total",
    "Model cache evictions",
)

# Training metrics
TRAINING_JOBS_TOTAL = Counter(
    "training_jobs_total",
    "Total training jobs",
    ["status"],
)

TRAINING_JOB_DURATION_SECONDS = Histogram(
    "training_job_duration_seconds",
    "Training job duration in seconds",
    ["model_name"],
    buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800],
)

TRAINING_JOBS_IN_PROGRESS = Gauge(
    "training_jobs_in_progress",
    "Training jobs currently running",
)

TRAINING_LOSS = Gauge(
    "training_loss",
    "Current training loss",
    ["job_id"],
)

# Database metrics
DB_CONNECTIONS_IN_USE = Gauge(
    "db_connections_in_use",
    "Database connections currently in use",
)

DB_QUERY_DURATION_SECONDS = Histogram(
    "db_query_duration_seconds",
    "Database query duration in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# System metrics
MEMORY_USAGE_BYTES = Gauge(
    "memory_usage_bytes",
    "Process memory usage in bytes",
)

MLX_MEMORY_USAGE_GB = Gauge(
    "mlx_memory_usage_gb",
    "MLX memory usage in GB",
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        method = request.method
        # Normalize path to avoid high cardinality
        endpoint = self._normalize_path(request.url.path)

        # Track in-progress requests
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            duration = time.perf_counter() - start_time

            # Record metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality."""
        # Replace UUIDs with placeholder
        import re
        uuid_pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        normalized = re.sub(uuid_pattern, "{id}", path)
        return normalized


def record_inference_metrics(
    model_id: str,
    ttft: float,
    tokens_per_second: float,
    tokens_generated: int,
    success: bool = True,
) -> None:
    """Record inference metrics."""
    status = "success" if success else "error"
    INFERENCE_REQUESTS_TOTAL.labels(model_id=model_id, status=status).inc()

    if success:
        INFERENCE_TIME_TO_FIRST_TOKEN.labels(model_id=model_id).observe(ttft)
        INFERENCE_TOKENS_PER_SECOND.labels(model_id=model_id).observe(tokens_per_second)
        INFERENCE_TOKENS_GENERATED.labels(model_id=model_id).inc(tokens_generated)


def record_cache_hit() -> None:
    """Record a model cache hit."""
    MODEL_CACHE_HITS.inc()


def record_cache_miss() -> None:
    """Record a model cache miss."""
    MODEL_CACHE_MISSES.inc()


def record_cache_eviction() -> None:
    """Record a model cache eviction."""
    MODEL_CACHE_EVICTIONS.inc()


def update_cache_metrics(size: int, memory_gb: float) -> None:
    """Update cache size metrics."""
    MODEL_CACHE_SIZE.set(size)
    MODEL_CACHE_MEMORY_GB.set(memory_gb)


def record_training_job(status: str) -> None:
    """Record a training job completion."""
    TRAINING_JOBS_TOTAL.labels(status=status).inc()


def update_training_in_progress(count: int) -> None:
    """Update training jobs in progress."""
    TRAINING_JOBS_IN_PROGRESS.set(count)


def update_training_loss(job_id: str, loss: float) -> None:
    """Update current training loss."""
    TRAINING_LOSS.labels(job_id=job_id).set(loss)


def timed_db_operation(operation: str):
    """Decorator to time database operations."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start_time
                DB_QUERY_DURATION_SECONDS.labels(operation=operation).observe(duration)
        return wrapper
    return decorator


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def update_system_metrics() -> None:
    """Update system-level metrics."""
    import psutil

    process = psutil.Process()
    MEMORY_USAGE_BYTES.set(process.memory_info().rss)

    # Note: MLX memory tracking would go here if mlx exposed memory APIs
    # For now, rely on the model cache metrics to track MLX memory usage

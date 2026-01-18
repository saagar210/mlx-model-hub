"""Prometheus Metrics Collection (P24: Observability).

Provides application-level metrics for monitoring and alerting.
All metrics use the 'kas_' prefix for namespace clarity.
"""

from __future__ import annotations

from typing import Any

try:
    from prometheus_client import Counter, Gauge, Histogram, Info

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from knowledge.config import get_settings

# =============================================================================
# Stub Classes (when prometheus-client not installed)
# =============================================================================


class _StubMetric:
    """Stub metric that does nothing when prometheus is unavailable."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def labels(self, *args: object, **kwargs: object) -> _StubMetric:
        return self

    def inc(self, *args: object, **kwargs: object) -> None:
        pass

    def dec(self, *args: object, **kwargs: object) -> None:
        pass

    def set(self, *args: object, **kwargs: object) -> None:
        pass

    def observe(self, *args: object, **kwargs: object) -> None:
        pass

    def info(self, *args: object, **kwargs: object) -> None:
        pass


# =============================================================================
# Application Info
# =============================================================================

if PROMETHEUS_AVAILABLE:
    app_info = Info("kas", "Knowledge Activation System info")
    settings = get_settings()
    app_info.info({
        "version": settings.api_version,
        "environment": "production",
    })
else:
    app_info = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# HTTP Request Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    http_requests_total = Counter(
        "kas_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
    )

    http_request_duration_seconds = Histogram(
        "kas_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )

    http_requests_in_progress = Gauge(
        "kas_http_requests_in_progress",
        "Number of HTTP requests currently being processed",
        ["method"],
    )
else:
    http_requests_total = _StubMetric()  # type: ignore[assignment]
    http_request_duration_seconds = _StubMetric()  # type: ignore[assignment]
    http_requests_in_progress = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Search Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    search_requests_total = Counter(
        "kas_search_requests_total",
        "Total search requests",
        ["namespace", "reranked"],
    )

    search_duration_seconds = Histogram(
        "kas_search_duration_seconds",
        "Search duration in seconds",
        ["search_type"],  # bm25, vector, hybrid, rerank
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    )

    search_results_count = Histogram(
        "kas_search_results_count",
        "Number of search results returned",
        buckets=[0, 1, 2, 5, 10, 20, 50, 100],
    )
else:
    search_requests_total = _StubMetric()  # type: ignore[assignment]
    search_duration_seconds = _StubMetric()  # type: ignore[assignment]
    search_results_count = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Embedding Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    embedding_requests_total = Counter(
        "kas_embedding_requests_total",
        "Total embedding generation requests",
    )

    embedding_duration_seconds = Histogram(
        "kas_embedding_duration_seconds",
        "Embedding generation duration in seconds",
        buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
    )

    embedding_batch_size = Histogram(
        "kas_embedding_batch_size",
        "Number of texts in embedding batch",
        buckets=[1, 5, 10, 25, 50, 100],
    )
else:
    embedding_requests_total = _StubMetric()  # type: ignore[assignment]
    embedding_duration_seconds = _StubMetric()  # type: ignore[assignment]
    embedding_batch_size = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Reranker Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    rerank_requests_total = Counter(
        "kas_rerank_requests_total",
        "Total reranking requests",
    )

    rerank_duration_seconds = Histogram(
        "kas_rerank_duration_seconds",
        "Reranking duration in seconds",
        buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    )
else:
    rerank_requests_total = _StubMetric()  # type: ignore[assignment]
    rerank_duration_seconds = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Content Metrics (Gauges - updated periodically)
# =============================================================================

if PROMETHEUS_AVAILABLE:
    content_total = Gauge(
        "kas_content_total",
        "Total content items",
        ["type"],
    )

    chunks_total = Gauge(
        "kas_chunks_total",
        "Total chunks in database",
    )

    review_items_active = Gauge(
        "kas_review_items_active",
        "Active items in review queue",
    )

    review_items_due = Gauge(
        "kas_review_items_due",
        "Items due for review",
    )
else:
    content_total = _StubMetric()  # type: ignore[assignment]
    chunks_total = _StubMetric()  # type: ignore[assignment]
    review_items_active = _StubMetric()  # type: ignore[assignment]
    review_items_due = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Database Pool Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    db_pool_size = Gauge(
        "kas_db_pool_size",
        "Current database connection pool size",
    )

    db_pool_available = Gauge(
        "kas_db_pool_available",
        "Available database connections in pool",
    )

    db_pool_min = Gauge(
        "kas_db_pool_min",
        "Minimum database pool size",
    )

    db_pool_max = Gauge(
        "kas_db_pool_max",
        "Maximum database pool size",
    )
else:
    db_pool_size = _StubMetric()  # type: ignore[assignment]
    db_pool_available = _StubMetric()  # type: ignore[assignment]
    db_pool_min = _StubMetric()  # type: ignore[assignment]
    db_pool_max = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Circuit Breaker Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    circuit_breaker_state = Gauge(
        "kas_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=half_open, 2=open)",
        ["circuit"],
    )

    circuit_breaker_failures = Counter(
        "kas_circuit_breaker_failures_total",
        "Total circuit breaker failures",
        ["circuit"],
    )
else:
    circuit_breaker_state = _StubMetric()  # type: ignore[assignment]
    circuit_breaker_failures = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Rate Limiter Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    rate_limit_exceeded_total = Counter(
        "kas_rate_limit_exceeded_total",
        "Total rate limit exceeded events",
        ["client_type"],  # api_key, ip
    )

    rate_limit_remaining = Gauge(
        "kas_rate_limit_remaining",
        "Remaining rate limit tokens (sampled)",
    )
else:
    rate_limit_exceeded_total = _StubMetric()  # type: ignore[assignment]
    rate_limit_remaining = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Ingest Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    ingest_requests_total = Counter(
        "kas_ingest_requests_total",
        "Total ingest requests",
        ["content_type"],  # youtube, bookmark, file
    )

    ingest_duration_seconds = Histogram(
        "kas_ingest_duration_seconds",
        "Ingest duration in seconds",
        ["content_type"],
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    )

    ingest_failures_total = Counter(
        "kas_ingest_failures_total",
        "Total ingest failures",
        ["content_type", "error_type"],
    )
else:
    ingest_requests_total = _StubMetric()  # type: ignore[assignment]
    ingest_duration_seconds = _StubMetric()  # type: ignore[assignment]
    ingest_failures_total = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Cache Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    cache_hits_total = Counter(
        "kas_cache_hits_total",
        "Total cache hits",
        ["cache_type"],  # search, embedding, rerank, expansion
    )

    cache_misses_total = Counter(
        "kas_cache_misses_total",
        "Total cache misses",
        ["cache_type"],
    )

    cache_errors_total = Counter(
        "kas_cache_errors_total",
        "Total cache errors",
        ["cache_type", "operation"],  # get, set, delete
    )

    cache_connected = Gauge(
        "kas_cache_connected",
        "Cache connection status (1=connected, 0=disconnected)",
    )
else:
    cache_hits_total = _StubMetric()  # type: ignore[assignment]
    cache_misses_total = _StubMetric()  # type: ignore[assignment]
    cache_errors_total = _StubMetric()  # type: ignore[assignment]
    cache_connected = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Query Expansion Metrics
# =============================================================================

if PROMETHEUS_AVAILABLE:
    query_expansion_total = Counter(
        "kas_query_expansion_total",
        "Total query expansions performed",
    )

    query_expansion_terms_added = Histogram(
        "kas_query_expansion_terms_added",
        "Number of terms added by query expansion",
        buckets=[0, 1, 2, 3, 4, 5],
    )
else:
    query_expansion_total = _StubMetric()  # type: ignore[assignment]
    query_expansion_terms_added = _StubMetric()  # type: ignore[assignment]


# =============================================================================
# Helper Functions
# =============================================================================


def update_db_pool_metrics(pool_stats: dict[str, int]) -> None:
    """Update database pool metrics from stats dict."""
    if not PROMETHEUS_AVAILABLE:
        return

    db_pool_size.set(pool_stats.get("size", 0))
    db_pool_available.set(pool_stats.get("free_size", 0))
    db_pool_min.set(pool_stats.get("min_size", 0))
    db_pool_max.set(pool_stats.get("max_size", 0))


def update_content_metrics(stats: dict[str, Any]) -> None:
    """Update content metrics from stats dict."""
    if not PROMETHEUS_AVAILABLE:
        return

    # Update type-specific content counts
    content_by_type = stats.get("content_by_type", {})
    if isinstance(content_by_type, dict):
        for content_type, count in content_by_type.items():
            content_total.labels(type=content_type).set(count)

    chunks_total.set(stats.get("total_chunks", 0))
    review_items_active.set(stats.get("review_active", 0))
    review_items_due.set(stats.get("review_due", 0))


def record_search_metrics(
    namespace: str | None,
    reranked: bool,
    search_type: str,
    duration: float,
    result_count: int,
) -> None:
    """Record metrics for a search operation."""
    if not PROMETHEUS_AVAILABLE:
        return

    search_requests_total.labels(
        namespace=namespace or "all",
        reranked=str(reranked).lower(),
    ).inc()

    search_duration_seconds.labels(search_type=search_type).observe(duration)
    search_results_count.observe(result_count)


def record_embedding_metrics(duration: float, batch_size: int = 1) -> None:
    """Record metrics for embedding generation."""
    if not PROMETHEUS_AVAILABLE:
        return

    embedding_requests_total.inc()
    embedding_duration_seconds.observe(duration)
    embedding_batch_size.observe(batch_size)


def record_rerank_metrics(duration: float) -> None:
    """Record metrics for reranking operation."""
    if not PROMETHEUS_AVAILABLE:
        return

    rerank_requests_total.inc()
    rerank_duration_seconds.observe(duration)


def record_cache_hit(cache_type: str) -> None:
    """Record a cache hit."""
    if not PROMETHEUS_AVAILABLE:
        return
    cache_hits_total.labels(cache_type=cache_type).inc()


def record_cache_miss(cache_type: str) -> None:
    """Record a cache miss."""
    if not PROMETHEUS_AVAILABLE:
        return
    cache_misses_total.labels(cache_type=cache_type).inc()


def record_cache_error(cache_type: str, operation: str) -> None:
    """Record a cache error."""
    if not PROMETHEUS_AVAILABLE:
        return
    cache_errors_total.labels(cache_type=cache_type, operation=operation).inc()


def update_cache_connection_status(connected: bool) -> None:
    """Update cache connection status metric."""
    if not PROMETHEUS_AVAILABLE:
        return
    cache_connected.set(1 if connected else 0)


def record_query_expansion(terms_added: int) -> None:
    """Record a query expansion operation."""
    if not PROMETHEUS_AVAILABLE:
        return
    query_expansion_total.inc()
    query_expansion_terms_added.observe(terms_added)

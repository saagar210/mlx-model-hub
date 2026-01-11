"""Observability module - metrics and tracing."""

from .metrics import (
    PrometheusMiddleware,
    get_metrics,
    record_cache_eviction,
    record_cache_hit,
    record_cache_miss,
    record_inference_metrics,
    record_training_job,
    update_cache_metrics,
    update_system_metrics,
    update_training_in_progress,
    update_training_loss,
)
from .tracing import (
    RequestIdMiddleware,
    add_span_event,
    configure_logging_with_trace_context,
    create_span,
    get_current_span,
    get_request_id,
    get_tracer,
    record_exception,
    set_span_attribute,
    set_span_status,
    setup_db_tracing,
    setup_tracing,
)

__all__ = [
    # Metrics
    "PrometheusMiddleware",
    "get_metrics",
    "record_cache_eviction",
    "record_cache_hit",
    "record_cache_miss",
    "record_inference_metrics",
    "record_training_job",
    "update_cache_metrics",
    "update_system_metrics",
    "update_training_in_progress",
    "update_training_loss",
    # Tracing
    "RequestIdMiddleware",
    "add_span_event",
    "configure_logging_with_trace_context",
    "create_span",
    "get_current_span",
    "get_request_id",
    "get_tracer",
    "record_exception",
    "set_span_attribute",
    "set_span_status",
    "setup_db_tracing",
    "setup_tracing",
]

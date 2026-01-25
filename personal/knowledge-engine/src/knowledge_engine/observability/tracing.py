"""Distributed tracing with OpenTelemetry.

Provides request tracing across service boundaries for debugging
and performance analysis. Integrates with Jaeger, Zipkin, or any
OTLP-compatible backend.
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable, Generator, TypeVar

from knowledge_engine.config import get_settings
from knowledge_engine.logging_config import get_logger

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TracingManager:
    """Manages OpenTelemetry tracing configuration and lifecycle."""

    def __init__(self) -> None:
        """Initialize tracing manager."""
        self._tracer: "Tracer | None" = None
        self._initialized = False
        settings = get_settings()
        self._enabled = settings.otlp_endpoint is not None

    def initialize(self) -> None:
        """Initialize OpenTelemetry tracing if configured."""
        if self._initialized or not self._enabled:
            return

        settings = get_settings()

        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            # Create resource identifying this service
            resource = Resource.create({
                "service.name": "knowledge-engine",
                "service.version": "0.1.0",
                "deployment.environment": settings.environment.value,
            })

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Add OTLP exporter
            otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

            # Set as global provider
            trace.set_tracer_provider(provider)

            # Auto-instrument common libraries
            FastAPIInstrumentor.instrument()
            HTTPXClientInstrumentor().instrument()

            self._tracer = trace.get_tracer("knowledge-engine")
            self._initialized = True
            logger.info("OpenTelemetry tracing initialized", endpoint=settings.otlp_endpoint)

        except ImportError:
            logger.warning(
                "OpenTelemetry packages not installed. "
                "Install with: pip install knowledge-engine[observability]"
            )
        except Exception as e:
            logger.error("Failed to initialize tracing", error=str(e))

    @property
    def tracer(self) -> "Tracer | None":
        """Get the tracer instance."""
        if not self._initialized:
            self.initialize()
        return self._tracer

    @property
    def enabled(self) -> bool:
        """Check if tracing is enabled."""
        return self._enabled and self._tracer is not None

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> Generator["Span | None", None, None]:
        """Create a traced span context manager.

        Args:
            name: Name of the span (e.g., "vector_search", "generate_embedding")
            attributes: Optional attributes to add to the span

        Yields:
            The span object, or None if tracing is disabled
        """
        if not self.enabled or self._tracer is None:
            yield None
            return

        from opentelemetry.trace import Status, StatusCode

        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    # Convert non-string values to strings for compatibility
                    if not isinstance(value, (str, int, float, bool)):
                        value = str(value)
                    span.set_attribute(key, value)

            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    def add_event(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Add an event to the current span.

        Args:
            name: Event name
            attributes: Optional event attributes
        """
        if not self.enabled:
            return

        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(name, attributes or {})

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span.

        Args:
            key: Attribute key
            value: Attribute value
        """
        if not self.enabled:
            return

        from opentelemetry import trace

        current_span = trace.get_current_span()
        if current_span:
            if not isinstance(value, (str, int, float, bool)):
                value = str(value)
            current_span.set_attribute(key, value)

    def shutdown(self) -> None:
        """Shutdown tracing, flushing any pending spans."""
        if self._initialized:
            try:
                from opentelemetry import trace

                provider = trace.get_tracer_provider()
                if hasattr(provider, "shutdown"):
                    provider.shutdown()
                logger.info("OpenTelemetry tracing shutdown complete")
            except Exception as e:
                logger.error("Error shutting down tracing", error=str(e))


@lru_cache
def get_tracer() -> TracingManager:
    """Get singleton tracing manager instance."""
    return TracingManager()


def trace_operation(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator to trace a function execution.

    Args:
        name: Span name (defaults to function name)
        attributes: Static attributes to add to span

    Example:
        @trace_operation("search_documents")
        async def search(query: str) -> list[Document]:
            ...

        @trace_operation(attributes={"component": "embedding"})
        def generate_embedding(text: str) -> list[float]:
            ...
    """
    def decorator(func: F) -> F:
        span_name = name or func.__name__
        is_async = callable(func) and hasattr(func, "__code__") and func.__code__.co_flags & 0x80

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                span_attrs = dict(attributes) if attributes else {}
                span_attrs["function"] = func.__name__

                with tracer.span(span_name, span_attrs):
                    return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                tracer = get_tracer()
                span_attrs = dict(attributes) if attributes else {}
                span_attrs["function"] = func.__name__

                with tracer.span(span_name, span_attrs):
                    return func(*args, **kwargs)

            return sync_wrapper  # type: ignore[return-value]

    return decorator


class SpanAttributes:
    """Standard span attribute keys for consistency."""

    # Document attributes
    DOCUMENT_ID = "document.id"
    DOCUMENT_SOURCE = "document.source"
    DOCUMENT_TYPE = "document.type"
    DOCUMENT_SIZE_BYTES = "document.size_bytes"
    CHUNK_COUNT = "document.chunk_count"

    # Search attributes
    SEARCH_QUERY = "search.query"
    SEARCH_TYPE = "search.type"
    SEARCH_LIMIT = "search.limit"
    SEARCH_RESULTS_COUNT = "search.results_count"
    SEARCH_CONFIDENCE = "search.confidence"

    # Embedding attributes
    EMBEDDING_PROVIDER = "embedding.provider"
    EMBEDDING_MODEL = "embedding.model"
    EMBEDDING_BATCH_SIZE = "embedding.batch_size"
    EMBEDDING_DIMENSIONS = "embedding.dimensions"

    # LLM attributes
    LLM_PROVIDER = "llm.provider"
    LLM_MODEL = "llm.model"
    LLM_INPUT_TOKENS = "llm.input_tokens"
    LLM_OUTPUT_TOKENS = "llm.output_tokens"
    LLM_TEMPERATURE = "llm.temperature"

    # Database attributes
    DB_SYSTEM = "db.system"
    DB_OPERATION = "db.operation"
    DB_COLLECTION = "db.collection"

    # Memory attributes
    MEMORY_TYPE = "memory.type"
    MEMORY_NAMESPACE = "memory.namespace"
    MEMORY_COUNT = "memory.count"

    # Cache attributes
    CACHE_TYPE = "cache.type"
    CACHE_HIT = "cache.hit"
    CACHE_KEY = "cache.key"

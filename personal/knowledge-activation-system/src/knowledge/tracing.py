"""OpenTelemetry Distributed Tracing (P25: Observability).

Provides distributed tracing for request flow visualization and debugging.
Integrates with Jaeger, Zipkin, or any OTLP-compatible backend.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from knowledge.config import get_settings
from knowledge.logging import get_logger

logger = get_logger(__name__)

# Track initialization state
_tracing_initialized = False


# =============================================================================
# Stub Classes (when OpenTelemetry not installed)
# =============================================================================


class _StubSpan:
    """Stub span that does nothing when tracing is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass

    def record_exception(self, exception: BaseException) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def __enter__(self) -> _StubSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _StubTracer:
    """Stub tracer that does nothing when tracing is disabled."""

    def start_span(self, name: str, **kwargs: Any) -> _StubSpan:
        return _StubSpan()

    @contextmanager
    def start_as_current_span(
        self, name: str, **kwargs: Any
    ) -> Generator[_StubSpan, None, None]:
        yield _StubSpan()


# =============================================================================
# Tracing Configuration
# =============================================================================


def configure_tracing() -> bool:
    """
    Configure OpenTelemetry tracing.

    Returns:
        True if tracing was configured, False otherwise
    """
    global _tracing_initialized

    if _tracing_initialized:
        return True

    settings = get_settings()

    if not settings.tracing_enabled:
        logger.info("tracing_disabled")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        # Create sampler based on sample rate
        sampler = TraceIdRatioBased(settings.tracing_sample_rate)

        # Create resource with service info
        resource = Resource.create({
            "service.name": "kas",
            "service.version": settings.api_version,
            "deployment.environment": "production",
        })

        # Create provider
        provider = TracerProvider(resource=resource, sampler=sampler)

        # Add OTLP exporter if endpoint configured
        if settings.tracing_otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=settings.tracing_otlp_endpoint)
                provider.add_span_processor(BatchSpanProcessor(exporter))
                logger.info(
                    "otlp_exporter_configured",
                    endpoint=settings.tracing_otlp_endpoint,
                )
            except ImportError:
                logger.warning("otlp_exporter_not_installed")

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Auto-instrument libraries
        _instrument_libraries()

        _tracing_initialized = True
        logger.info(
            "tracing_configured",
            sample_rate=settings.tracing_sample_rate,
        )
        return True

    except ImportError:
        logger.warning("opentelemetry_not_installed")
        return False
    except Exception as e:
        logger.error("tracing_configuration_failed", error=str(e))
        return False


def _instrument_libraries() -> None:
    """Auto-instrument common libraries."""
    # FastAPI instrumentation
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument()
        logger.debug("instrumented_fastapi")
    except ImportError:
        pass

    # AsyncPG instrumentation
    try:
        from opentelemetry.instrumentation.asyncpg import (  # type: ignore[import-not-found]
            AsyncPGInstrumentor,
        )

        AsyncPGInstrumentor().instrument()
        logger.debug("instrumented_asyncpg")
    except ImportError:
        pass

    # HTTPX instrumentation
    try:
        from opentelemetry.instrumentation.httpx import (  # type: ignore[import-not-found]
            HTTPXClientInstrumentor,
        )

        HTTPXClientInstrumentor().instrument()
        logger.debug("instrumented_httpx")
    except ImportError:
        pass


# =============================================================================
# Tracer Access
# =============================================================================


def get_tracer(name: str) -> Any:
    """
    Get a tracer instance for the given name.

    Args:
        name: Usually __name__ of the module

    Returns:
        Tracer instance (real or stub)
    """
    settings = get_settings()

    if not settings.tracing_enabled:
        return _StubTracer()

    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _StubTracer()


def get_current_span() -> Any:
    """
    Get the current active span.

    Returns:
        Current span or stub span
    """
    settings = get_settings()

    if not settings.tracing_enabled:
        return _StubSpan()

    try:
        from opentelemetry import trace

        return trace.get_current_span()
    except ImportError:
        return _StubSpan()


# =============================================================================
# Span Decorators and Context Managers
# =============================================================================


@contextmanager
def traced_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer_name: str = "kas",
) -> Generator[Any, None, None]:
    """
    Context manager for tracing an operation.

    Args:
        name: Name of the operation/span
        attributes: Optional attributes to add to span
        tracer_name: Name of the tracer to use

    Yields:
        The span (real or stub)

    Example:
        with traced_operation("fetch_content", {"content_id": id}):
            content = await db.get_content(id)
    """
    tracer = get_tracer(tracer_name)

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise


def add_span_attributes(attributes: dict[str, Any]) -> None:
    """
    Add attributes to the current span.

    Args:
        attributes: Dict of attributes to add
    """
    span = get_current_span()
    for key, value in attributes.items():
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """
    Add an event to the current span.

    Args:
        name: Event name
        attributes: Optional event attributes
    """
    span = get_current_span()
    span.add_event(name, attributes=attributes)


# =============================================================================
# Trace Context Propagation
# =============================================================================


def get_trace_context() -> dict[str, str]:
    """
    Get the current trace context for propagation.

    Returns:
        Dict with trace context headers
    """
    settings = get_settings()

    if not settings.tracing_enabled:
        return {}

    try:
        from opentelemetry.propagate import inject

        context: dict[str, str] = {}
        inject(context)
        return context
    except ImportError:
        return {}


def get_trace_id() -> str | None:
    """
    Get the current trace ID.

    Returns:
        Trace ID as hex string or None
    """
    settings = get_settings()

    if not settings.tracing_enabled:
        return None

    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, "032x")
        return None
    except ImportError:
        return None

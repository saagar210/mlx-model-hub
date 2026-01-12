"""OpenTelemetry tracing setup for MLX Model Hub."""

import logging
import uuid
from contextvars import ContextVar
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from mlx_hub.config import get_settings

logger = logging.getLogger(__name__)

# Context variable for request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def setup_tracing(app: Any = None) -> TracerProvider:
    """Set up OpenTelemetry tracing.

    Args:
        app: Optional FastAPI application to instrument.

    Returns:
        Configured TracerProvider.
    """
    settings = get_settings()

    # Create resource with service information
    resource = Resource.create(
        {
            "service.name": "mlx-hub",
            "service.version": "0.1.0",
            "service.instance.id": str(uuid.uuid4()),
            "deployment.environment": "development" if settings.debug else "production",
        }
    )

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add console exporter for development
    if settings.debug:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("OpenTelemetry console exporter enabled")

    # Add OTLP exporter if endpoint configured
    otlp_endpoint = getattr(settings, "otlp_endpoint", None)
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"OpenTelemetry OTLP exporter enabled: {otlp_endpoint}")

    # Set as global tracer provider
    trace.set_tracer_provider(provider)

    # Instrument libraries
    HTTPXClientInstrumentor().instrument()
    logger.info("HTTPX instrumentation enabled")

    # Instrument FastAPI if provided
    if app:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumentation enabled")

    return provider


def setup_db_tracing(engine: Any) -> None:
    """Set up database tracing.

    Args:
        engine: SQLAlchemy engine to instrument.
    """
    SQLAlchemyInstrumentor().instrument(engine=engine)
    logger.info("SQLAlchemy instrumentation enabled")


def get_tracer(name: str = "mlx-hub") -> trace.Tracer:
    """Get a tracer instance.

    Args:
        name: Tracer name (typically module name).

    Returns:
        Tracer instance.
    """
    return trace.get_tracer(name)


def get_current_span() -> trace.Span:
    """Get the current active span."""
    return trace.get_current_span()


def get_request_id() -> str:
    """Get the current request ID."""
    return request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the current request ID."""
    request_id_ctx.set(request_id)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and add request ID."""
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Set in context
        set_request_id(request_id)

        # Add to current span if available
        current_span = get_current_span()
        if current_span.is_recording():
            current_span.set_attribute("request.id", request_id)

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class TraceContextLogger(logging.Filter):
    """Logging filter to add trace context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add trace context to log record."""
        # Add request ID
        record.request_id = get_request_id() or "-"

        # Add trace and span IDs
        current_span = get_current_span()
        span_context = current_span.get_span_context()

        if span_context.is_valid:
            record.trace_id = format(span_context.trace_id, "032x")
            record.span_id = format(span_context.span_id, "016x")
        else:
            record.trace_id = "-"
            record.span_id = "-"

        return True


def configure_logging_with_trace_context() -> None:
    """Configure logging to include trace context."""
    # Create formatter with trace context
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[trace_id=%(trace_id)s span_id=%(span_id)s request_id=%(request_id)s] - "
        "%(message)s"
    )

    # Add filter to root logger
    root_logger = logging.getLogger()
    trace_filter = TraceContextLogger()

    for handler in root_logger.handlers:
        handler.addFilter(trace_filter)
        handler.setFormatter(formatter)


def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    kind: trace.SpanKind = trace.SpanKind.INTERNAL,
):
    """Context manager to create a new span.

    Args:
        name: Span name.
        attributes: Optional span attributes.
        kind: Span kind (internal, server, client, etc.).

    Returns:
        Span context manager.
    """
    tracer = get_tracer()
    return tracer.start_as_current_span(
        name,
        attributes=attributes or {},
        kind=kind,
    )


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span.

    Args:
        name: Event name.
        attributes: Optional event attributes.
    """
    current_span = get_current_span()
    if current_span.is_recording():
        current_span.add_event(name, attributes=attributes or {})


def set_span_status(code: StatusCode, description: str | None = None) -> None:
    """Set the status of the current span.

    Args:
        code: Status code (OK, ERROR).
        description: Optional status description.
    """
    current_span = get_current_span()
    if current_span.is_recording():
        current_span.set_status(Status(code, description))


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span.

    Args:
        exception: The exception to record.
    """
    current_span = get_current_span()
    if current_span.is_recording():
        current_span.record_exception(exception)
        current_span.set_status(Status(StatusCode.ERROR, str(exception)))


def set_span_attribute(key: str, value: Any) -> None:
    """Set an attribute on the current span.

    Args:
        key: Attribute key.
        value: Attribute value.
    """
    current_span = get_current_span()
    if current_span.is_recording():
        current_span.set_attribute(key, value)

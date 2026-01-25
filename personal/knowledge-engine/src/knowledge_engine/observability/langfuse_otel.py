"""
OpenTelemetry to Langfuse bridge for Knowledge Engine.

Configures OpenTelemetry to export traces to Langfuse's OTLP endpoint,
enabling unified observability for RAG pipelines and other operations.

Usage:
    from knowledge_engine.observability.langfuse_otel import configure_langfuse_otel

    tracer = configure_langfuse_otel()

    with tracer.start_as_current_span("rag_query") as span:
        span.set_attribute("question.length", len(question))
        # RAG pipeline execution
"""

from __future__ import annotations

import os
import base64
import logging
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

logger = logging.getLogger(__name__)


def get_langfuse_auth_header() -> str:
    """
    Create Basic auth header for Langfuse OTLP endpoint.

    Returns:
        Base64-encoded "public_key:secret_key" string
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

    credentials = f"{public_key}:{secret_key}"
    return base64.b64encode(credentials.encode()).decode()


def configure_langfuse_otel(
    service_name: str = "knowledge-engine",
    service_version: str = "1.0.0",
    enable_console: bool = False,
) -> trace.Tracer:
    """
    Configure OpenTelemetry to export traces to Langfuse.

    Sets up the trace provider with Langfuse's OTLP endpoint and returns
    a tracer that can be used to create spans.

    Args:
        service_name: Name of the service for trace attribution
        service_version: Version of the service
        enable_console: Also export spans to console (for debugging)

    Returns:
        OpenTelemetry Tracer instance

    Example:
        tracer = configure_langfuse_otel()

        with tracer.start_as_current_span("retrieval") as span:
            span.set_attribute("query", question[:100])
            docs = retriever.search(question)
            span.set_attribute("doc_count", len(docs))
    """
    # Check if already configured
    current_provider = trace.get_tracer_provider()
    if isinstance(current_provider, TracerProvider):
        logger.debug("TracerProvider already configured, returning existing tracer")
        return trace.get_tracer(service_name)

    # Create resource with service information
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
    })

    # Create and configure provider
    provider = TracerProvider(resource=resource)

    # Configure Langfuse OTLP exporter
    langfuse_host = os.getenv("LANGFUSE_HOST", "http://localhost:3002")
    langfuse_enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() in ("true", "1", "yes")

    if langfuse_enabled:
        try:
            langfuse_exporter = OTLPSpanExporter(
                endpoint=f"{langfuse_host}/api/public/otel/v1/traces",
                headers={
                    "Authorization": f"Basic {get_langfuse_auth_header()}"
                },
            )
            provider.add_span_processor(BatchSpanProcessor(langfuse_exporter))
            logger.info(f"Langfuse OTLP exporter configured: {langfuse_host}")
        except Exception as e:
            logger.error(f"Failed to configure Langfuse exporter: {e}")
    else:
        logger.info("Langfuse tracing disabled")

    # Optional console exporter for debugging
    if enable_console:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.debug("Console span exporter enabled")

    # Set as global provider
    trace.set_tracer_provider(provider)

    return trace.get_tracer(service_name)


class RAGTracer:
    """
    Convenience wrapper for tracing RAG pipeline operations.

    Provides methods for creating spans with appropriate attributes
    for retrieval and generation operations.

    Example:
        rag_tracer = RAGTracer()

        with rag_tracer.retrieval("Find docs about AI") as span:
            docs = retriever.search(question)
            span.set_result(len(docs))

        with rag_tracer.generation("qwen2.5:14b", docs) as span:
            answer = generator.generate(question, docs)
            span.set_result(answer)
    """

    def __init__(self, tracer: Optional[trace.Tracer] = None):
        self.tracer = tracer or configure_langfuse_otel()

    class RetrievalSpan:
        """Context manager for retrieval operations."""

        def __init__(self, tracer: trace.Tracer, query: str):
            self.tracer = tracer
            self.query = query
            self.span = None

        def __enter__(self):
            self.span = self.tracer.start_span("retrieval")
            self.span.set_attribute("retrieval.query", self.query[:500])
            self.span.set_attribute("retrieval.query_length", len(self.query))
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.span.set_attribute("error", True)
                self.span.set_attribute("error.type", exc_type.__name__)
                self.span.set_attribute("error.message", str(exc_val)[:500])
            self.span.end()
            return False

        def set_result(self, doc_count: int, latency_ms: Optional[float] = None):
            """Set retrieval results on the span."""
            self.span.set_attribute("retrieval.doc_count", doc_count)
            if latency_ms:
                self.span.set_attribute("retrieval.latency_ms", latency_ms)

    class GenerationSpan:
        """Context manager for generation operations."""

        def __init__(self, tracer: trace.Tracer, model: str, context_docs: int):
            self.tracer = tracer
            self.model = model
            self.context_docs = context_docs
            self.span = None

        def __enter__(self):
            self.span = self.tracer.start_span("generation")
            self.span.set_attribute("generation.model", self.model)
            self.span.set_attribute("generation.context_doc_count", self.context_docs)
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                self.span.set_attribute("error", True)
                self.span.set_attribute("error.type", exc_type.__name__)
                self.span.set_attribute("error.message", str(exc_val)[:500])
            self.span.end()
            return False

        def set_result(self, output: str, latency_ms: Optional[float] = None):
            """Set generation results on the span."""
            self.span.set_attribute("generation.output_length", len(output))
            self.span.set_attribute("generation.output_preview", output[:200])
            if latency_ms:
                self.span.set_attribute("generation.latency_ms", latency_ms)

    def retrieval(self, query: str) -> RetrievalSpan:
        """Create a retrieval span context manager."""
        return self.RetrievalSpan(self.tracer, query)

    def generation(self, model: str, context_doc_count: int) -> GenerationSpan:
        """Create a generation span context manager."""
        return self.GenerationSpan(self.tracer, model, context_doc_count)

    def query(self, question: str):
        """
        Create a top-level RAG query span.

        Use as context manager for the entire RAG pipeline.

        Example:
            with rag_tracer.query("What is machine learning?") as span:
                # Retrieval
                docs = retriever.search(question)
                span.set_attribute("retrieval.doc_count", len(docs))

                # Generation
                answer = generator.generate(question, docs)
                span.set_attribute("generation.answer_length", len(answer))
        """
        span = self.tracer.start_span("rag_query")
        span.set_attribute("rag.question", question[:500])
        span.set_attribute("rag.question_length", len(question))
        return span


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID if available."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")
    return None

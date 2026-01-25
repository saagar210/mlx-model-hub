"""Comprehensive metrics collection for Knowledge Engine.

This module provides business-level metrics beyond basic HTTP stats.
Metrics categories:
- Document ingestion (count, size, time, errors)
- Search operations (latency, result counts, fusion stages)
- Memory operations (store, recall, access patterns)
- Embedding generation (batch sizes, latency, errors)
- LLM operations (token usage, latency, model selection)
- Vector database operations (insert, search, delete)
- Graph database operations (node/edge counts, traversals)
- Cache operations (hits, misses, evictions)
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    Summary,
)

if TYPE_CHECKING:
    from prometheus_client.metrics import MetricWrapperBase


class MetricsCollector:
    """Centralized metrics collection with labeled metrics for detailed analysis."""

    def __init__(self) -> None:
        """Initialize all metric collectors."""
        self._init_system_metrics()
        self._init_ingestion_metrics()
        self._init_search_metrics()
        self._init_memory_metrics()
        self._init_embedding_metrics()
        self._init_llm_metrics()
        self._init_vector_db_metrics()
        self._init_graph_db_metrics()
        self._init_cache_metrics()

    def _init_system_metrics(self) -> None:
        """System-level metrics."""
        self.app_info = Info(
            "knowledge_engine",
            "Knowledge Engine application information",
        )
        self.app_info.info({
            "version": "0.1.0",
            "python_version": "3.11+",
        })

        self.uptime_seconds = Gauge(
            "knowledge_engine_uptime_seconds",
            "Application uptime in seconds",
        )

        self.active_connections = Gauge(
            "knowledge_engine_active_connections",
            "Number of active connections",
            ["connection_type"],  # postgres, qdrant, neo4j, redis
        )

    def _init_ingestion_metrics(self) -> None:
        """Document ingestion metrics."""
        self.documents_ingested_total = Counter(
            "knowledge_engine_documents_ingested_total",
            "Total documents ingested",
            ["source_type", "status"],  # source: url, youtube, file; status: success, error
        )

        self.documents_bytes_ingested = Counter(
            "knowledge_engine_documents_bytes_ingested_total",
            "Total bytes of content ingested",
            ["source_type"],
        )

        self.chunks_created_total = Counter(
            "knowledge_engine_chunks_created_total",
            "Total chunks created from documents",
            ["source_type"],
        )

        self.ingestion_duration_seconds = Histogram(
            "knowledge_engine_ingestion_duration_seconds",
            "Time to ingest a document",
            ["source_type"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0],
        )

        self.ingestion_queue_size = Gauge(
            "knowledge_engine_ingestion_queue_size",
            "Number of items waiting in ingestion queue",
        )

        self.ingestion_errors_total = Counter(
            "knowledge_engine_ingestion_errors_total",
            "Total ingestion errors by type",
            ["source_type", "error_type"],  # error_type: network, parse, validation, embedding
        )

    def _init_search_metrics(self) -> None:
        """Search operation metrics."""
        self.searches_total = Counter(
            "knowledge_engine_searches_total",
            "Total search operations",
            ["search_type"],  # vector, keyword, hybrid, memory
        )

        self.search_duration_seconds = Histogram(
            "knowledge_engine_search_duration_seconds",
            "Search operation latency",
            ["search_type", "stage"],  # stage: vector, bm25, fusion, rerank, total
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        self.search_results_count = Histogram(
            "knowledge_engine_search_results_count",
            "Number of results returned per search",
            ["search_type"],
            buckets=[0, 1, 5, 10, 25, 50, 100],
        )

        self.search_rerank_candidates = Histogram(
            "knowledge_engine_search_rerank_candidates",
            "Number of candidates sent to reranker",
            buckets=[5, 10, 25, 50, 100, 200],
        )

        self.search_confidence_score = Summary(
            "knowledge_engine_search_confidence_score",
            "Distribution of search confidence scores",
            ["search_type"],
        )

    def _init_memory_metrics(self) -> None:
        """Memory operation metrics."""
        self.memories_stored_total = Counter(
            "knowledge_engine_memories_stored_total",
            "Total memories stored",
            ["memory_type", "namespace"],
        )

        self.memories_recalled_total = Counter(
            "knowledge_engine_memories_recalled_total",
            "Total memory recall operations",
            ["namespace"],
        )

        self.memory_access_total = Counter(
            "knowledge_engine_memory_access_total",
            "Total memory access events",
            ["memory_type", "namespace"],
        )

        self.memories_active = Gauge(
            "knowledge_engine_memories_active",
            "Current number of active (non-deleted) memories",
            ["memory_type", "namespace"],
        )

        self.memory_store_duration_seconds = Histogram(
            "knowledge_engine_memory_store_duration_seconds",
            "Time to store a memory",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0],
        )

        self.memory_recall_duration_seconds = Histogram(
            "knowledge_engine_memory_recall_duration_seconds",
            "Time to recall memories",
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
        )

    def _init_embedding_metrics(self) -> None:
        """Embedding generation metrics."""
        self.embeddings_generated_total = Counter(
            "knowledge_engine_embeddings_generated_total",
            "Total embeddings generated",
            ["provider", "model"],  # provider: ollama, voyage
        )

        self.embedding_batch_size = Histogram(
            "knowledge_engine_embedding_batch_size",
            "Batch sizes for embedding generation",
            ["provider"],
            buckets=[1, 5, 10, 25, 50, 100, 200],
        )

        self.embedding_duration_seconds = Histogram(
            "knowledge_engine_embedding_duration_seconds",
            "Time to generate embeddings",
            ["provider", "model"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        self.embedding_tokens_processed = Counter(
            "knowledge_engine_embedding_tokens_processed_total",
            "Total tokens processed for embeddings (estimated)",
            ["provider"],
        )

        self.embedding_errors_total = Counter(
            "knowledge_engine_embedding_errors_total",
            "Total embedding generation errors",
            ["provider", "error_type"],
        )

    def _init_llm_metrics(self) -> None:
        """LLM operation metrics."""
        self.llm_requests_total = Counter(
            "knowledge_engine_llm_requests_total",
            "Total LLM requests",
            ["provider", "model", "operation"],  # operation: query, summary, entity_extract, etc.
        )

        self.llm_tokens_input_total = Counter(
            "knowledge_engine_llm_tokens_input_total",
            "Total input tokens sent to LLM",
            ["provider", "model"],
        )

        self.llm_tokens_output_total = Counter(
            "knowledge_engine_llm_tokens_output_total",
            "Total output tokens from LLM",
            ["provider", "model"],
        )

        self.llm_duration_seconds = Histogram(
            "knowledge_engine_llm_duration_seconds",
            "LLM request latency",
            ["provider", "model", "operation"],
            buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
        )

        self.llm_errors_total = Counter(
            "knowledge_engine_llm_errors_total",
            "Total LLM errors",
            ["provider", "error_type"],  # error_type: rate_limit, timeout, invalid_response
        )

        self.llm_cost_estimate_dollars = Counter(
            "knowledge_engine_llm_cost_estimate_dollars",
            "Estimated LLM cost in dollars",
            ["provider", "model"],
        )

    def _init_vector_db_metrics(self) -> None:
        """Vector database (Qdrant) metrics."""
        self.vector_points_inserted = Counter(
            "knowledge_engine_vector_points_inserted_total",
            "Total vector points inserted",
            ["collection"],
        )

        self.vector_points_deleted = Counter(
            "knowledge_engine_vector_points_deleted_total",
            "Total vector points deleted",
            ["collection"],
        )

        self.vector_search_requests = Counter(
            "knowledge_engine_vector_search_requests_total",
            "Total vector search requests",
            ["collection"],
        )

        self.vector_search_duration_seconds = Histogram(
            "knowledge_engine_vector_search_duration_seconds",
            "Vector search latency",
            ["collection"],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
        )

        self.vector_collection_points = Gauge(
            "knowledge_engine_vector_collection_points",
            "Number of points in vector collection",
            ["collection"],
        )

        self.vector_collection_segments = Gauge(
            "knowledge_engine_vector_collection_segments",
            "Number of segments in vector collection",
            ["collection"],
        )

    def _init_graph_db_metrics(self) -> None:
        """Graph database (Neo4j) metrics."""
        self.graph_nodes_total = Gauge(
            "knowledge_engine_graph_nodes_total",
            "Total nodes in graph",
            ["label"],  # Document, Entity, Memory, etc.
        )

        self.graph_edges_total = Gauge(
            "knowledge_engine_graph_edges_total",
            "Total edges in graph",
            ["relationship_type"],
        )

        self.graph_queries_total = Counter(
            "knowledge_engine_graph_queries_total",
            "Total graph queries executed",
            ["query_type"],  # traversal, match, create, delete
        )

        self.graph_query_duration_seconds = Histogram(
            "knowledge_engine_graph_query_duration_seconds",
            "Graph query latency",
            ["query_type"],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        )

        self.graph_traversal_hops = Histogram(
            "knowledge_engine_graph_traversal_hops",
            "Number of hops in graph traversals",
            buckets=[1, 2, 3, 4, 5, 10],
        )

    def _init_cache_metrics(self) -> None:
        """Cache (Redis) metrics."""
        self.cache_hits_total = Counter(
            "knowledge_engine_cache_hits_total",
            "Total cache hits",
            ["cache_type"],  # embedding, search, query
        )

        self.cache_misses_total = Counter(
            "knowledge_engine_cache_misses_total",
            "Total cache misses",
            ["cache_type"],
        )

        self.cache_sets_total = Counter(
            "knowledge_engine_cache_sets_total",
            "Total cache set operations",
            ["cache_type"],
        )

        self.cache_evictions_total = Counter(
            "knowledge_engine_cache_evictions_total",
            "Total cache evictions",
            ["cache_type", "reason"],  # reason: ttl, memory, manual
        )

        self.cache_size_bytes = Gauge(
            "knowledge_engine_cache_size_bytes",
            "Current cache size in bytes",
            ["cache_type"],
        )

        self.cache_operation_duration_seconds = Histogram(
            "knowledge_engine_cache_operation_duration_seconds",
            "Cache operation latency",
            ["cache_type", "operation"],  # operation: get, set, delete
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1],
        )

    # Convenience methods for common metric updates

    def record_document_ingestion(
        self,
        source_type: str,
        success: bool,
        content_bytes: int,
        chunks: int,
        duration_seconds: float,
        error_type: str | None = None,
    ) -> None:
        """Record a document ingestion attempt."""
        status = "success" if success else "error"
        self.documents_ingested_total.labels(
            source_type=source_type,
            status=status,
        ).inc()

        if success:
            self.documents_bytes_ingested.labels(source_type=source_type).inc(content_bytes)
            self.chunks_created_total.labels(source_type=source_type).inc(chunks)

        self.ingestion_duration_seconds.labels(source_type=source_type).observe(duration_seconds)

        if not success and error_type:
            self.ingestion_errors_total.labels(
                source_type=source_type,
                error_type=error_type,
            ).inc()

    def record_search(
        self,
        search_type: str,
        duration_seconds: float,
        results_count: int,
        confidence_score: float | None = None,
        stage_durations: dict[str, float] | None = None,
    ) -> None:
        """Record a search operation."""
        self.searches_total.labels(search_type=search_type).inc()
        self.search_duration_seconds.labels(
            search_type=search_type,
            stage="total",
        ).observe(duration_seconds)
        self.search_results_count.labels(search_type=search_type).observe(results_count)

        if confidence_score is not None:
            self.search_confidence_score.labels(search_type=search_type).observe(confidence_score)

        if stage_durations:
            for stage, dur in stage_durations.items():
                self.search_duration_seconds.labels(
                    search_type=search_type,
                    stage=stage,
                ).observe(dur)

    def record_embedding_generation(
        self,
        provider: str,
        model: str,
        batch_size: int,
        duration_seconds: float,
        tokens_estimated: int,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        """Record an embedding generation operation."""
        if success:
            self.embeddings_generated_total.labels(
                provider=provider,
                model=model,
            ).inc(batch_size)
            self.embedding_batch_size.labels(provider=provider).observe(batch_size)
            self.embedding_duration_seconds.labels(
                provider=provider,
                model=model,
            ).observe(duration_seconds)
            self.embedding_tokens_processed.labels(provider=provider).inc(tokens_estimated)
        elif error_type:
            self.embedding_errors_total.labels(
                provider=provider,
                error_type=error_type,
            ).inc()

    def record_llm_request(
        self,
        provider: str,
        model: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        """Record an LLM request."""
        self.llm_requests_total.labels(
            provider=provider,
            model=model,
            operation=operation,
        ).inc()

        if success:
            self.llm_tokens_input_total.labels(provider=provider, model=model).inc(input_tokens)
            self.llm_tokens_output_total.labels(provider=provider, model=model).inc(output_tokens)
            self.llm_duration_seconds.labels(
                provider=provider,
                model=model,
                operation=operation,
            ).observe(duration_seconds)
        elif error_type:
            self.llm_errors_total.labels(provider=provider, error_type=error_type).inc()

    def record_cache_operation(
        self,
        cache_type: str,
        operation: str,
        hit: bool | None = None,
        duration_seconds: float = 0.0,
    ) -> None:
        """Record a cache operation."""
        self.cache_operation_duration_seconds.labels(
            cache_type=cache_type,
            operation=operation,
        ).observe(duration_seconds)

        if operation == "get":
            if hit:
                self.cache_hits_total.labels(cache_type=cache_type).inc()
            else:
                self.cache_misses_total.labels(cache_type=cache_type).inc()
        elif operation == "set":
            self.cache_sets_total.labels(cache_type=cache_type).inc()


@lru_cache
def get_metrics() -> MetricsCollector:
    """Get singleton metrics collector instance."""
    return MetricsCollector()

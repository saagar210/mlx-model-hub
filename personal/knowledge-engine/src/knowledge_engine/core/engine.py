"""Main Knowledge Engine orchestrating all components.

Cost-optimized design:
- Default: Ollama (embeddings, reranking, LLM) + Qdrant + PostgreSQL = FREE
- Optional: Enable graph_enabled for Neo4j integration
- Upgrade: Switch providers via environment variables
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID, uuid4

from knowledge_engine.config import Settings, get_settings
from knowledge_engine.core.embeddings import EmbeddingService
from knowledge_engine.core.fusion import reciprocal_rank_fusion
from knowledge_engine.core.llm import LLMService
from knowledge_engine.core.reranker import RerankerService
from knowledge_engine.models.documents import Document, DocumentCreate
from knowledge_engine.models.memory import Memory, MemoryCreate
from knowledge_engine.models.query import Citation, ConfidenceLevel, QueryRequest, QueryResponse
from knowledge_engine.models.search import (
    HybridSearchRequest,
    SearchResult,
    SearchResultItem,
)
from knowledge_engine.storage.postgres import PostgresStore
from knowledge_engine.storage.qdrant import QdrantStore

logger = logging.getLogger(__name__)


class KnowledgeEngine:
    """
    Main orchestrator for the Knowledge Engine.

    Cost tiers:
    - FREE (default): Ollama + Qdrant (self-hosted) + PostgreSQL (self-hosted)
    - GRAPH (+Neo4j): Enable graph_enabled=true
    - PREMIUM: Switch to Voyage AI, Cohere, Anthropic via env vars
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize Knowledge Engine with all components."""
        self._settings = settings or get_settings()

        # Core storage (always enabled)
        self._qdrant = QdrantStore(self._settings)
        self._postgres = PostgresStore(self._settings)

        # Optional graph storage
        self._neo4j = None
        if self._settings.graph_enabled:
            from knowledge_engine.storage.neo4j import Neo4jStore

            self._neo4j = Neo4jStore(self._settings)

        # AI services (default to Ollama = FREE)
        self._embeddings = EmbeddingService(self._settings)
        self._reranker = RerankerService(self._settings)
        self._llm = LLMService(self._settings)

        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all connections."""
        if self._initialized:
            return

        logger.info("Initializing Knowledge Engine...")
        logger.info("  Embedding provider: %s", self._settings.embedding_provider.value)
        logger.info("  Reranking: %s", self._settings.rerank_provider)
        logger.info("  LLM provider: %s", self._settings.llm_provider.value)
        logger.info("  Graph enabled: %s", self._settings.graph_enabled)

        # Connect to storage
        await self._qdrant.connect()
        await self._postgres.connect()

        if self._neo4j:
            await self._neo4j.connect()
            await self._neo4j.ensure_indexes()

        self._initialized = True
        logger.info("Knowledge Engine initialized (FREE tier)")

    async def close(self) -> None:
        """Close all connections."""
        await self._qdrant.close()
        await self._postgres.close()
        if self._neo4j:
            await self._neo4j.close()
        self._initialized = False
        logger.info("Knowledge Engine shutdown")

    async def health_check(self) -> dict[str, bool]:
        """Check health of all components."""
        health = {
            "qdrant": await self._qdrant.health_check(),
            "postgres": await self._postgres.health_check(),
        }
        if self._neo4j:
            health["neo4j"] = await self._neo4j.health_check()
        return health

    # ============================================================
    # INGESTION
    # ============================================================

    async def ingest_document(
        self,
        doc: DocumentCreate,
    ) -> Document:
        """
        Ingest a document into the knowledge base.

        Pipeline:
        1. Chunk the document
        2. Generate embeddings (Ollama by default = FREE)
        3. Store vectors in Qdrant (self-hosted = FREE)
        4. Store metadata in PostgreSQL (self-hosted = FREE)
        5. (Optional) Extract entities to Neo4j if graph_enabled
        """
        await self.initialize()

        doc_id = uuid4()
        start_time = time.time()

        # Chunk the document
        chunks = self._chunk_text(doc.content)
        logger.info("Document chunked into %d segments", len(chunks))

        # Generate embeddings (FREE with Ollama)
        embeddings = await self._embeddings.embed_documents(chunks)

        # Store vectors in Qdrant (FREE, self-hosted)
        points = [
            {
                "id": uuid4(),
                "vector": embedding,
                "payload": {
                    "document_id": str(doc_id),
                    "chunk_index": i,
                    "content": chunk,
                    "document_type": doc.document_type.value,
                    "title": doc.title,
                    "source": doc.metadata.source,
                },
            }
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        await self._qdrant.upsert_batch(points, namespace=doc.namespace)

        # Store in Neo4j if enabled
        if self._neo4j:
            await self._neo4j.create_entity(
                entity_type="Document",
                name=doc.title or str(doc_id),
                properties={
                    "document_id": str(doc_id),
                    "document_type": doc.document_type.value,
                    "source": doc.metadata.source,
                },
                namespace=doc.namespace,
            )

        # Store metadata in PostgreSQL (FREE, self-hosted)
        await self._postgres.save_document(
            id=doc_id,
            namespace=doc.namespace,
            title=doc.title,
            document_type=doc.document_type.value,
            source=doc.metadata.source,
            chunk_count=len(chunks),
            embedding_model=self._embeddings.model_name,
            metadata=doc.metadata.custom,
        )

        # Store chunks in PostgreSQL for BM25 search (FREE)
        chunk_records = [
            {
                "id": point["id"],
                "chunk_index": point["payload"]["chunk_index"],
                "content": point["payload"]["content"],
                "title": doc.title,
            }
            for point in points
        ]
        await self._postgres.save_chunks(doc_id, doc.namespace, chunk_records)

        elapsed = time.time() - start_time
        logger.info(
            "Ingested document %s (%d chunks) in %.2fs using %s",
            doc_id,
            len(chunks),
            elapsed,
            self._embeddings.model_name,
        )

        return Document(
            id=doc_id,
            content=doc.content,
            title=doc.title,
            document_type=doc.document_type,
            namespace=doc.namespace,
            metadata=doc.metadata,
            chunk_count=len(chunks),
            embedding_model=self._embeddings.model_name,
        )

    def _chunk_text(self, text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
        """Simple text chunking with sentence boundary detection."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        min_chunk_size = overlap + 10  # Minimum progress per iteration

        while start < len(text):
            end = min(start + chunk_size, len(text))

            # Only look for sentence boundary if we're not at the end
            if end < len(text):
                for sep in [". ", ".\n", "\n\n", "\n"]:
                    boundary = text.rfind(sep, start, end)
                    # Only use boundary if it gives us a reasonable chunk size
                    if boundary > start + min_chunk_size:
                        end = boundary + len(sep)
                        break

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Ensure we always make progress (at least 1 character)
            new_start = max(start + 1, end - overlap)
            # But don't go backwards
            start = max(new_start, start + min_chunk_size)

            # Safety check: if we're not making progress, force it
            if start <= (end - overlap) and start < len(text):
                start = end

        return chunks

    # ============================================================
    # SEARCH
    # ============================================================

    async def search(
        self,
        request: HybridSearchRequest,
    ) -> SearchResult:
        """
        Perform hybrid search with RRF fusion.

        Pipeline:
        1. Generate query embedding (FREE with Ollama)
        2. Vector search in Qdrant (FREE, self-hosted)
        3. BM25 search in PostgreSQL (FREE, self-hosted)
        4. Combine with Reciprocal Rank Fusion
        5. (Optional) Graph traversal in Neo4j
        6. Rerank results (FREE with Ollama)
        """
        await self.initialize()

        start_time = time.time()

        # Generate query embedding (FREE)
        query_embedding = await self._embeddings.embed_query(request.query)

        # Vector search (FREE)
        vector_start = time.time()
        vector_results = await self._qdrant.search(
            query_vector=query_embedding,
            namespace=request.namespace,
            limit=self._settings.search_vector_candidates,
            filters=self._build_qdrant_filters(request.filters) if request.filters else None,
        )
        vector_time = (time.time() - vector_start) * 1000

        # BM25 search (FREE)
        bm25_start = time.time()
        try:
            bm25_results = await self._postgres.bm25_search(
                query=request.query,
                namespace=request.namespace,
                limit=self._settings.search_bm25_candidates,
            )
        except Exception as e:
            logger.warning("BM25 search failed: %s", e)
            bm25_results = []
        bm25_time = (time.time() - bm25_start) * 1000

        # Graph search (optional)
        graph_time: float | None = None
        if request.include_graph and self._neo4j:
            graph_start = time.time()
            # TODO: Extract entities from query and traverse
            graph_time = (time.time() - graph_start) * 1000

        # Combine results using RRF fusion
        combined = self._combine_with_rrf(vector_results, bm25_results)

        # Rerank (FREE with Ollama)
        rerank_time: float | None = None
        if request.rerank and combined and self._reranker.enabled:
            rerank_start = time.time()
            combined = await self._reranker.rerank_with_metadata(
                query=request.query,
                items=combined,
                text_key="content",
                top_n=request.limit,
            )
            rerank_time = (time.time() - rerank_start) * 1000

        # Build response
        items = [
            SearchResultItem(
                document_id=UUID(r["document_id"]),
                chunk_id=UUID(r["id"]) if "id" in r else None,
                title=r.get("title"),
                content=r["content"],
                document_type=r.get("document_type", "text"),
                namespace=request.namespace,
                score=r.get("rerank_score", r.get("rrf_score", r.get("score", 0.0))),
                vector_score=r.get("vector_score"),
                bm25_score=r.get("bm25_score"),
                rerank_score=r.get("rerank_score"),
                source=r.get("source"),
            )
            for r in combined[: request.limit]
        ]

        total_time = (time.time() - start_time) * 1000

        return SearchResult(
            query=request.query,
            namespace=request.namespace,
            total_results=len(items),
            items=items,
            search_time_ms=total_time,
            vector_search_time_ms=vector_time,
            graph_search_time_ms=graph_time,
            rerank_time_ms=rerank_time,
        )

    def _build_qdrant_filters(self, filters: Any) -> dict[str, Any] | None:
        """Convert search filters to Qdrant filter format."""
        if not filters:
            return None
        qdrant_filters: dict[str, Any] = {}
        if filters.document_types:
            qdrant_filters["document_type"] = [t.value for t in filters.document_types]
        return qdrant_filters if qdrant_filters else None

    def _combine_results(
        self,
        vector_results: list[dict[str, Any]],
        graph_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Combine vector and graph results."""
        combined: dict[str, dict[str, Any]] = {}

        for rank, result in enumerate(vector_results, 1):
            doc_id = result["payload"]["document_id"]
            if doc_id not in combined:
                combined[doc_id] = {
                    "id": result["id"],
                    "document_id": doc_id,
                    "content": result["payload"]["content"],
                    "title": result["payload"].get("title"),
                    "document_type": result["payload"].get("document_type"),
                    "source": result["payload"].get("source"),
                    "score": result["score"],
                    "vector_rank": rank,
                }
            else:
                combined[doc_id]["score"] = max(combined[doc_id]["score"], result["score"])

        return sorted(combined.values(), key=lambda x: x["score"], reverse=True)

    def _combine_with_rrf(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Combine vector and BM25 results using Reciprocal Rank Fusion.

        RRF is robust to different score scales between search methods.
        """
        # Convert vector results to standard format
        vector_items = []
        for result in vector_results:
            vector_items.append({
                "id": result["id"],
                "document_id": result["payload"]["document_id"],
                "content": result["payload"]["content"],
                "title": result["payload"].get("title"),
                "document_type": result["payload"].get("document_type"),
                "source": result["payload"].get("source"),
                "vector_score": result["score"],
            })

        # Convert BM25 results to standard format
        bm25_items = []
        for result in bm25_results:
            bm25_items.append({
                "id": result["id"],
                "document_id": result["document_id"],
                "content": result["content"],
                "title": result.get("title"),
                "bm25_score": result["score"],
            })

        # Use RRF to combine
        combined = reciprocal_rank_fusion(
            [vector_items, bm25_items],
            id_key="id",
            k=self._settings.search_rrf_k,
        )

        return combined

    # ============================================================
    # QUERY (RAG)
    # ============================================================

    async def query(
        self,
        request: QueryRequest,
    ) -> QueryResponse:
        """
        Perform RAG query with confidence scoring.

        Note: LLM generation requires Anthropic API key or Ollama.
        Default returns search results without generation.
        """
        await self.initialize()

        start_time = time.time()

        # Search for context
        search_request = HybridSearchRequest(
            query=request.question,
            namespace=request.namespace,
            limit=request.max_sources,
            rerank=True,
            include_graph=self._settings.graph_enabled,
        )
        search_result = await self.search(search_request)
        search_time = search_result.search_time_ms

        # Build context chunks for LLM
        context_chunks = [
            {
                "content": item.content,
                "title": item.title,
                "document_id": str(item.document_id),
                "score": item.score,
            }
            for item in search_result.items
        ]

        # Build citations
        citations: list[Citation] = []
        for i, item in enumerate(search_result.items):
            if request.include_citations:
                citations.append(
                    Citation(
                        document_id=item.document_id,
                        chunk_id=item.chunk_id,
                        title=item.title,
                        content=item.content[:500],
                        source=item.source,
                        relevance_score=item.score,
                    )
                )

        # Generate answer with LLM (FREE with Ollama)
        gen_start = time.time()
        try:
            answer, cited_indices = await self._llm.generate_rag_answer(
                question=request.question,
                context_chunks=context_chunks,
            )
        except Exception as e:
            logger.warning("LLM generation failed, using fallback: %s", e)
            answer = self._generate_simple_answer(
                request.question,
                [f"[{i+1}] {c['content']}" for i, c in enumerate(context_chunks)]
            )
        generation_time = (time.time() - gen_start) * 1000

        # Calculate confidence
        avg_score = (
            sum(item.score for item in search_result.items) / len(search_result.items)
            if search_result.items
            else 0.0
        )

        if avg_score >= 0.7:
            confidence = ConfidenceLevel.HIGH
        elif avg_score >= 0.4:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW

        total_time = (time.time() - start_time) * 1000

        return QueryResponse(
            question=request.question,
            answer=answer,
            namespace=request.namespace,
            confidence=confidence,
            confidence_score=avg_score,
            confidence_reason=f"Based on {len(search_result.items)} sources",
            citations=citations,
            model_used=self._llm.model_name,
            search_time_ms=search_time,
            generation_time_ms=generation_time,
            total_time_ms=total_time,
        )

    def _generate_simple_answer(self, question: str, context_parts: list[str]) -> str:
        """Generate a simple answer without LLM (placeholder)."""
        if not context_parts:
            return "I couldn't find relevant information to answer your question."

        # Return the most relevant context
        return f"Based on the retrieved information:\n\n{context_parts[0]}"

    # ============================================================
    # MEMORY
    # ============================================================

    async def store_memory(
        self,
        memory: MemoryCreate,
    ) -> Memory:
        """Store a memory for later recall."""
        await self.initialize()

        memory_id = uuid4()

        # Generate embedding (FREE)
        embedding = await self._embeddings.embed_text(memory.content)

        # Store in Qdrant (FREE)
        await self._qdrant.upsert(
            id=memory_id,
            vector=embedding,
            payload={
                "memory_id": str(memory_id),
                "content": memory.content,
                "memory_type": memory.memory_type.value,
                "context": memory.context,
                "source": memory.source,
                "importance": memory.importance,
                "tags": memory.tags,
            },
            namespace=memory.namespace,
        )

        # Store in Neo4j if enabled
        if self._neo4j:
            await self._neo4j.create_entity(
                entity_type="Memory",
                name=str(memory_id),
                properties={
                    "content_preview": memory.content[:200],
                    "memory_type": memory.memory_type.value,
                    "importance": memory.importance,
                },
                namespace=memory.namespace,
            )

        # Store metadata in PostgreSQL (FREE)
        await self._postgres.save_memory(
            id=memory_id,
            namespace=memory.namespace,
            content=memory.content,
            memory_type=memory.memory_type.value,
            context=memory.context,
            source=memory.source,
            importance=memory.importance,
            tags=memory.tags,
            metadata=memory.metadata,
            expires_at=memory.expires_at,
        )

        logger.info("Stored memory %s", memory_id)

        return Memory(
            id=memory_id,
            content=memory.content,
            memory_type=memory.memory_type,
            namespace=memory.namespace,
            context=memory.context,
            source=memory.source,
            importance=memory.importance,
            tags=memory.tags,
            metadata=memory.metadata,
            expires_at=memory.expires_at,
        )

    async def recall_memories(
        self,
        query: str,
        namespace: str = "default",
        limit: int = 10,
    ) -> list[Memory]:
        """Recall memories relevant to query."""
        await self.initialize()

        # Generate query embedding (FREE)
        query_embedding = await self._embeddings.embed_query(query)

        # Search Qdrant (FREE)
        results = await self._qdrant.search(
            query_vector=query_embedding,
            namespace=namespace,
            limit=limit,
        )

        memories = []
        for result in results:
            memory_id = UUID(result["payload"]["memory_id"])
            memory_data = await self._postgres.get_memory(memory_id, namespace)
            if memory_data:
                memories.append(
                    Memory(
                        id=memory_data["id"],
                        content=memory_data["content"],
                        memory_type=memory_data["memory_type"],
                        namespace=namespace,
                        context=memory_data.get("context"),
                        source=memory_data.get("source"),
                        importance=memory_data["importance"],
                        tags=memory_data.get("tags", []),
                        metadata=memory_data.get("metadata", {}),
                        created_at=memory_data["created_at"],
                        updated_at=memory_data["updated_at"],
                        accessed_at=memory_data.get("accessed_at"),
                        access_count=memory_data.get("access_count", 0),
                    )
                )

        return memories

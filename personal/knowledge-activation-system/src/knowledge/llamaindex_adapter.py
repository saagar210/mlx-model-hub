"""LlamaIndex adapter for Knowledge Activation System.

Provides custom vector store and retriever implementations that wrap
our existing pgvector setup and hybrid search functionality.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.callbacks.base import CallbackManager
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryResult,
)

from knowledge.db import Database, get_db
from knowledge.embeddings import embed_text
from knowledge.search import rrf_fusion


class KnowledgeVectorStore(BasePydanticVectorStore):
    """Custom vector store adapter for existing chunks/content tables.

    This is a read-only adapter that queries our existing PostgreSQL
    database with pgvector embeddings. It doesn't implement add() or delete()
    since we manage content through the CLI ingest commands.
    """

    stores_text: bool = True
    is_embedding_query: bool = True

    _db: Database | None = PrivateAttr(default=None)

    def __init__(self, db: Database | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._db = db

    @property
    def client(self) -> Database | None:
        """Return the database client."""
        return self._db

    async def _ensure_db(self) -> Database:
        """Ensure database connection is available."""
        if self._db is None:
            self._db = await get_db()
        return self._db

    def add(self, nodes: list[TextNode], **kwargs: Any) -> list[str]:  # type: ignore[override]
        """Not implemented - use CLI ingest commands instead."""
        raise NotImplementedError(
            "Use 'python cli.py ingest' commands to add content. "
            "This adapter is read-only."
        )

    def delete(self, ref_doc_id: str, **kwargs: Any) -> None:
        """Not implemented - use CLI or database directly."""
        raise NotImplementedError(
            "Use CLI or database directly to delete content. "
            "This adapter is read-only."
        )

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        """Synchronous query - wraps async implementation."""
        return asyncio.get_event_loop().run_until_complete(
            self.aquery(query, **kwargs)
        )

    async def aquery(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> VectorStoreQueryResult:
        """Query existing chunks table with vector similarity.

        Args:
            query: VectorStoreQuery with embedding and parameters

        Returns:
            VectorStoreQueryResult with matching nodes and scores
        """
        db = await self._ensure_db()

        if query.query_embedding is None:
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])

        limit = query.similarity_top_k or 10

        # Query our chunks table directly
        sql = """
        SELECT c.id, c.chunk_text, c.source_ref, c.content_id,
               ct.title, ct.type,
               1 - (c.embedding <=> $1::vector) as similarity
        FROM chunks c
        JOIN content ct ON c.content_id = ct.id
        WHERE ct.deleted_at IS NULL
        ORDER BY c.embedding <=> $1::vector
        LIMIT $2
        """

        async with db.acquire() as conn:
            rows = await conn.fetch(sql, query.query_embedding, limit)

        nodes = []
        similarities = []
        ids = []

        for row in rows:
            # Create TextNode with metadata
            node = TextNode(
                text=row["chunk_text"],
                id_=str(row["id"]),
                metadata={
                    "content_id": str(row["content_id"]),
                    "title": row["title"],
                    "type": row["type"],
                    "source_ref": row["source_ref"],
                },
            )
            nodes.append(node)
            similarities.append(float(row["similarity"]))
            ids.append(str(row["id"]))

        return VectorStoreQueryResult(
            nodes=nodes,
            similarities=similarities,
            ids=ids,
        )


class HybridKnowledgeRetriever(BaseRetriever):
    """Hybrid retriever using our existing RRF fusion implementation.

    This wraps our battle-tested hybrid search (BM25 + vector with RRF)
    and exposes it through the LlamaIndex retriever interface.
    """

    def __init__(
        self,
        similarity_top_k: int = 10,
        bm25_candidates: int = 50,
        vector_candidates: int = 50,
        rrf_k: int = 60,
        db: Database | None = None,
        callback_manager: CallbackManager | None = None,
    ) -> None:
        """Initialize hybrid retriever.

        Args:
            similarity_top_k: Number of final results to return
            bm25_candidates: Number of BM25 candidates for RRF
            vector_candidates: Number of vector candidates for RRF
            rrf_k: RRF constant (default 60)
            db: Optional database instance
            callback_manager: LlamaIndex callback manager
        """
        super().__init__(callback_manager=callback_manager)
        self._similarity_top_k = similarity_top_k
        self._bm25_candidates = bm25_candidates
        self._vector_candidates = vector_candidates
        self._rrf_k = rrf_k
        self._db = db

    async def _ensure_db(self) -> Database:
        """Ensure database connection is available."""
        if self._db is None:
            self._db = await get_db()
        return self._db

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        """Synchronous retrieve - wraps async implementation."""
        return asyncio.get_event_loop().run_until_complete(
            self._aretrieve(query_bundle)
        )

    async def _aretrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        """Retrieve using hybrid search with RRF fusion.

        Args:
            query_bundle: Query with text and optional embedding

        Returns:
            List of NodeWithScore objects
        """
        db = await self._ensure_db()
        query_text = query_bundle.query_str

        # Generate query embedding
        query_embedding = await embed_text(query_text)

        # Run BM25 and vector search
        bm25_results = await db.bm25_search(query_text, limit=self._bm25_candidates)
        vector_results = await db.vector_search(query_embedding, limit=self._vector_candidates)

        # Combine with RRF
        combined = rrf_fusion(bm25_results, vector_results, k=self._rrf_k)

        # Convert to LlamaIndex nodes
        nodes_with_scores = []
        for result in combined[: self._similarity_top_k]:
            node = TextNode(
                text=result.chunk_text or "",
                id_=str(result.content_id),
                metadata={
                    "title": result.title,
                    "type": result.content_type,
                    "bm25_rank": result.bm25_rank,
                    "vector_rank": result.vector_rank,
                    "source_ref": result.source_ref,
                },
            )
            nodes_with_scores.append(
                NodeWithScore(node=node, score=result.score)
            )

        return nodes_with_scores


@dataclass
class OllamaEmbeddingAdapter(BaseEmbedding):
    """Adapter to use our existing Ollama embedding function with LlamaIndex.

    This wraps our embed_text() function which calls Ollama with nomic-embed-text.
    """

    model_name: str = "nomic-embed-text"
    embed_batch_size: int = 10
    _callback_manager: CallbackManager = field(default_factory=CallbackManager)

    def __post_init__(self) -> None:
        """Initialize the embedding adapter."""
        pass

    @classmethod
    def class_name(cls) -> str:
        return "OllamaEmbeddingAdapter"

    def _get_query_embedding(self, query: str) -> list[float]:
        """Get embedding for a query synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._aget_query_embedding(query)
        )

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """Get embedding for a query asynchronously."""
        return await embed_text(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        """Get embedding for text synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._aget_text_embedding(text)
        )

    async def _aget_text_embedding(self, text: str) -> list[float]:
        """Get embedding for text asynchronously."""
        return await embed_text(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts synchronously."""
        return asyncio.get_event_loop().run_until_complete(
            self._aget_text_embeddings(texts)
        )

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts asynchronously."""
        # Process in batches
        embeddings = []
        for text in texts:
            embedding = await embed_text(text)
            embeddings.append(embedding)
        return embeddings


# Convenience functions for quick setup

async def get_knowledge_vector_store() -> KnowledgeVectorStore:
    """Get a configured KnowledgeVectorStore instance."""
    db = await get_db()
    return KnowledgeVectorStore(db=db)


async def get_hybrid_retriever(
    similarity_top_k: int = 10,
    bm25_candidates: int = 50,
    vector_candidates: int = 50,
) -> HybridKnowledgeRetriever:
    """Get a configured HybridKnowledgeRetriever instance."""
    db = await get_db()
    return HybridKnowledgeRetriever(
        similarity_top_k=similarity_top_k,
        bm25_candidates=bm25_candidates,
        vector_candidates=vector_candidates,
        db=db,
    )


def get_embedding_adapter() -> OllamaEmbeddingAdapter:
    """Get a configured OllamaEmbeddingAdapter instance."""
    return OllamaEmbeddingAdapter()

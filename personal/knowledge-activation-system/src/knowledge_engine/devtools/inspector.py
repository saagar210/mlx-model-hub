"""Data inspection tools for debugging and exploration."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingStats:
    """Statistics about an embedding vector."""

    dimensions: int
    min_value: float
    max_value: float
    mean: float
    std: float
    magnitude: float
    sparsity: float  # Percentage of near-zero values
    histogram: list[tuple[float, int]] = field(default_factory=list)


@dataclass
class SimilarityResult:
    """Result of similarity comparison."""

    score: float
    method: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkInfo:
    """Information about a document chunk."""

    chunk_id: str
    content: str
    word_count: int
    char_count: int
    position: int
    has_embedding: bool
    embedding_stats: EmbeddingStats | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentInfo:
    """Information about a document."""

    document_id: str
    title: str
    total_chunks: int
    total_words: int
    total_chars: int
    source: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[ChunkInfo] = field(default_factory=list)


@dataclass
class InspectionResult:
    """Result of data inspection."""

    type: str
    summary: dict[str, Any]
    details: Any = None
    warnings: list[str] = field(default_factory=list)


class Inspector:
    """
    Data inspection toolkit.

    Features:
    - Document structure analysis
    - Embedding vector inspection
    - Similarity debugging
    - Data quality checks
    """

    def __init__(self, db_connection: Any = None):
        """
        Initialize inspector.

        Args:
            db_connection: Optional database connection for data access
        """
        self.db = db_connection

    async def inspect_document(
        self,
        document_id: str,
        include_chunks: bool = True,
        include_embeddings: bool = False,
    ) -> DocumentInfo:
        """
        Inspect a document's structure and contents.

        Args:
            document_id: Document ID to inspect
            include_chunks: Whether to include chunk details
            include_embeddings: Whether to include embedding stats

        Returns:
            DocumentInfo with document details
        """
        if not self.db:
            raise ValueError("Database connection required for document inspection")

        # Fetch document
        doc = await self.db.fetchrow(
            """
            SELECT id, title, source_url, created_at, metadata
            FROM documents
            WHERE id = $1
            """,
            document_id,
        )

        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        # Fetch chunk stats
        stats = await self.db.fetchrow(
            """
            SELECT
                COUNT(*) as chunk_count,
                SUM(LENGTH(content)) as total_chars
            FROM chunks
            WHERE document_id = $1
            """,
            document_id,
        )

        info = DocumentInfo(
            document_id=document_id,
            title=doc["title"] or "Untitled",
            total_chunks=stats["chunk_count"] or 0,
            total_words=0,  # Will be calculated from chunks
            total_chars=stats["total_chars"] or 0,
            source=doc["source_url"],
            created_at=str(doc["created_at"]) if doc["created_at"] else None,
            metadata=doc["metadata"] or {},
        )

        if include_chunks:
            chunks = await self.db.fetch(
                """
                SELECT id, content, position, metadata
                FROM chunks
                WHERE document_id = $1
                ORDER BY position
                """,
                document_id,
            )

            total_words = 0
            for chunk in chunks:
                word_count = len(chunk["content"].split())
                total_words += word_count

                chunk_info = ChunkInfo(
                    chunk_id=str(chunk["id"]),
                    content=chunk["content"][:200] + "..."
                    if len(chunk["content"]) > 200
                    else chunk["content"],
                    word_count=word_count,
                    char_count=len(chunk["content"]),
                    position=chunk["position"],
                    has_embedding=False,  # TODO: Check embeddings table
                    metadata=chunk["metadata"] or {},
                )

                if include_embeddings:
                    # TODO: Fetch and analyze embedding
                    pass

                info.chunks.append(chunk_info)

            info.total_words = total_words

        return info

    def inspect_embedding(
        self,
        embedding: list[float] | np.ndarray,
    ) -> EmbeddingStats:
        """
        Inspect an embedding vector.

        Args:
            embedding: The embedding vector

        Returns:
            EmbeddingStats with vector statistics
        """
        if isinstance(embedding, list):
            embedding = np.array(embedding)

        # Basic stats
        dimensions = len(embedding)
        min_val = float(np.min(embedding))
        max_val = float(np.max(embedding))
        mean = float(np.mean(embedding))
        std = float(np.std(embedding))
        magnitude = float(np.linalg.norm(embedding))

        # Sparsity (values close to zero)
        near_zero = np.sum(np.abs(embedding) < 0.01)
        sparsity = near_zero / dimensions * 100

        # Histogram
        hist, bin_edges = np.histogram(embedding, bins=20)
        histogram = [
            (float(bin_edges[i]), int(hist[i])) for i in range(len(hist))
        ]

        return EmbeddingStats(
            dimensions=dimensions,
            min_value=min_val,
            max_value=max_val,
            mean=mean,
            std=std,
            magnitude=magnitude,
            sparsity=sparsity,
            histogram=histogram,
        )

    def compare_embeddings(
        self,
        embedding1: list[float] | np.ndarray,
        embedding2: list[float] | np.ndarray,
    ) -> list[SimilarityResult]:
        """
        Compare two embeddings using multiple similarity measures.

        Args:
            embedding1: First embedding
            embedding2: Second embedding

        Returns:
            List of similarity results for different measures
        """
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)

        results = []

        # Cosine similarity
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        cosine_sim = dot_product / (norm1 * norm2) if norm1 * norm2 > 0 else 0

        results.append(
            SimilarityResult(
                score=float(cosine_sim),
                method="cosine",
                details={
                    "dot_product": float(dot_product),
                    "norm1": float(norm1),
                    "norm2": float(norm2),
                },
            )
        )

        # Euclidean distance (converted to similarity)
        euclidean_dist = np.linalg.norm(embedding1 - embedding2)
        euclidean_sim = 1 / (1 + euclidean_dist)

        results.append(
            SimilarityResult(
                score=float(euclidean_sim),
                method="euclidean",
                details={"distance": float(euclidean_dist)},
            )
        )

        # Manhattan distance
        manhattan_dist = np.sum(np.abs(embedding1 - embedding2))
        manhattan_sim = 1 / (1 + manhattan_dist)

        results.append(
            SimilarityResult(
                score=float(manhattan_sim),
                method="manhattan",
                details={"distance": float(manhattan_dist)},
            )
        )

        # Inner product
        results.append(
            SimilarityResult(
                score=float(dot_product),
                method="inner_product",
            )
        )

        return results

    def analyze_chunk_distribution(
        self,
        chunks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Analyze the distribution of chunks.

        Args:
            chunks: List of chunk dictionaries with 'content' key

        Returns:
            Analysis of chunk distribution
        """
        if not chunks:
            return {"error": "No chunks provided"}

        word_counts = []
        char_counts = []

        for chunk in chunks:
            content = chunk.get("content", "")
            word_counts.append(len(content.split()))
            char_counts.append(len(content))

        word_array = np.array(word_counts)
        char_array = np.array(char_counts)

        return {
            "total_chunks": len(chunks),
            "words": {
                "total": int(np.sum(word_array)),
                "mean": float(np.mean(word_array)),
                "std": float(np.std(word_array)),
                "min": int(np.min(word_array)),
                "max": int(np.max(word_array)),
                "median": float(np.median(word_array)),
            },
            "chars": {
                "total": int(np.sum(char_array)),
                "mean": float(np.mean(char_array)),
                "std": float(np.std(char_array)),
                "min": int(np.min(char_array)),
                "max": int(np.max(char_array)),
                "median": float(np.median(char_array)),
            },
            "uniformity": {
                "word_cv": float(np.std(word_array) / np.mean(word_array))
                if np.mean(word_array) > 0
                else 0,
                "char_cv": float(np.std(char_array) / np.mean(char_array))
                if np.mean(char_array) > 0
                else 0,
            },
        }

    def check_data_quality(
        self,
        data: dict[str, Any],
        data_type: str = "document",
    ) -> InspectionResult:
        """
        Check data quality and identify issues.

        Args:
            data: Data to check
            data_type: Type of data (document, chunk, embedding)

        Returns:
            InspectionResult with quality assessment
        """
        warnings: list[str] = []
        summary: dict[str, Any] = {}

        if data_type == "document":
            # Check document quality
            title = data.get("title", "")
            if not title:
                warnings.append("Document has no title")
            elif len(title) < 3:
                warnings.append("Document title is very short")

            chunks = data.get("chunks", [])
            if not chunks:
                warnings.append("Document has no chunks")
            elif len(chunks) == 1:
                warnings.append("Document has only one chunk")

            content_length = sum(len(c.get("content", "")) for c in chunks)
            if content_length < 100:
                warnings.append("Document has very little content")

            summary = {
                "has_title": bool(title),
                "chunk_count": len(chunks),
                "content_length": content_length,
            }

        elif data_type == "chunk":
            content = data.get("content", "")
            if not content:
                warnings.append("Chunk has no content")
            elif len(content) < 50:
                warnings.append("Chunk content is very short")
            elif len(content) > 5000:
                warnings.append("Chunk content is very long")

            # Check for common issues
            if content.strip() != content:
                warnings.append("Chunk has leading/trailing whitespace")
            if "\n\n\n" in content:
                warnings.append("Chunk has excessive newlines")

            summary = {
                "length": len(content),
                "word_count": len(content.split()),
            }

        elif data_type == "embedding":
            embedding = data.get("embedding", [])
            if not embedding:
                warnings.append("No embedding provided")
            else:
                stats = self.inspect_embedding(embedding)
                if stats.magnitude < 0.1:
                    warnings.append("Embedding magnitude is very low")
                if stats.sparsity > 50:
                    warnings.append("Embedding is very sparse")
                if not math.isfinite(stats.mean):
                    warnings.append("Embedding contains non-finite values")

                summary = {
                    "dimensions": stats.dimensions,
                    "magnitude": stats.magnitude,
                    "sparsity": stats.sparsity,
                }

        return InspectionResult(
            type=data_type,
            summary=summary,
            warnings=warnings,
        )


# Convenience functions
async def inspect_document(
    document_id: str,
    db_connection: Any,
    **kwargs: Any,
) -> DocumentInfo:
    """Inspect a document."""
    inspector = Inspector(db_connection)
    return await inspector.inspect_document(document_id, **kwargs)


def inspect_embeddings(
    embedding: list[float] | np.ndarray,
) -> EmbeddingStats:
    """Inspect an embedding vector."""
    inspector = Inspector()
    return inspector.inspect_embedding(embedding)

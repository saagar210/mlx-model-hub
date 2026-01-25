"""Qdrant vector database adapter."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient, models
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_engine.config import Settings, get_settings

logger = logging.getLogger(__name__)


class QdrantStore:
    """Qdrant vector database adapter with multi-tenancy support."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize Qdrant connection."""
        self._settings = settings or get_settings()
        self._client: AsyncQdrantClient | None = None

    async def connect(self) -> None:
        """Establish connection to Qdrant."""
        if self._client is not None:
            return

        api_key = (
            self._settings.qdrant_api_key.get_secret_value()
            if self._settings.qdrant_api_key
            else None
        )

        self._client = AsyncQdrantClient(
            url=self._settings.qdrant_url,
            api_key=api_key,
            timeout=30,
        )
        logger.info("Connected to Qdrant at %s", self._settings.qdrant_url)

    async def close(self) -> None:
        """Close Qdrant connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from Qdrant")

    def _collection_name(self, namespace: str, suffix: str = "chunks") -> str:
        """Generate collection name with namespace prefix."""
        prefix = self._settings.qdrant_collection_prefix
        return f"{prefix}_{namespace}_{suffix}"

    async def ensure_collection(
        self,
        namespace: str = "default",
        suffix: str = "chunks",
        vector_size: int | None = None,
    ) -> None:
        """Ensure collection exists with proper configuration."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace, suffix)
        size = vector_size or self._settings.embedding_dimensions

        try:
            await self._client.get_collection(collection_name)
            logger.debug("Collection %s already exists", collection_name)
        except Exception:
            # Collection doesn't exist, create it
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=size,
                    distance=models.Distance.COSINE,
                    on_disk=True,  # Use disk for large collections
                ),
                # Hybrid search with sparse vectors
                sparse_vectors_config={
                    "text": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=True),
                    ),
                },
                # Quantization for storage efficiency
                quantization_config=models.ScalarQuantization(
                    scalar=models.ScalarQuantizationConfig(
                        type=models.ScalarType.INT8,
                        quantile=0.99,
                        always_ram=True,
                    ),
                ),
                # HNSW index configuration
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    on_disk=True,
                ),
            )
            logger.info("Created collection %s with size %d", collection_name, size)

            # Create payload indexes for filtering
            await self._client.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=collection_name,
                field_name="document_type",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            await self._client.create_payload_index(
                collection_name=collection_name,
                field_name="created_at",
                field_schema=models.PayloadSchemaType.DATETIME,
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def upsert(
        self,
        id: UUID,
        vector: list[float],
        payload: dict[str, Any],
        namespace: str = "default",
        sparse_vector: dict[int, float] | None = None,
    ) -> None:
        """Upsert a single vector with payload."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)
        await self.ensure_collection(namespace)

        point = models.PointStruct(
            id=str(id),
            vector={
                "": vector,  # Default dense vector
                **({"text": sparse_vector} if sparse_vector else {}),
            }
            if sparse_vector
            else vector,
            payload=payload,
        )

        await self._client.upsert(
            collection_name=collection_name,
            points=[point],
            wait=True,
        )

    async def upsert_batch(
        self,
        points: list[dict[str, Any]],
        namespace: str = "default",
        batch_size: int = 100,
    ) -> int:
        """Batch upsert vectors."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)
        await self.ensure_collection(namespace)

        total = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            qdrant_points = [
                models.PointStruct(
                    id=str(p["id"]),
                    vector=p["vector"],
                    payload=p["payload"],
                )
                for p in batch
            ]
            await self._client.upsert(
                collection_name=collection_name,
                points=qdrant_points,
                wait=True,
            )
            total += len(batch)
            logger.debug("Upserted batch %d-%d", i, i + len(batch))

        return total

    async def search(
        self,
        query_vector: list[float],
        namespace: str = "default",
        limit: int = 10,
        score_threshold: float | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)

        # Build filter conditions
        filter_conditions = None
        if filters:
            must_conditions = []
            for key, value in filters.items():
                if isinstance(value, list):
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchAny(any=value),
                        )
                    )
                else:
                    must_conditions.append(
                        models.FieldCondition(
                            key=key,
                            match=models.MatchValue(value=value),
                        )
                    )
            if must_conditions:
                filter_conditions = models.Filter(must=must_conditions)

        results = await self._client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            score_threshold=score_threshold,
            query_filter=filter_conditions,
            with_payload=True,
        )

        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload,
            }
            for point in results.points
        ]

    async def hybrid_search(
        self,
        query_vector: list[float],
        sparse_vector: dict[int, float],
        namespace: str = "default",
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid search combining dense and sparse vectors."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)

        # Build filter conditions
        filter_conditions = None
        if filters:
            must_conditions = [
                models.FieldCondition(key=k, match=models.MatchValue(value=v))
                for k, v in filters.items()
            ]
            filter_conditions = models.Filter(must=must_conditions)

        results = await self._client.query_points(
            collection_name=collection_name,
            prefetch=[
                models.Prefetch(
                    query=query_vector,
                    using="",  # Dense vector
                    limit=limit * 2,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=list(sparse_vector.keys()),
                        values=list(sparse_vector.values()),
                    ),
                    using="text",  # Sparse vector
                    limit=limit * 2,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            query_filter=filter_conditions,
            with_payload=True,
        )

        return [
            {
                "id": result.id,
                "score": result.score,
                "payload": result.payload,
            }
            for result in results.points
        ]

    async def delete(
        self,
        ids: list[UUID],
        namespace: str = "default",
    ) -> int:
        """Delete vectors by ID."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)

        await self._client.delete(
            collection_name=collection_name,
            points_selector=models.PointIdsList(
                points=[str(id) for id in ids],
            ),
        )
        return len(ids)

    async def delete_by_filter(
        self,
        filters: dict[str, Any],
        namespace: str = "default",
    ) -> None:
        """Delete vectors matching filter conditions."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)

        must_conditions = [
            models.FieldCondition(key=k, match=models.MatchValue(value=v))
            for k, v in filters.items()
        ]

        await self._client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(must=must_conditions),
            ),
        )

    async def get_collection_info(self, namespace: str = "default") -> dict[str, Any]:
        """Get collection statistics."""
        if self._client is None:
            await self.connect()
        assert self._client is not None

        collection_name = self._collection_name(namespace)

        try:
            info = await self._client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value,
                "config": {
                    "vector_size": info.config.params.vectors.size
                    if hasattr(info.config.params.vectors, "size")
                    else None,
                },
            }
        except Exception as e:
            logger.warning("Collection %s not found: %s", collection_name, e)
            return {"name": collection_name, "exists": False}

    async def health_check(self) -> bool:
        """Check Qdrant connection health."""
        try:
            if self._client is None:
                await self.connect()
            assert self._client is not None
            await self._client.get_collections()
            return True
        except Exception as e:
            logger.error("Qdrant health check failed: %s", e)
            return False

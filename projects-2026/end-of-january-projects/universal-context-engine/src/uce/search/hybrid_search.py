"""
Hybrid search engine combining vector, BM25, and graph search.
"""

import time
from datetime import datetime, timedelta
from uuid import UUID

import asyncpg
import httpx

from ..models.context_item import ContextItem, BiTemporalMetadata, RelevanceSignals
from ..models.search import SearchQuery, SearchResult, SearchResponse
from .vector_search import VectorSearch
from .bm25_search import BM25Search
from .graph_search import GraphSearch
from .ranking import RankingEngine


class HybridSearchEngine:
    """
    Hybrid search combining vector similarity, BM25 full-text, and graph traversal.

    Uses Reciprocal Rank Fusion (RRF) to combine results from multiple methods.
    """

    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        rrf_k: int = 60,
        decay_half_life_hours: int = 168,
    ) -> None:
        """
        Initialize hybrid search engine.

        Args:
            pg_pool: PostgreSQL connection pool
            ollama_url: Ollama API URL for embeddings
            embedding_model: Embedding model name
            rrf_k: RRF constant
            decay_half_life_hours: Temporal decay half-life
        """
        self.pg = pg_pool
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model

        # Initialize search components
        self.vector_search = VectorSearch(pg_pool)
        self.bm25_search = BM25Search(pg_pool)
        self.graph_search = GraphSearch(pg_pool)
        self.ranker = RankingEngine(rrf_k, decay_half_life_hours)

    async def search(
        self,
        query: SearchQuery,
        limit: int = 20,
        rerank: bool = True,
    ) -> SearchResponse:
        """
        Execute hybrid search.

        Args:
            query: Search query with filters
            limit: Maximum results
            rerank: Whether to apply reranking

        Returns:
            SearchResponse with ranked results
        """
        start_time = time.time()

        # Generate query embedding
        query_embedding = await self._embed(query.query)

        # Prepare filters
        source_filter = list(query.sources) if query.sources else None
        type_filter = list(query.content_types) if query.content_types else None

        # Execute parallel searches
        candidate_limit = limit * 3

        vector_results = await self.vector_search.search(
            embedding=query_embedding,
            limit=candidate_limit,
            source_filter=source_filter,
            type_filter=type_filter,
            namespace=query.namespace,
        )

        bm25_results = await self.bm25_search.search(
            query=query.query,
            limit=candidate_limit,
            source_filter=source_filter,
            type_filter=type_filter,
            namespace=query.namespace,
        )

        # Entity-based search if entities specified
        entity_results = []
        if query.entities:
            entity_results = await self.graph_search.search_by_entities(
                entity_names=list(query.entities),
                require_all=False,
                limit=candidate_limit,
            )

        # RRF fusion
        result_lists = [vector_results, bm25_results]
        if entity_results:
            result_lists.append(entity_results)

        fused = self.ranker.rrf_fusion(*result_lists)

        # Apply temporal filter if specified
        if query.since:
            fused = await self._filter_by_time(fused, query.since, query.until)

        # Apply temporal decay
        timestamps = await self._get_timestamps([r["id"] for r in fused])
        fused = self.ranker.apply_temporal_decay(fused, timestamps)

        # Apply source weights
        sources = await self._get_sources([r["id"] for r in fused])
        source_weights = {
            "kas": 0.9,
            "git": 0.75,
            "browser": 0.6,
            "manual": 0.85,
        }
        fused = self.ranker.apply_source_weights(fused, source_weights, sources)

        # Sort and limit
        fused = self.ranker.rank(fused, top_k=limit * 2 if rerank else limit)

        # Normalize scores
        fused = self.ranker.normalize_scores(fused)

        # Take top results
        top_results = fused[:limit]

        # Convert to response
        items = []
        for r in top_results:
            item = await self._fetch_item(r["id"])
            if item:
                items.append(SearchResult(
                    item=item,
                    score=r["score"],
                    match_type=r.get("match_type", "hybrid"),
                ))

        search_time = (time.time() - start_time) * 1000

        return SearchResponse(
            results=items,
            total=len(fused),
            query=query.query,
            search_time_ms=search_time,
            vector_candidates=len(vector_results),
            bm25_candidates=len(bm25_results),
        )

    async def search_similar(
        self,
        item_id: UUID,
        limit: int = 10,
    ) -> list[SearchResult]:
        """
        Find items similar to a given item.

        Args:
            item_id: ID of reference item
            limit: Maximum results

        Returns:
            List of similar items
        """
        results = await self.vector_search.find_similar(item_id, limit)

        items = []
        for r in results:
            item = await self._fetch_item(r["id"])
            if item:
                items.append(SearchResult(
                    item=item,
                    score=r["score"],
                    match_type="similar",
                ))

        return items

    async def _embed(self, text: str) -> list[float]:
        """Generate embedding via Ollama."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text[:8000]},
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()["embedding"]

    async def _filter_by_time(
        self,
        results: list[dict],
        since: datetime | None,
        until: datetime | None,
    ) -> list[dict]:
        """Filter results by time range."""
        if not since and not until:
            return results

        item_ids = [r["id"] for r in results]

        async with self.pg.acquire() as conn:
            conditions = ["id = ANY($1)"]
            params: list = [item_ids]

            if since:
                conditions.append(f"t_valid >= ${len(params) + 1}")
                params.append(since)

            if until:
                conditions.append(f"t_valid <= ${len(params) + 1}")
                params.append(until)

            rows = await conn.fetch(
                f"""
                SELECT id FROM context_items
                WHERE {' AND '.join(conditions)}
                """,
                *params,
            )

        valid_ids = {row["id"] for row in rows}
        return [r for r in results if r["id"] in valid_ids]

    async def _get_timestamps(self, item_ids: list[UUID]) -> dict[UUID, datetime]:
        """Get timestamps for items."""
        if not item_ids:
            return {}

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, t_valid FROM context_items WHERE id = ANY($1)",
                item_ids,
            )

        return {row["id"]: row["t_valid"] for row in rows}

    async def _get_sources(self, item_ids: list[UUID]) -> dict[UUID, str]:
        """Get sources for items."""
        if not item_ids:
            return {}

        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, source FROM context_items WHERE id = ANY($1)",
                item_ids,
            )

        return {row["id"]: row["source"] for row in rows}

    async def _fetch_item(self, item_id: UUID) -> ContextItem | None:
        """Fetch full context item by ID."""
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM context_items WHERE id = $1",
                item_id,
            )

            if row:
                return self._row_to_item(row)
        return None

    def _row_to_item(self, row: asyncpg.Record) -> ContextItem:
        """Convert database row to ContextItem."""
        return ContextItem(
            id=row["id"],
            source=row["source"],
            source_id=row["source_id"],
            source_url=row["source_url"],
            content_type=row["content_type"],
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            temporal=BiTemporalMetadata(
                t_valid=row["t_valid"],
                t_invalid=row["t_invalid"],
                t_created=row["t_created"],
                t_expired=row["t_expired"],
            ),
            expires_at=row["expires_at"],
            entities=row["entities"] or [],
            entity_ids=[UUID(eid) for eid in (row["entity_ids"] or [])],
            tags=row["tags"] or [],
            namespace=row["namespace"],
            relevance=RelevanceSignals(**(row["relevance"] or {})),
            metadata=row["metadata"] or {},
        )


__all__ = ["HybridSearchEngine"]

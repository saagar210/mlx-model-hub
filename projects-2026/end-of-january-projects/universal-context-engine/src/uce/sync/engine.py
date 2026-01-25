"""
Sync engine for orchestrating data synchronization.
"""

import asyncio
from datetime import datetime
from typing import Any

import asyncpg
import httpx

from ..core.config import settings
from ..core.logging import get_logger
from ..adapters.base import BaseAdapter, SyncCursor
from ..entity_resolution.resolver import EntityResolver
from ..models.context_item import ContextItem
from .cursors import CursorManager

logger = get_logger(__name__)


class SyncEngine:
    """
    Orchestrates synchronization from all adapters.

    Handles:
    - Incremental sync from each adapter
    - Embedding generation
    - Entity extraction
    - Storing context items
    """

    def __init__(
        self,
        pg_pool: asyncpg.Pool,
        adapters: list[BaseAdapter],
    ) -> None:
        """
        Initialize sync engine.

        Args:
            pg_pool: PostgreSQL connection pool
            adapters: List of adapters to sync from
        """
        self.pg = pg_pool
        self.adapters = {a.source_type: a for a in adapters}
        self.cursor_manager = CursorManager(pg_pool)
        self.entity_resolver = EntityResolver(pg_pool)
        self._running = False

    async def sync_all(self) -> dict[str, Any]:
        """
        Sync all adapters.

        Returns:
            Summary of sync results
        """
        results = {}

        for source_type, adapter in self.adapters.items():
            try:
                result = await self.sync_source(source_type)
                results[source_type] = result
            except Exception as e:
                logger.error(f"Sync failed for {source_type}", error=str(e))
                results[source_type] = {"status": "error", "error": str(e)}

        return results

    async def sync_source(self, source_type: str) -> dict[str, Any]:
        """
        Sync a single source.

        Args:
            source_type: Source to sync

        Returns:
            Sync result summary
        """
        adapter = self.adapters.get(source_type)
        if not adapter:
            return {"status": "error", "error": f"Unknown source: {source_type}"}

        started_at = datetime.utcnow()

        # Get cursor
        cursor = await self.cursor_manager.get_cursor(source_type)

        # Mark as running
        await self.cursor_manager.set_status(source_type, "running")

        try:
            # Fetch items
            items, new_cursor = await adapter.fetch_incremental(cursor)

            # Process items
            created = 0
            updated = 0
            skipped = 0

            for item in items:
                result = await self._process_item(item)
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
                else:
                    skipped += 1

            # Flush entity co-occurrence
            await self.entity_resolver.flush_cooccurrence()

            # Save cursor
            await self.cursor_manager.save_cursor(new_cursor)

            # Record history
            await self.cursor_manager.record_sync_history(
                source=source_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                status="success",
                items_processed=len(items),
                items_created=created,
                items_updated=updated,
                items_skipped=skipped,
            )

            logger.info(
                f"Sync completed for {source_type}",
                items=len(items),
                created=created,
                updated=updated,
            )

            return {
                "status": "success",
                "items_processed": len(items),
                "items_created": created,
                "items_updated": updated,
                "items_skipped": skipped,
            }

        except Exception as e:
            # Mark as error
            await self.cursor_manager.set_status(source_type, "error", str(e))

            # Record history
            await self.cursor_manager.record_sync_history(
                source=source_type,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                status="error",
                error_message=str(e),
            )

            raise

    async def _process_item(self, item: ContextItem) -> str:
        """
        Process a single context item.

        - Generate embedding if missing
        - Extract entities
        - Store in database

        Returns:
            "created", "updated", or "skipped"
        """
        # Check for duplicate by content hash
        async with self.pg.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT id FROM context_items
                WHERE content_hash = $1 AND source = $2 AND t_expired IS NULL
                """,
                item.computed_hash,
                item.source,
            )

            if existing:
                return "skipped"

        # Generate embedding if missing
        if not item.embedding:
            item.embedding = await self._generate_embedding(item.content)

        # Extract and resolve entities
        entity_names, entity_ids = await self.entity_resolver.resolve_entities(item)
        item.entities = entity_names
        item.entity_ids = entity_ids

        # Check for existing item by source_id
        async with self.pg.acquire() as conn:
            existing_by_source = await conn.fetchrow(
                """
                SELECT id FROM context_items
                WHERE source = $1 AND source_id = $2 AND t_expired IS NULL
                """,
                item.source,
                item.source_id,
            ) if item.source_id else None

            if existing_by_source:
                # Expire old version
                await conn.execute(
                    "UPDATE context_items SET t_expired = NOW() WHERE id = $1",
                    existing_by_source["id"],
                )

            # Insert new item
            await conn.execute(
                """
                INSERT INTO context_items (
                    id, source, source_id, source_url, content_type,
                    title, content, content_hash, embedding,
                    t_valid, t_invalid, t_created, t_expired, expires_at,
                    entities, entity_ids, tags, namespace, relevance, metadata
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9::vector,
                    $10, $11, $12, $13, $14,
                    $15, $16, $17, $18, $19, $20
                )
                """,
                item.id,
                item.source,
                item.source_id,
                item.source_url,
                item.content_type,
                item.title,
                item.content,
                item.computed_hash,
                item.embedding,
                item.temporal.t_valid,
                item.temporal.t_invalid,
                item.temporal.t_created,
                item.temporal.t_expired,
                item.expires_at,
                item.entities,
                [str(eid) for eid in item.entity_ids],
                item.tags,
                item.namespace,
                item.relevance.model_dump(),
                item.metadata,
            )

            return "updated" if existing_by_source else "created"

    async def _generate_embedding(self, text: str) -> list[float] | None:
        """Generate embedding via Ollama."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ollama_url}/api/embeddings",
                    json={
                        "model": settings.embedding_model,
                        "prompt": text[:8000],  # Limit input length
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()["embedding"]
        except Exception as e:
            logger.warning(f"Embedding generation failed", error=str(e))
            return None


__all__ = ["SyncEngine"]

"""ChromaDB-based context store for Universal Context Engine."""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from .config import settings
from .embedding import embedding_client
from .logging import log_exception, log_operation, logger
from .models import ContextItem, ContextType, SearchResult

# Thread pool for blocking ChromaDB operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chromadb-")


class ContextStore:
    """Persistent context store using ChromaDB."""

    COLLECTIONS = {
        ContextType.SESSION: "sessions",
        ContextType.DECISION: "decisions",
        ContextType.PATTERN: "patterns",
        ContextType.CONTEXT: "context",
        ContextType.BLOCKER: "blockers",
        ContextType.ERROR: "errors",
    }

    def __init__(self, persist_directory: str | None = None):
        """Initialize the context store.

        Args:
            persist_directory: Path to ChromaDB storage. Defaults to config setting.
        """
        persist_dir = persist_directory or str(settings.chromadb_path)
        settings.ensure_directories()

        self._client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        self._collections: dict[str, chromadb.Collection] = {}
        self._embedding_client = embedding_client

    def _get_collection(self, context_type: ContextType) -> chromadb.Collection:
        """Get or create a collection for the given context type."""
        collection_name = f"{settings.chroma_collection_prefix}_{self.COLLECTIONS[context_type]}"

        if collection_name not in self._collections:
            self._collections[collection_name] = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        return self._collections[collection_name]

    async def save(
        self,
        content: str,
        context_type: ContextType,
        project: str | None = None,
        branch: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ContextItem:
        """Save a context item with embedding.

        Args:
            content: The content to save.
            context_type: Type of context item.
            project: Associated project path.
            branch: Git branch if applicable.
            metadata: Additional metadata.

        Returns:
            The saved ContextItem.
        """
        item_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC)

        # Generate embedding
        embedding = await self._embedding_client.embed(content)

        # Prepare metadata for ChromaDB (must be flat)
        chroma_metadata: dict[str, Any] = {
            "context_type": context_type.value,
            "timestamp": timestamp.isoformat(),
        }
        if project:
            chroma_metadata["project"] = project
        if branch:
            chroma_metadata["branch"] = branch
        if metadata:
            # Flatten metadata (ChromaDB only supports flat dicts)
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    chroma_metadata[f"meta_{key}"] = value

        # Save to collection (run blocking ChromaDB call in executor)
        collection = self._get_collection(context_type)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _executor,
            partial(
                collection.add,
                ids=[item_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[chroma_metadata],
            ),
        )

        return ContextItem(
            id=item_id,
            content=content,
            context_type=context_type,
            project=project,
            branch=branch,
            timestamp=timestamp,
            metadata=metadata or {},
        )

    async def search(
        self,
        query: str,
        context_type: ContextType | None = None,
        project: str | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Search for context items using semantic similarity.

        Args:
            query: The search query.
            context_type: Filter by context type. If None, searches all types.
            project: Filter by project.
            limit: Maximum number of results.

        Returns:
            List of SearchResults sorted by relevance.
        """
        # Generate query embedding
        query_embedding = await self._embedding_client.embed(query)

        # Build where clause for filtering
        where: dict[str, Any] | None = None
        if project:
            where = {"project": project}

        results: list[SearchResult] = []

        # Search in specified collection or all collections
        if context_type:
            collections_to_search = [self._get_collection(context_type)]
        else:
            collections_to_search = [
                self._get_collection(ct) for ct in ContextType
            ]

        loop = asyncio.get_event_loop()

        for collection in collections_to_search:
            try:
                # Run blocking ChromaDB query in executor
                search_results = await loop.run_in_executor(
                    _executor,
                    partial(
                        collection.query,
                        query_embeddings=[query_embedding],
                        n_results=limit,
                        where=where,
                        include=["documents", "metadatas", "distances"],
                    ),
                )

                # Process results
                if search_results["ids"] and search_results["ids"][0]:
                    for i, item_id in enumerate(search_results["ids"][0]):
                        doc = search_results["documents"][0][i] if search_results["documents"] else ""
                        meta = search_results["metadatas"][0][i] if search_results["metadatas"] else {}
                        distance = search_results["distances"][0][i] if search_results["distances"] else 0.0

                        # Convert distance to similarity score (cosine distance to similarity)
                        score = 1.0 - distance

                        # Reconstruct ContextItem
                        item = ContextItem(
                            id=item_id,
                            content=doc,
                            context_type=ContextType(meta.get("context_type", "context")),
                            project=meta.get("project"),
                            branch=meta.get("branch"),
                            timestamp=datetime.fromisoformat(meta["timestamp"]) if "timestamp" in meta else datetime.now(UTC),
                            metadata={
                                k[5:]: v for k, v in meta.items()
                                if k.startswith("meta_")
                            },
                        )

                        results.append(SearchResult(
                            item=item,
                            score=score,
                            distance=distance,
                        ))
            except Exception as e:
                # Collection might be empty or not exist yet
                log_exception("context_store", "search", e, {"collection": collection.name})
                continue

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def get_recent(
        self,
        project: str | None = None,
        hours: int = 24,
        context_type: ContextType | None = None,
        limit: int = 20,
    ) -> list[ContextItem]:
        """Get recent context items.

        Args:
            project: Filter by project.
            hours: Look back this many hours.
            context_type: Filter by context type.
            limit: Maximum number of results.

        Returns:
            List of recent ContextItems.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        cutoff_iso = cutoff.isoformat()

        items: list[ContextItem] = []

        # Get from specified collection or all collections
        if context_type:
            collections_to_search = [(context_type, self._get_collection(context_type))]
        else:
            collections_to_search = [
                (ct, self._get_collection(ct)) for ct in ContextType
            ]

        loop = asyncio.get_event_loop()

        for ct, collection in collections_to_search:
            try:
                # Build where clause
                where_clause = {"project": project} if project else None

                # ChromaDB doesn't support timestamp comparisons well,
                # so we get items and filter in Python
                # Use limit to reduce data loaded (multiply by collection count for safety margin)
                fetch_limit = limit * len(collections_to_search) * 2

                # Run blocking ChromaDB call in executor
                results = await loop.run_in_executor(
                    _executor,
                    partial(
                        collection.get,
                        include=["documents", "metadatas"],
                        where=where_clause,
                        limit=fetch_limit,  # Limit data loaded from ChromaDB
                    ),
                )

                if results["ids"]:
                    for i, item_id in enumerate(results["ids"]):
                        meta = results["metadatas"][i] if results["metadatas"] else {}
                        doc = results["documents"][i] if results["documents"] else ""

                        timestamp_str = meta.get("timestamp", "")
                        if timestamp_str and timestamp_str >= cutoff_iso:
                            items.append(ContextItem(
                                id=item_id,
                                content=doc,
                                context_type=ct,
                                project=meta.get("project"),
                                branch=meta.get("branch"),
                                timestamp=datetime.fromisoformat(timestamp_str),
                                metadata={
                                    k[5:]: v for k, v in meta.items()
                                    if k.startswith("meta_")
                                },
                            ))
            except Exception as e:
                log_exception("context_store", "get_recent", e, {"context_type": str(ct)})
                continue

        # Sort by timestamp descending and limit
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items[:limit]

    async def delete(self, item_id: str, context_type: ContextType) -> bool:
        """Delete a context item.

        Args:
            item_id: The ID of the item to delete.
            context_type: The type of the item.

        Returns:
            True if deleted, False if not found.
        """
        try:
            collection = self._get_collection(context_type)
            collection.delete(ids=[item_id])
            return True
        except Exception as e:
            log_exception("context_store", "delete", e, {"item_id": item_id})
            return False

    def get_stats(self) -> dict[str, int]:
        """Get statistics about stored context items.

        Returns:
            Dictionary mapping collection names to item counts.
        """
        stats = {}
        for context_type in ContextType:
            try:
                collection = self._get_collection(context_type)
                stats[context_type.value] = collection.count()
            except Exception as e:
                log_exception("context_store", "get_stats", e, {"context_type": context_type.value})
                stats[context_type.value] = 0
        return stats


# Default context store instance
context_store = ContextStore()


async def cleanup_executor() -> None:
    """Shutdown the thread pool executor gracefully."""
    _executor.shutdown(wait=False)

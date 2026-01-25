"""Base adapter interface for context sources."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import AsyncIterator

from ..models.context_item import ContextItem


@dataclass
class SyncCursor:
    """
    Tracks incremental sync position for an adapter.

    Each adapter can use the cursor_value in a source-specific way
    (timestamp, ID, offset, etc.).
    """

    source: str
    cursor_value: str | None = None
    last_sync_at: datetime | None = None
    items_synced: int = 0
    metadata: dict = field(default_factory=dict)

    def update(self, new_cursor: str | None, items_added: int = 0) -> None:
        """Update cursor after a sync operation."""
        self.cursor_value = new_cursor
        self.last_sync_at = datetime.utcnow()
        self.items_synced += items_added


class BaseAdapter(ABC):
    """
    Abstract base class for context source adapters.

    Each adapter is responsible for:
    - Fetching data from its source (incrementally or in full)
    - Transforming source data into ContextItems
    - Providing source-specific search capabilities
    """

    # Subclasses must set these
    name: str = "Base Adapter"
    source_type: str = "unknown"

    @abstractmethod
    async def fetch_incremental(
        self, cursor: SyncCursor | None = None
    ) -> tuple[list[ContextItem], SyncCursor]:
        """
        Fetch items since last sync.

        Args:
            cursor: Previous sync cursor, or None for initial sync

        Returns:
            Tuple of (new items, updated cursor)
        """
        pass

    @abstractmethod
    async def fetch_recent(self, hours: int = 24) -> list[ContextItem]:
        """
        Fetch recent items for a time window.

        Args:
            hours: How many hours back to fetch

        Returns:
            List of context items from the time window
        """
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """
        Search this source for matching items.

        Args:
            query: Search query
            limit: Maximum results to return

        Returns:
            List of matching context items
        """
        pass

    def get_sync_interval(self) -> timedelta:
        """
        How often this source should be synced.

        Override in subclass for source-specific intervals.
        """
        return timedelta(minutes=5)

    def get_source_quality(self) -> float:
        """
        Quality weight for this source (0-1).

        Higher quality sources are weighted more heavily in search results.
        Override in subclass.
        """
        return 0.8

    async def health_check(self) -> bool:
        """
        Check if the source is accessible.

        Returns:
            True if source is healthy
        """
        try:
            await self.fetch_recent(hours=1)
            return True
        except Exception:
            return False

    async def close(self) -> None:
        """
        Clean up resources (connection pools, etc.).

        Override in subclass if needed.
        """
        pass


class AdapterRegistry:
    """Registry for managing multiple adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, BaseAdapter] = {}

    def register(self, adapter: BaseAdapter) -> None:
        """Register an adapter."""
        self._adapters[adapter.source_type] = adapter

    def get(self, source_type: str) -> BaseAdapter | None:
        """Get adapter by source type."""
        return self._adapters.get(source_type)

    def all(self) -> list[BaseAdapter]:
        """Get all registered adapters."""
        return list(self._adapters.values())

    async def close_all(self) -> None:
        """Close all adapters."""
        for adapter in self._adapters.values():
            await adapter.close()


# Global registry
adapter_registry = AdapterRegistry()


__all__ = [
    "SyncCursor",
    "BaseAdapter",
    "AdapterRegistry",
    "adapter_registry",
]

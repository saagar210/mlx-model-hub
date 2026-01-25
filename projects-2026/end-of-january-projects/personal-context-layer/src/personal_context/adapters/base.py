"""Abstract base class for context adapters."""

from abc import ABC, abstractmethod

from personal_context.schema import ContextItem, ContextSource


class AbstractContextAdapter(ABC):
    """Base class for all context source adapters."""

    @property
    @abstractmethod
    def source(self) -> ContextSource:
        """Return the context source type."""
        ...

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """Search this source for matching items."""
        ...

    @abstractmethod
    async def get_recent(self, hours: int = 24, limit: int = 20) -> list[ContextItem]:
        """Get recently modified items from this source."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if this source is available."""
        ...

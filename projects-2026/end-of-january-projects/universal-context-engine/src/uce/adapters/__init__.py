"""UCE data source adapters."""

from .base import BaseAdapter, SyncCursor, AdapterRegistry, adapter_registry
from .kas_adapter import KASAdapter
from .git_adapter import GitAdapter
from .browser_adapter import BrowserContextAdapter

__all__ = [
    "BaseAdapter",
    "SyncCursor",
    "AdapterRegistry",
    "adapter_registry",
    "KASAdapter",
    "GitAdapter",
    "BrowserContextAdapter",
]

"""UCE API routes."""

from .search import router as search_router
from .context import router as context_router
from .entities import router as entities_router
from .health import router as health_router

__all__ = [
    "search_router",
    "context_router",
    "entities_router",
    "health_router",
]

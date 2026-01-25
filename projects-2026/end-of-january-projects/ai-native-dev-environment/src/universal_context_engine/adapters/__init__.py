"""Adapters for external services."""

from .kas import KASAdapter, kas_adapter
from .localcrew import LocalCrewAdapter, localcrew_adapter

__all__ = [
    "KASAdapter",
    "kas_adapter",
    "LocalCrewAdapter",
    "localcrew_adapter",
]

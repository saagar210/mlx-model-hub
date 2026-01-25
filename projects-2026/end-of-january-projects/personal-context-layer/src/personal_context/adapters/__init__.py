"""Context adapters for different data sources."""

from personal_context.adapters.base import AbstractContextAdapter
from personal_context.adapters.obsidian import ObsidianAdapter
from personal_context.adapters.git import GitAdapter
from personal_context.adapters.kas import KASAdapter

__all__ = ["AbstractContextAdapter", "ObsidianAdapter", "GitAdapter", "KASAdapter"]

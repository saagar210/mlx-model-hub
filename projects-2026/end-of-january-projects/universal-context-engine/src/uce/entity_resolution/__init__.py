"""UCE entity resolution."""

from .aliases import AliasRegistry, alias_registry
from .extractors import (
    ExtractedEntity,
    BaseExtractor,
    PatternExtractor,
    KeywordExtractor,
    CompositeExtractor,
)
from .cooccurrence import CooccurrenceTracker
from .resolver import EntityResolver

__all__ = [
    "AliasRegistry",
    "alias_registry",
    "ExtractedEntity",
    "BaseExtractor",
    "PatternExtractor",
    "KeywordExtractor",
    "CompositeExtractor",
    "CooccurrenceTracker",
    "EntityResolver",
]

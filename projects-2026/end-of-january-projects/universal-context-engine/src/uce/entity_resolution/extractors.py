"""
Entity extraction strategies.

Provides different methods for extracting entity mentions from text.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .aliases import alias_registry


@dataclass
class ExtractedEntity:
    """An entity extracted from text."""

    name: str
    entity_type: str | None = None
    confidence: float = 1.0
    start_pos: int | None = None
    end_pos: int | None = None
    context: str | None = None


class BaseExtractor(ABC):
    """Base class for entity extractors."""

    @abstractmethod
    def extract(self, text: str) -> list[ExtractedEntity]:
        """Extract entities from text."""
        pass


class PatternExtractor(BaseExtractor):
    """
    Pattern-based entity extraction.

    Uses regex patterns to find known entity names and patterns.
    """

    # Known technology/framework patterns (case-insensitive)
    _known_patterns: list[tuple[str, str]] = [
        # Specific technologies
        (r'\b(Knowledge Engine|KAS|Knowledge Activation System)\b', 'technology'),
        (r'\b(OAuth|OAuth2|JWT|Bearer)\b', 'technology'),
        (r'\b(Claude Code|Claude|Anthropic)\b', 'tool'),
        (r'\b(PostgreSQL|Postgres|MySQL|MongoDB|Redis|SQLite|Neo4j|Qdrant)\b', 'database'),
        (r'\b(FastAPI|Django|Flask|Express|Next\.js|React|Vue|Angular|Svelte)\b', 'framework'),
        (r'\b(Python|TypeScript|JavaScript|Rust|Go|Java|C\+\+|Ruby)\b', 'language'),
        (r'\b(Docker|Kubernetes|K8s|AWS|GCP|Azure|Vercel)\b', 'infrastructure'),
        (r'\b(Git|GitHub|GitLab|VSCode|Cursor)\b', 'tool'),
        (r'\b(RAG|GraphRAG|LLM|GPT|Ollama|LangChain|LlamaIndex|CrewAI)\b', 'technology'),
        (r'\b(MCP|Model Context Protocol)\b', 'technology'),
    ]

    # Generic patterns
    _generic_patterns: list[tuple[str, str]] = [
        # CamelCase words (likely class/component names)
        (r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b', 'unknown'),
        # Code references in backticks
        (r'`([a-zA-Z_][a-zA-Z0-9_.-]+)`', 'unknown'),
        # File paths
        (r'\b([a-zA-Z_][a-zA-Z0-9_-]*\.[a-z]{2,4})\b', 'file'),
    ]

    def __init__(self, include_generic: bool = True) -> None:
        """
        Initialize pattern extractor.

        Args:
            include_generic: Whether to include generic pattern matches
        """
        self.include_generic = include_generic
        self._compiled_known = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self._known_patterns
        ]
        self._compiled_generic = [
            (re.compile(p), t) for p, t in self._generic_patterns
        ]

    def extract(self, text: str) -> list[ExtractedEntity]:
        """Extract entities using patterns."""
        entities: dict[str, ExtractedEntity] = {}

        # Known patterns first (higher confidence)
        for pattern, entity_type in self._compiled_known:
            for match in pattern.finditer(text):
                name = match.group(1)
                canonical = alias_registry.resolve(name)

                if canonical not in entities:
                    entities[canonical] = ExtractedEntity(
                        name=canonical,
                        entity_type=entity_type,
                        confidence=0.9,
                        start_pos=match.start(),
                        end_pos=match.end(),
                    )

        # Generic patterns (lower confidence)
        if self.include_generic:
            for pattern, entity_type in self._compiled_generic:
                for match in pattern.finditer(text):
                    name = match.group(1)

                    # Skip if too short or common words
                    if len(name) < 3 or name.lower() in _COMMON_WORDS:
                        continue

                    canonical = alias_registry.resolve(name)

                    if canonical not in entities:
                        entities[canonical] = ExtractedEntity(
                            name=canonical,
                            entity_type=entity_type,
                            confidence=0.6,
                            start_pos=match.start(),
                            end_pos=match.end(),
                        )

        return list(entities.values())


class KeywordExtractor(BaseExtractor):
    """
    Keyword-based entity extraction.

    Looks for specific keywords and their surrounding context.
    """

    # Keywords that indicate entity types
    _type_keywords: dict[str, list[str]] = {
        "database": ["database", "db", "store", "storage"],
        "framework": ["framework", "library", "package"],
        "language": ["language", "lang", "written in", "using"],
        "tool": ["tool", "cli", "editor", "ide"],
        "file": ["file", "script", "module"],
        "project": ["project", "repo", "repository", "codebase"],
    }

    def extract(self, text: str) -> list[ExtractedEntity]:
        """Extract entities based on keyword context."""
        entities: list[ExtractedEntity] = []
        text_lower = text.lower()

        for entity_type, keywords in self._type_keywords.items():
            for keyword in keywords:
                # Find sentences/phrases containing the keyword
                pattern = rf'\b(\w+)\s+{keyword}\b|\b{keyword}\s+(\w+)\b'
                for match in re.finditer(pattern, text_lower):
                    name = match.group(1) or match.group(2)
                    if name and len(name) > 2 and name not in _COMMON_WORDS:
                        canonical = alias_registry.resolve(name)
                        entities.append(ExtractedEntity(
                            name=canonical,
                            entity_type=entity_type,
                            confidence=0.7,
                        ))

        return entities


class CompositeExtractor(BaseExtractor):
    """
    Combines multiple extractors and deduplicates results.
    """

    def __init__(self, extractors: list[BaseExtractor] | None = None) -> None:
        """
        Initialize composite extractor.

        Args:
            extractors: List of extractors to use, defaults to pattern + keyword
        """
        self.extractors = extractors or [
            PatternExtractor(),
            KeywordExtractor(),
        ]

    def extract(self, text: str) -> list[ExtractedEntity]:
        """Extract entities using all extractors and deduplicate."""
        all_entities: dict[str, ExtractedEntity] = {}

        for extractor in self.extractors:
            for entity in extractor.extract(text):
                key = entity.name.lower()

                if key not in all_entities:
                    all_entities[key] = entity
                else:
                    # Keep higher confidence version
                    if entity.confidence > all_entities[key].confidence:
                        all_entities[key] = entity

        return list(all_entities.values())


# Common words to skip
_COMMON_WORDS = frozenset([
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
    "be", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "shall", "can", "need",
    "this", "that", "these", "those", "it", "its", "they", "them",
    "we", "us", "our", "you", "your", "he", "she", "him", "her",
    "what", "which", "who", "whom", "when", "where", "why", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "any", "no", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "also", "now", "here", "there", "then",
    "once", "get", "got", "set", "let", "new", "old", "first", "last",
    "long", "great", "little", "own", "other", "old", "right", "big",
    "high", "different", "small", "large", "next", "early", "young",
    "important", "public", "bad", "same", "able", "use", "using", "used",
])


__all__ = [
    "ExtractedEntity",
    "BaseExtractor",
    "PatternExtractor",
    "KeywordExtractor",
    "CompositeExtractor",
]

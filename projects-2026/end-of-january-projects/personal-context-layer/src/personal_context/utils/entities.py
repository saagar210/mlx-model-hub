"""Entity extraction and resolution utilities."""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from personal_context.schema import ContextItem


@dataclass
class Entity:
    """An entity extracted from content."""

    name: str
    entity_type: str  # project, technology, person, concept
    aliases: set[str] = field(default_factory=set)
    mentions: list[ContextItem] = field(default_factory=list)
    mention_count: int = 0

    def add_mention(self, item: ContextItem):
        """Add a mention of this entity."""
        self.mentions.append(item)
        self.mention_count += 1


# Common technology terms to extract
KNOWN_TECHNOLOGIES = {
    "python", "javascript", "typescript", "react", "vue", "angular",
    "node", "nodejs", "fastapi", "flask", "django", "express",
    "postgresql", "postgres", "mysql", "mongodb", "redis", "sqlite",
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
    "git", "github", "gitlab", "oauth", "jwt", "api", "rest", "graphql",
    "qdrant", "pinecone", "mcp", "langchain", "llm", "rag",
    "obsidian", "kas", "mcp", "ollama", "anthropic", "openai",
    "playwright", "pytest", "jest", "vitest",
}

# Patterns for entity extraction
PATTERNS = {
    "project": re.compile(
        r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b"  # PascalCase
        r"|\b([a-z]+-[a-z]+(?:-[a-z]+)*)\b",  # kebab-case
        re.MULTILINE,
    ),
    "technology": re.compile(
        r"\b(" + "|".join(re.escape(t) for t in KNOWN_TECHNOLOGIES) + r")\b",
        re.IGNORECASE,
    ),
    "file_path": re.compile(
        r"(?:^|\s)([a-zA-Z0-9_/.-]+\.(?:py|js|ts|tsx|jsx|md|json|yaml|yml|toml))\b",
        re.MULTILINE,
    ),
}


def extract_entities_from_text(text: str) -> dict[str, set[str]]:
    """
    Extract entities from text content.

    Returns dict mapping entity type to set of entity names.
    """
    entities: dict[str, set[str]] = defaultdict(set)

    # Extract technologies
    for match in PATTERNS["technology"].finditer(text):
        tech = match.group(1).lower()
        entities["technology"].add(tech)

    # Extract project-like names
    for match in PATTERNS["project"].finditer(text):
        name = match.group(1) or match.group(2)
        if name and len(name) > 3:
            # Filter out common words
            if name.lower() not in {"the", "and", "for", "with", "from", "this", "that"}:
                entities["project"].add(name)

    # Extract file paths
    for match in PATTERNS["file_path"].finditer(text):
        path = match.group(1)
        if "/" in path or path.count(".") == 1:
            entities["file_path"].add(path)

    return dict(entities)


def extract_entities_from_items(items: list[ContextItem]) -> dict[str, Entity]:
    """
    Extract and consolidate entities from multiple context items.

    Returns dict mapping normalized entity name to Entity object.
    """
    entities: dict[str, Entity] = {}

    for item in items:
        # Combine title and content for extraction
        text = f"{item.title}\n{item.content}"
        extracted = extract_entities_from_text(text)

        for entity_type, names in extracted.items():
            for name in names:
                # Normalize name for lookup
                normalized = name.lower().replace("-", " ").replace("_", " ")

                if normalized not in entities:
                    entities[normalized] = Entity(
                        name=name,
                        entity_type=entity_type,
                        aliases={name},
                    )
                else:
                    entities[normalized].aliases.add(name)

                entities[normalized].add_mention(item)

    return entities


def find_entity_mentions(
    entity_name: str,
    items: list[ContextItem],
    fuzzy: bool = True,
) -> list[ContextItem]:
    """
    Find all items that mention a specific entity.

    Args:
        entity_name: Name of entity to find
        items: List of items to search
        fuzzy: Whether to use fuzzy matching

    Returns:
        Items that mention the entity
    """
    results = []
    name_lower = entity_name.lower()
    name_variants = {
        name_lower,
        name_lower.replace(" ", "-"),
        name_lower.replace(" ", "_"),
        name_lower.replace("-", " "),
        name_lower.replace("_", " "),
    }

    # Add common variations
    if fuzzy:
        # Handle plural/singular
        if name_lower.endswith("s"):
            name_variants.add(name_lower[:-1])
        else:
            name_variants.add(name_lower + "s")

    for item in items:
        text = f"{item.title}\n{item.content}".lower()
        if any(variant in text for variant in name_variants):
            results.append(item)

    return results


def resolve_entity_aliases(entities: dict[str, Entity]) -> dict[str, Entity]:
    """
    Resolve entity aliases to canonical names.

    Merges entities that are likely the same thing.
    """
    # Group entities by similar names
    merged: dict[str, Entity] = {}

    for normalized, entity in entities.items():
        # Find existing entity this might merge with
        merged_key = None
        for key in merged:
            # Check if names are similar enough
            if _names_similar(normalized, key):
                merged_key = key
                break

        if merged_key:
            # Merge into existing entity
            merged[merged_key].aliases.update(entity.aliases)
            merged[merged_key].mentions.extend(entity.mentions)
            merged[merged_key].mention_count += entity.mention_count
        else:
            # Add as new entity
            merged[normalized] = entity

    return merged


def _names_similar(name1: str, name2: str, threshold: float = 0.8) -> bool:
    """Check if two names are similar enough to be the same entity."""
    # Simple containment check
    if name1 in name2 or name2 in name1:
        return True

    # Word overlap check
    words1 = set(name1.split())
    words2 = set(name2.split())

    if not words1 or not words2:
        return False

    overlap = len(words1 & words2)
    total = len(words1 | words2)

    return overlap / total >= threshold


def rank_entities_by_relevance(
    entities: dict[str, Entity],
    query: str | None = None,
) -> list[Entity]:
    """
    Rank entities by relevance.

    Considers mention count, recency, and query match.
    """
    entity_list = list(entities.values())

    def score(entity: Entity) -> float:
        s = entity.mention_count * 0.5

        # Boost if matches query
        if query:
            query_lower = query.lower()
            if query_lower in entity.name.lower():
                s += 10
            elif any(query_lower in alias.lower() for alias in entity.aliases):
                s += 5

        # Boost technologies (more concrete)
        if entity.entity_type == "technology":
            s += 2

        return s

    entity_list.sort(key=score, reverse=True)
    return entity_list

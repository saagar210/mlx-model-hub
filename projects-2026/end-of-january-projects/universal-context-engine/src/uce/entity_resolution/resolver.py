"""
Entity resolution engine.

Extracts, normalizes, and links entities across context sources.
"""

import re
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg

from ..models.entity import Entity, EntityType
from ..models.context_item import ContextItem
from .aliases import alias_registry
from .extractors import CompositeExtractor, ExtractedEntity
from .cooccurrence import CooccurrenceTracker


class EntityResolver:
    """
    Entity resolution engine for cross-source linking.

    Features:
    - Alias mapping (OAuth2 -> OAuth)
    - Type inference (PostgreSQL -> database)
    - Entity extraction from text
    - Co-occurrence tracking for relationship discovery
    """

    # Type inference patterns
    _type_patterns: dict[EntityType, list[str]] = {
        "database": [
            "postgresql", "postgres", "mysql", "mongodb", "redis",
            "sqlite", "neo4j", "qdrant", "dynamodb", "cassandra",
        ],
        "framework": [
            "fastapi", "django", "flask", "express", "nextjs", "react",
            "vue", "angular", "svelte", "crewai", "langchain", "llamaindex",
        ],
        "language": [
            "python", "typescript", "javascript", "rust", "go", "java",
            "ruby", "c++", "c#", "swift", "kotlin",
        ],
        "tool": [
            "claude_code", "git", "github", "vscode", "cursor", "docker",
            "ollama", "npm", "yarn", "pip",
        ],
        "technology": [
            "oauth", "jwt", "rag", "graphrag", "mcp", "llm", "gpt",
            "rest", "graphql", "grpc", "websocket",
        ],
        "infrastructure": [
            "kubernetes", "aws", "gcp", "azure", "vercel", "heroku",
            "docker", "terraform", "ansible",
        ],
    }

    def __init__(self, pg_pool: asyncpg.Pool) -> None:
        """
        Initialize entity resolver.

        Args:
            pg_pool: PostgreSQL connection pool
        """
        self.pg = pg_pool
        self._entity_cache: dict[str, Entity] = {}
        self._extractor = CompositeExtractor()
        self._cooccurrence = CooccurrenceTracker(pg_pool)

    async def extract_entities(self, item: ContextItem) -> list[str]:
        """
        Extract entity names from a context item.

        Args:
            item: Context item to extract entities from

        Returns:
            List of extracted entity names (canonical form)
        """
        text = f"{item.title} {item.content}"
        extracted = self._extractor.extract(text)

        # Resolve aliases and deduplicate
        entities = set()
        for e in extracted:
            canonical = alias_registry.resolve(e.name)
            if len(canonical) > 2:  # Skip very short matches
                entities.add(canonical)

        return list(entities)[:20]  # Limit to 20 entities per item

    async def resolve_or_create(
        self,
        name: str,
        source: str | None = None,
    ) -> Entity:
        """
        Resolve entity by name, creating if needed.

        Args:
            name: Entity name to resolve
            source: Optional source that mentioned this entity

        Returns:
            Resolved or newly created Entity
        """
        canonical = self._canonicalize(name)

        # Check cache first
        if canonical in self._entity_cache:
            entity = self._entity_cache[canonical]
            # Update mention count asynchronously
            await self._increment_mentions(entity.id)
            return entity

        # Check database
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM entities WHERE canonical_name = $1
                """,
                canonical,
            )

            if row:
                entity = Entity(
                    id=row["id"],
                    canonical_name=row["canonical_name"],
                    display_name=row["display_name"],
                    entity_type=row["entity_type"],
                    aliases=row["aliases"] or [],
                    description=row["description"],
                    metadata=row["metadata"] or {},
                    mention_count=row["mention_count"],
                    last_seen_at=row["last_seen_at"],
                    first_seen_at=row["first_seen_at"],
                )
                self._entity_cache[canonical] = entity

                # Update mention count
                await conn.execute(
                    """
                    UPDATE entities
                    SET mention_count = mention_count + 1, last_seen_at = NOW()
                    WHERE id = $1
                    """,
                    entity.id,
                )

                return entity

            # Create new entity
            entity_type = self._infer_type(name)
            display_name = self._to_display_name(name)

            entity = Entity(
                id=uuid4(),
                canonical_name=canonical,
                display_name=display_name,
                entity_type=entity_type,
                aliases=[name.lower()] if name.lower() != canonical else [],
                mention_count=1,
                last_seen_at=datetime.utcnow(),
            )

            await conn.execute(
                """
                INSERT INTO entities (
                    id, canonical_name, display_name, entity_type,
                    aliases, mention_count, last_seen_at, first_seen_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                entity.id,
                entity.canonical_name,
                entity.display_name,
                entity.entity_type,
                entity.aliases,
                entity.mention_count,
                entity.last_seen_at,
                entity.first_seen_at,
            )

            self._entity_cache[canonical] = entity
            return entity

    async def resolve_entities(
        self,
        item: ContextItem,
    ) -> tuple[list[str], list[UUID]]:
        """
        Extract and resolve all entities from a context item.

        Args:
            item: Context item to process

        Returns:
            Tuple of (entity names, entity IDs)
        """
        entity_names = await self.extract_entities(item)

        entity_ids = []
        for name in entity_names:
            entity = await self.resolve_or_create(name, source=item.source)
            entity_ids.append(entity.id)

        # Record co-occurrence
        if len(entity_ids) >= 2:
            await self._cooccurrence.record(entity_ids)

        return entity_names, entity_ids

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        """Get entity by ID."""
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM entities WHERE id = $1",
                entity_id,
            )

            if row:
                return Entity(
                    id=row["id"],
                    canonical_name=row["canonical_name"],
                    display_name=row["display_name"],
                    entity_type=row["entity_type"],
                    aliases=row["aliases"] or [],
                    description=row["description"],
                    metadata=row["metadata"] or {},
                    mention_count=row["mention_count"],
                    last_seen_at=row["last_seen_at"],
                    first_seen_at=row["first_seen_at"],
                )
        return None

    async def get_entity_by_name(self, name: str) -> Entity | None:
        """Get entity by name (resolves aliases)."""
        canonical = self._canonicalize(name)

        if canonical in self._entity_cache:
            return self._entity_cache[canonical]

        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM entities WHERE canonical_name = $1",
                canonical,
            )

            if row:
                entity = Entity(
                    id=row["id"],
                    canonical_name=row["canonical_name"],
                    display_name=row["display_name"],
                    entity_type=row["entity_type"],
                    aliases=row["aliases"] or [],
                    description=row["description"],
                    metadata=row["metadata"] or {},
                    mention_count=row["mention_count"],
                    last_seen_at=row["last_seen_at"],
                    first_seen_at=row["first_seen_at"],
                )
                self._entity_cache[canonical] = entity
                return entity
        return None

    async def search_entities(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Entity]:
        """Search entities by name or alias."""
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM entities
                WHERE canonical_name ILIKE $1
                   OR display_name ILIKE $1
                   OR $2 = ANY(aliases)
                ORDER BY mention_count DESC
                LIMIT $3
                """,
                f"%{query}%",
                query.lower(),
                limit,
            )

        return [
            Entity(
                id=row["id"],
                canonical_name=row["canonical_name"],
                display_name=row["display_name"],
                entity_type=row["entity_type"],
                aliases=row["aliases"] or [],
                mention_count=row["mention_count"],
            )
            for row in rows
        ]

    async def get_related_entities(
        self,
        entity_id: UUID,
        limit: int = 10,
    ) -> list[tuple[Entity, int]]:
        """Get entities related by co-occurrence."""
        related = await self._cooccurrence.get_related(
            entity_id,
            min_count=2,
            limit=limit,
        )

        results = []
        for related_id, count in related:
            entity = await self.get_entity(related_id)
            if entity:
                results.append((entity, count))

        return results

    async def flush_cooccurrence(self) -> None:
        """Flush pending co-occurrence data to database."""
        await self._cooccurrence.flush()

    def _canonicalize(self, name: str) -> str:
        """Get canonical form of entity name."""
        # Resolve alias first
        resolved = alias_registry.resolve(name)

        # Normalize: lowercase, replace spaces/hyphens with underscores
        canonical = re.sub(r'[\s\-]+', '_', resolved.lower().strip())
        # Remove special characters except underscores
        canonical = re.sub(r'[^\w]', '', canonical)

        return canonical

    def _to_display_name(self, name: str) -> str:
        """Convert to human-readable display name."""
        # If it's a known alias, use the canonical display form
        resolved = alias_registry.resolve(name)

        # Capitalize words
        words = re.split(r'[\s_\-]+', resolved)
        return ' '.join(word.capitalize() for word in words if word)

    def _infer_type(self, name: str) -> EntityType:
        """Infer entity type from name."""
        canonical = self._canonicalize(name)

        for entity_type, patterns in self._type_patterns.items():
            if canonical in patterns:
                return entity_type

        # Check for file patterns
        if re.match(r'^[\w\-]+\.\w{2,4}$', name):
            return "file"
        if '/' in name or name.startswith('~'):
            return "directory"

        return "unknown"

    async def _increment_mentions(self, entity_id: UUID) -> None:
        """Increment entity mention count."""
        async with self.pg.acquire() as conn:
            await conn.execute(
                """
                UPDATE entities
                SET mention_count = mention_count + 1, last_seen_at = NOW()
                WHERE id = $1
                """,
                entity_id,
            )

    def clear_cache(self) -> None:
        """Clear the entity cache."""
        self._entity_cache.clear()


__all__ = ["EntityResolver"]

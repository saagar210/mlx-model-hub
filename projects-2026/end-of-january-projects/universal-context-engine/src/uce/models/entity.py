"""Entity and relationship models for the knowledge graph."""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# Entity type classification
EntityType = Literal[
    "technology",
    "framework",
    "database",
    "language",
    "tool",
    "file",
    "directory",
    "repository",
    "person",
    "project",
    "concept",
    "unknown",
]

# Relationship types
RelationshipType = Literal[
    "uses",
    "depends_on",
    "related_to",
    "part_of",
    "implements",
    "extends",
    "references",
    "created_by",
    "modified_by",
]


class Entity(BaseModel):
    """
    Entity in the knowledge graph.

    Represents a distinct concept, technology, person, or thing that appears
    across multiple context items.
    """

    id: UUID = Field(default_factory=uuid4)

    # Identity
    canonical_name: str = Field(
        description="Normalized canonical form (lowercase, underscores)"
    )
    display_name: str = Field(
        description="Human-readable display form"
    )

    # Classification
    entity_type: EntityType = Field(
        description="Type of entity"
    )

    # Aliases for resolution
    aliases: list[str] = Field(
        default_factory=list,
        description="Alternative names that map to this entity"
    )

    # Metadata
    description: str | None = Field(
        default=None,
        description="Brief description of the entity"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    # Statistics
    mention_count: int = Field(
        default=0,
        description="Number of times this entity has been mentioned"
    )
    last_seen_at: datetime | None = Field(
        default=None,
        description="Last time this entity was seen in context"
    )
    first_seen_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="First time this entity was seen"
    )

    def add_alias(self, alias: str) -> None:
        """Add an alias if not already present."""
        normalized = alias.lower().strip()
        if normalized and normalized not in self.aliases:
            self.aliases.append(normalized)

    def increment_mentions(self) -> None:
        """Increment mention count and update last_seen."""
        self.mention_count += 1
        self.last_seen_at = datetime.utcnow()

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "display_name": self.display_name,
            "entity_type": self.entity_type,
            "aliases": self.aliases,
            "description": self.description,
            "metadata": self.metadata,
            "mention_count": self.mention_count,
            "last_seen_at": self.last_seen_at,
            "first_seen_at": self.first_seen_at,
        }


class EntityRelationship(BaseModel):
    """
    Relationship between entities in the knowledge graph.

    Supports bi-temporal tracking for when relationships were valid.
    """

    id: UUID = Field(default_factory=uuid4)

    # Relationship endpoints
    from_entity_id: UUID = Field(description="Source entity ID")
    to_entity_id: UUID = Field(description="Target entity ID")
    relationship_type: RelationshipType = Field(
        description="Type of relationship"
    )

    # Bi-temporal
    t_valid: datetime = Field(
        description="When relationship became true"
    )
    t_invalid: datetime | None = Field(
        default=None,
        description="When relationship ended"
    )

    # Confidence and provenance
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for this relationship"
    )
    source: str | None = Field(
        default=None,
        description="Which adapter discovered this relationship"
    )
    source_item_id: UUID | None = Field(
        default=None,
        description="Context item that established this relationship"
    )

    # Metadata
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata"
    )

    def is_active(self, as_of: datetime | None = None) -> bool:
        """Check if relationship is active at given time."""
        check_time = as_of or datetime.utcnow()
        if self.t_valid > check_time:
            return False
        if self.t_invalid and self.t_invalid <= check_time:
            return False
        return True

    def invalidate(self, at: datetime | None = None) -> None:
        """Mark relationship as ended."""
        self.t_invalid = at or datetime.utcnow()

    def to_db_dict(self) -> dict:
        """Convert to dictionary for database insertion."""
        return {
            "id": self.id,
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "relationship_type": self.relationship_type,
            "t_valid": self.t_valid,
            "t_invalid": self.t_invalid,
            "confidence": self.confidence,
            "source": self.source,
            "source_item_id": self.source_item_id,
            "metadata": self.metadata,
        }


class EntityCooccurrence(BaseModel):
    """
    Tracks how often two entities appear together.

    Used for discovering implicit relationships.
    """

    entity_a_id: UUID = Field(description="First entity (always < entity_b_id)")
    entity_b_id: UUID = Field(description="Second entity")
    cooccurrence_count: int = Field(
        default=1,
        description="Number of times seen together"
    )
    last_seen_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last co-occurrence"
    )

    def increment(self) -> None:
        """Increment count and update timestamp."""
        self.cooccurrence_count += 1
        self.last_seen_at = datetime.utcnow()


__all__ = [
    "EntityType",
    "RelationshipType",
    "Entity",
    "EntityRelationship",
    "EntityCooccurrence",
]

"""
Memory CRUD operations for episodic and semantic memory.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.memory import EpisodicMemory, SemanticMemory
from sia.schemas.memory import (
    EpisodicMemoryCreate,
    SemanticMemoryCreate,
    SemanticMemoryUpdate,
)


class EpisodicMemoryCRUD:
    """CRUD operations for episodic memory."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: EpisodicMemoryCreate) -> EpisodicMemory:
        """Create a new episodic memory entry."""
        memory = EpisodicMemory(
            execution_id=data.execution_id,
            sequence_num=data.sequence_num,
            event_type=data.event_type,
            description=data.description,
            details=data.details,
            agent_state=data.agent_state,
            memory_state=data.memory_state,
            environment_state=data.environment_state,
            content_for_embedding=data.content_for_embedding,
            importance_score=data.importance_score,
            related_skill_id=data.related_skill_id,
            related_fact_ids=data.related_fact_ids,
        )

        self.session.add(memory)
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def get(self, memory_id: UUID) -> EpisodicMemory | None:
        """Get an episodic memory by ID."""
        result = await self.session.execute(
            select(EpisodicMemory).where(EpisodicMemory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def list_by_execution(self, execution_id: UUID) -> list[EpisodicMemory]:
        """Get all episodic memories for an execution."""
        result = await self.session.execute(
            select(EpisodicMemory)
            .where(EpisodicMemory.execution_id == execution_id)
            .order_by(EpisodicMemory.sequence_num)
        )
        return list(result.scalars().all())

    async def list(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
        min_importance: float | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[EpisodicMemory]:
        """List episodic memories with optional filters."""
        query = select(EpisodicMemory)

        if event_type:
            query = query.where(EpisodicMemory.event_type == event_type)

        if since:
            query = query.where(EpisodicMemory.timestamp >= since)

        if min_importance is not None:
            query = query.where(EpisodicMemory.importance_score >= min_importance)

        query = query.order_by(EpisodicMemory.timestamp.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_embedding(
        self,
        memory_id: UUID,
        embedding: list[float],
        embedding_model: str,
    ) -> EpisodicMemory | None:
        """Update a memory's embedding."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        memory.embedding = embedding
        memory.embedding_model = embedding_model

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        since: datetime | None = None,
        min_importance: float | None = None,
    ) -> list[tuple[EpisodicMemory, float]]:
        """Search episodic memories by embedding similarity."""
        query = (
            select(
                EpisodicMemory,
                EpisodicMemory.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(EpisodicMemory.embedding.isnot(None))
        )

        if since:
            query = query.where(EpisodicMemory.timestamp >= since)

        if min_importance is not None:
            query = query.where(EpisodicMemory.importance_score >= min_importance)

        query = query.order_by("distance").limit(limit)

        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def count(self, execution_id: UUID | None = None) -> int:
        """Count episodic memories."""
        query = select(func.count(EpisodicMemory.id))

        if execution_id:
            query = query.where(EpisodicMemory.execution_id == execution_id)

        result = await self.session.execute(query)
        return result.scalar_one()


class SemanticMemoryCRUD:
    """CRUD operations for semantic memory."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: SemanticMemoryCreate) -> SemanticMemory:
        """Create a new semantic memory entry."""
        memory = SemanticMemory(
            fact=data.fact,
            fact_type=data.fact_type,
            category=data.category,
            tags=data.tags,
            confidence=data.confidence,
            supporting_executions=data.supporting_executions,
            source=data.source,
            source_description=data.source_description,
            valid_until=data.valid_until,
        )

        self.session.add(memory)
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def get(self, memory_id: UUID) -> SemanticMemory | None:
        """Get a semantic memory by ID."""
        result = await self.session.execute(
            select(SemanticMemory).where(SemanticMemory.id == memory_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        fact_type: str | None = None,
        category: str | None = None,
        min_confidence: float | None = None,
        include_deleted: bool = False,
        include_expired: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SemanticMemory]:
        """List semantic memories with optional filters."""
        query = select(SemanticMemory)

        if not include_deleted:
            query = query.where(SemanticMemory.deleted_at.is_(None))

        if not include_expired:
            query = query.where(
                (SemanticMemory.valid_until.is_(None))
                | (SemanticMemory.valid_until > datetime.utcnow())
            )

        if fact_type:
            query = query.where(SemanticMemory.fact_type == fact_type)

        if category:
            query = query.where(SemanticMemory.category == category)

        if min_confidence is not None:
            query = query.where(SemanticMemory.confidence >= min_confidence)

        query = query.order_by(SemanticMemory.confidence.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        memory_id: UUID,
        data: SemanticMemoryUpdate,
    ) -> SemanticMemory | None:
        """Update a semantic memory."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(memory, field, value)

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def soft_delete(self, memory_id: UUID) -> SemanticMemory | None:
        """Soft delete a semantic memory."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        memory.deleted_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def reinforce(
        self,
        memory_id: UUID,
        execution_id: UUID,
    ) -> SemanticMemory | None:
        """Reinforce a fact with supporting evidence."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        memory.reinforce(execution_id)

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def contradict(
        self,
        memory_id: UUID,
        execution_id: UUID,
    ) -> SemanticMemory | None:
        """Record contradicting evidence for a fact."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        memory.contradict(execution_id)

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def record_access(self, memory_id: UUID) -> SemanticMemory | None:
        """Record that a memory was accessed."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        memory.access_count += 1
        memory.last_accessed = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def update_embedding(
        self,
        memory_id: UUID,
        embedding: list[float],
        embedding_model: str,
    ) -> SemanticMemory | None:
        """Update a memory's embedding."""
        memory = await self.get(memory_id)
        if not memory:
            return None

        memory.embedding = embedding
        memory.embedding_model = embedding_model

        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        min_confidence: float | None = None,
        fact_type: str | None = None,
    ) -> list[tuple[SemanticMemory, float]]:
        """Search semantic memories by embedding similarity."""
        query = (
            select(
                SemanticMemory,
                SemanticMemory.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(SemanticMemory.embedding.isnot(None))
            .where(SemanticMemory.deleted_at.is_(None))
            .where(
                (SemanticMemory.valid_until.is_(None))
                | (SemanticMemory.valid_until > datetime.utcnow())
            )
        )

        if min_confidence is not None:
            query = query.where(SemanticMemory.confidence >= min_confidence)

        if fact_type:
            query = query.where(SemanticMemory.fact_type == fact_type)

        query = query.order_by("distance").limit(limit)

        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

    async def count(
        self,
        include_deleted: bool = False,
        include_expired: bool = False,
    ) -> int:
        """Count semantic memories."""
        query = select(func.count(SemanticMemory.id))

        if not include_deleted:
            query = query.where(SemanticMemory.deleted_at.is_(None))

        if not include_expired:
            query = query.where(
                (SemanticMemory.valid_until.is_(None))
                | (SemanticMemory.valid_until > datetime.utcnow())
            )

        result = await self.session.execute(query)
        return result.scalar_one()

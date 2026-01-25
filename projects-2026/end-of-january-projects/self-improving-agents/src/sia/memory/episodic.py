"""
Episodic Memory System.

Stores timestamped execution events for context retrieval.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud.memory import EpisodicMemoryCRUD
from sia.llm.embeddings import EmbeddingService
from sia.models.memory import EpisodicMemory as EpisodicMemoryModel
from sia.schemas.memory import EpisodicMemoryCreate


@dataclass
class EpisodicSearchResult:
    """Result from episodic memory search."""

    memory: EpisodicMemoryModel
    similarity_score: float
    recency_score: float
    importance_score: float
    combined_score: float


class EpisodicMemoryManager:
    """
    Manages episodic memory - timestamped execution events.

    Features:
    - Trace recording during execution
    - Automatic embedding generation
    - Similarity search with recency/importance weighting
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        recency_weight: float = 0.3,
        importance_weight: float = 0.2,
        similarity_weight: float = 0.5,
        recency_decay_days: float = 7.0,
    ):
        """
        Initialize episodic memory manager.

        Args:
            session: Database session
            embedding_service: Service for generating embeddings
            recency_weight: Weight for recency in combined score
            importance_weight: Weight for importance in combined score
            similarity_weight: Weight for similarity in combined score
            recency_decay_days: Days after which recency score is ~0
        """
        self.session = session
        self.crud = EpisodicMemoryCRUD(session)
        self._embedding_service = embedding_service
        self.recency_weight = recency_weight
        self.importance_weight = importance_weight
        self.similarity_weight = similarity_weight
        self.recency_decay_days = recency_decay_days

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    async def record_event(
        self,
        execution_id: UUID,
        sequence_num: int,
        event_type: str,
        description: str,
        details: dict[str, Any] | None = None,
        agent_state: dict[str, Any] | None = None,
        memory_state: dict[str, Any] | None = None,
        environment_state: dict[str, Any] | None = None,
        importance_score: float = 0.5,
        related_skill_id: UUID | None = None,
        related_fact_ids: list[UUID] | None = None,
        generate_embedding: bool = True,
    ) -> EpisodicMemoryModel:
        """
        Record an execution event to episodic memory.

        Args:
            execution_id: ID of the execution
            sequence_num: Order of this event in the execution
            event_type: Type of event (task_start, step_complete, etc.)
            description: Human-readable description
            details: Additional event details
            agent_state: Snapshot of agent state
            memory_state: Snapshot of working memory
            environment_state: Relevant environment info
            importance_score: 0-1, higher = more important
            related_skill_id: Associated skill if any
            related_fact_ids: Associated semantic facts
            generate_embedding: Whether to generate embedding

        Returns:
            Created episodic memory record
        """
        # Build content for embedding
        content_for_embedding = self._build_embedding_content(
            event_type=event_type,
            description=description,
            details=details,
        )

        # Create the memory record
        memory = await self.crud.create(
            EpisodicMemoryCreate(
                execution_id=execution_id,
                sequence_num=sequence_num,
                event_type=event_type,
                description=description,
                details=details or {},
                agent_state=agent_state,
                memory_state=memory_state,
                environment_state=environment_state,
                content_for_embedding=content_for_embedding,
                importance_score=importance_score,
                related_skill_id=related_skill_id,
                related_fact_ids=related_fact_ids or [],
            )
        )

        # Generate embedding if requested
        if generate_embedding and content_for_embedding:
            await self._update_embedding(memory.id, content_for_embedding)

        return memory

    async def search(
        self,
        query: str,
        limit: int = 10,
        since: datetime | None = None,
        min_importance: float | None = None,
        event_types: list[str] | None = None,
        execution_id: UUID | None = None,
    ) -> list[EpisodicSearchResult]:
        """
        Search episodic memory with combined scoring.

        Args:
            query: Search query text
            limit: Maximum results to return
            since: Only search events after this time
            min_importance: Minimum importance score filter
            event_types: Filter by event types
            execution_id: Filter by specific execution

        Returns:
            List of search results with combined scores
        """
        # Generate query embedding
        embedding_result = await self.embedding_service.embed(query)
        query_embedding = embedding_result.embedding

        # Search by embedding similarity
        results = await self.crud.search_by_embedding(
            embedding=query_embedding,
            limit=limit * 2,  # Get more to filter/rerank
            since=since,
            min_importance=min_importance,
        )

        # Calculate combined scores
        now = datetime.utcnow()
        scored_results = []

        for memory, distance in results:
            # Filter by event type if specified
            if event_types and memory.event_type not in event_types:
                continue

            # Filter by execution if specified
            if execution_id and memory.execution_id != execution_id:
                continue

            # Convert distance to similarity (0-1)
            similarity_score = max(0, 1 - distance)

            # Calculate recency score with exponential decay
            age_days = (now - memory.timestamp).total_seconds() / 86400
            recency_score = max(0, 1 - (age_days / self.recency_decay_days)) ** 2

            # Get importance score
            importance = memory.importance_score or 0.5

            # Calculate combined score
            combined_score = (
                self.similarity_weight * similarity_score
                + self.recency_weight * recency_score
                + self.importance_weight * importance
            )

            scored_results.append(
                EpisodicSearchResult(
                    memory=memory,
                    similarity_score=similarity_score,
                    recency_score=recency_score,
                    importance_score=importance,
                    combined_score=combined_score,
                )
            )

        # Sort by combined score and limit
        scored_results.sort(key=lambda r: r.combined_score, reverse=True)
        return scored_results[:limit]

    async def get_recent(
        self,
        hours: int = 24,
        limit: int = 50,
        min_importance: float | None = None,
        event_types: list[str] | None = None,
    ) -> list[EpisodicMemoryModel]:
        """
        Get recent episodic memories.

        Args:
            hours: How many hours back to look
            limit: Maximum results
            min_importance: Minimum importance filter
            event_types: Filter by event types

        Returns:
            List of recent memories
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        memories = await self.crud.list(
            since=since,
            min_importance=min_importance,
            limit=limit,
        )

        if event_types:
            memories = [m for m in memories if m.event_type in event_types]

        return memories

    async def get_execution_trace(
        self,
        execution_id: UUID,
    ) -> list[EpisodicMemoryModel]:
        """
        Get full trace for an execution.

        Args:
            execution_id: ID of the execution

        Returns:
            List of memories in sequence order
        """
        return await self.crud.list_by_execution(execution_id)

    async def get_similar_executions(
        self,
        task_description: str,
        limit: int = 5,
        only_successful: bool = True,
    ) -> list[EpisodicSearchResult]:
        """
        Find similar past executions based on task description.

        Args:
            task_description: Description of the task
            limit: Maximum results
            only_successful: Only return successful executions

        Returns:
            List of similar execution start events
        """
        results = await self.search(
            query=task_description,
            limit=limit * 2,
            event_types=["task_start"],
        )

        if only_successful:
            # Filter to only include executions that completed successfully
            # This requires checking the execution record
            # For now, we return all and let caller filter
            pass

        return results[:limit]

    async def update_importance(
        self,
        memory_id: UUID,
        importance_score: float,
    ) -> EpisodicMemoryModel | None:
        """
        Update importance score of a memory.

        Args:
            memory_id: ID of the memory
            importance_score: New importance score (0-1)

        Returns:
            Updated memory or None if not found
        """
        memory = await self.crud.get(memory_id)
        if not memory:
            return None

        memory.importance_score = max(0, min(1, importance_score))
        await self.session.flush()
        await self.session.refresh(memory)
        return memory

    async def count(self, execution_id: UUID | None = None) -> int:
        """Count episodic memories."""
        return await self.crud.count(execution_id)

    def _build_embedding_content(
        self,
        event_type: str,
        description: str,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Build text content for embedding generation."""
        parts = [f"Event: {event_type}", f"Description: {description}"]

        if details:
            # Include relevant detail keys
            for key in ["task", "action", "result", "error", "context"]:
                if key in details:
                    value = details[key]
                    if isinstance(value, str):
                        parts.append(f"{key.title()}: {value}")
                    elif isinstance(value, dict):
                        parts.append(f"{key.title()}: {str(value)[:200]}")

        return "\n".join(parts)

    async def _update_embedding(
        self,
        memory_id: UUID,
        content: str,
    ) -> None:
        """Generate and store embedding for a memory."""
        result = await self.embedding_service.embed(content)
        await self.crud.update_embedding(
            memory_id=memory_id,
            embedding=result.embedding,
            embedding_model=result.model,
        )

    async def close(self) -> None:
        """Close resources."""
        if self._embedding_service:
            await self._embedding_service.close()

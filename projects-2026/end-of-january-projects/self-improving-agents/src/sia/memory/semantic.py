"""
Semantic Memory System.

Stores facts, knowledge, and learned patterns with confidence tracking.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud.memory import SemanticMemoryCRUD
from sia.llm.embeddings import EmbeddingService
from sia.models.memory import SemanticMemory as SemanticMemoryModel
from sia.schemas.memory import SemanticMemoryCreate, SemanticMemoryUpdate


@dataclass
class SemanticSearchResult:
    """Result from semantic memory search."""

    memory: SemanticMemoryModel
    similarity_score: float
    confidence_score: float
    combined_score: float


class SemanticMemoryManager:
    """
    Manages semantic memory - facts, knowledge, and patterns.

    Features:
    - Fact storage with confidence scores
    - Automatic embedding generation
    - Confidence decay over time
    - Evidence reinforcement/contradiction
    - Semantic similarity search
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        confidence_weight: float = 0.3,
        similarity_weight: float = 0.7,
        confidence_decay_rate: float = 0.01,  # Per day
    ):
        """
        Initialize semantic memory manager.

        Args:
            session: Database session
            embedding_service: Service for generating embeddings
            confidence_weight: Weight for confidence in combined score
            similarity_weight: Weight for similarity in combined score
            confidence_decay_rate: Daily confidence decay rate
        """
        self.session = session
        self.crud = SemanticMemoryCRUD(session)
        self._embedding_service = embedding_service
        self.confidence_weight = confidence_weight
        self.similarity_weight = similarity_weight
        self.confidence_decay_rate = confidence_decay_rate

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    async def store_fact(
        self,
        fact: str,
        fact_type: str,
        category: str | None = None,
        tags: list[str] | None = None,
        confidence: float = 1.0,
        source: str = "learned",
        source_description: str | None = None,
        supporting_execution: UUID | None = None,
        valid_until: datetime | None = None,
        generate_embedding: bool = True,
    ) -> SemanticMemoryModel:
        """
        Store a new fact in semantic memory.

        Args:
            fact: The fact/knowledge to store
            fact_type: Type (rule, constraint, pattern, etc.)
            category: Optional category
            tags: Optional tags for filtering
            confidence: Initial confidence (0-1)
            source: Source of fact (learned, configured, user_feedback, extracted)
            source_description: Additional source info
            supporting_execution: Execution that supports this fact
            valid_until: Expiration time (None = indefinite)
            generate_embedding: Whether to generate embedding

        Returns:
            Created semantic memory record
        """
        supporting_executions = [supporting_execution] if supporting_execution else []

        memory = await self.crud.create(
            SemanticMemoryCreate(
                fact=fact,
                fact_type=fact_type,
                category=category,
                tags=tags or [],
                confidence=max(0, min(1, confidence)),
                source=source,
                source_description=source_description,
                supporting_executions=supporting_executions,
                valid_until=valid_until,
            )
        )

        # Generate embedding if requested
        if generate_embedding:
            await self._update_embedding(memory.id, fact)

        return memory

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_confidence: float | None = None,
        fact_type: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> list[SemanticSearchResult]:
        """
        Search semantic memory by similarity.

        Args:
            query: Search query text
            limit: Maximum results
            min_confidence: Minimum confidence filter
            fact_type: Filter by fact type
            category: Filter by category
            tags: Filter by tags (any match)

        Returns:
            List of search results with combined scores
        """
        # Generate query embedding
        embedding_result = await self.embedding_service.embed(query)
        query_embedding = embedding_result.embedding

        # Search by embedding similarity
        results = await self.crud.search_by_embedding(
            embedding=query_embedding,
            limit=limit * 2,  # Get more for filtering
            min_confidence=min_confidence,
            fact_type=fact_type,
        )

        # Apply additional filters and calculate combined scores
        scored_results = []

        for memory, distance in results:
            # Filter by category if specified
            if category and memory.category != category:
                continue

            # Filter by tags if specified (any match)
            if tags and not any(tag in (memory.tags or []) for tag in tags):
                continue

            # Convert distance to similarity (0-1)
            similarity_score = max(0, 1 - distance)

            # Get confidence with decay applied
            confidence_score = self._apply_confidence_decay(memory)

            # Calculate combined score
            combined_score = (
                self.similarity_weight * similarity_score
                + self.confidence_weight * confidence_score
            )

            scored_results.append(
                SemanticSearchResult(
                    memory=memory,
                    similarity_score=similarity_score,
                    confidence_score=confidence_score,
                    combined_score=combined_score,
                )
            )

        # Record access for retrieved memories
        for result in scored_results[:limit]:
            await self.crud.record_access(result.memory.id)

        # Sort by combined score and limit
        scored_results.sort(key=lambda r: r.combined_score, reverse=True)
        return scored_results[:limit]

    async def get_facts_by_type(
        self,
        fact_type: str,
        limit: int = 50,
        min_confidence: float | None = None,
    ) -> list[SemanticMemoryModel]:
        """
        Get all facts of a specific type.

        Args:
            fact_type: Type of facts to retrieve
            limit: Maximum results
            min_confidence: Minimum confidence filter

        Returns:
            List of matching facts
        """
        return await self.crud.list(
            fact_type=fact_type,
            min_confidence=min_confidence,
            limit=limit,
        )

    async def get_facts_by_category(
        self,
        category: str,
        limit: int = 50,
        min_confidence: float | None = None,
    ) -> list[SemanticMemoryModel]:
        """
        Get all facts in a category.

        Args:
            category: Category to filter by
            limit: Maximum results
            min_confidence: Minimum confidence filter

        Returns:
            List of matching facts
        """
        return await self.crud.list(
            category=category,
            min_confidence=min_confidence,
            limit=limit,
        )

    async def reinforce(
        self,
        memory_id: UUID,
        execution_id: UUID,
    ) -> SemanticMemoryModel | None:
        """
        Reinforce a fact with supporting evidence.

        Increases confidence and records the supporting execution.

        Args:
            memory_id: ID of the memory to reinforce
            execution_id: ID of execution that supports this fact

        Returns:
            Updated memory or None if not found
        """
        return await self.crud.reinforce(memory_id, execution_id)

    async def contradict(
        self,
        memory_id: UUID,
        execution_id: UUID,
    ) -> SemanticMemoryModel | None:
        """
        Record contradicting evidence for a fact.

        Decreases confidence and records the contradicting execution.

        Args:
            memory_id: ID of the memory to contradict
            execution_id: ID of execution that contradicts this fact

        Returns:
            Updated memory or None if not found
        """
        return await self.crud.contradict(memory_id, execution_id)

    async def supersede(
        self,
        old_memory_id: UUID,
        new_fact: str,
        **kwargs: Any,
    ) -> tuple[SemanticMemoryModel | None, SemanticMemoryModel]:
        """
        Replace an old fact with a new one.

        The old fact is marked as superseded.

        Args:
            old_memory_id: ID of the memory to supersede
            new_fact: The new fact
            **kwargs: Additional arguments for store_fact

        Returns:
            Tuple of (old_memory, new_memory)
        """
        # Get the old memory
        old_memory = await self.crud.get(old_memory_id)

        # Create the new memory
        new_memory = await self.store_fact(fact=new_fact, **kwargs)

        # Mark old as superseded if it exists
        if old_memory:
            await self.crud.update(
                old_memory_id,
                SemanticMemoryUpdate(superseded_by=new_memory.id),
            )
            await self.session.refresh(old_memory)

        return old_memory, new_memory

    async def delete(self, memory_id: UUID) -> SemanticMemoryModel | None:
        """
        Soft delete a semantic memory.

        Args:
            memory_id: ID of the memory to delete

        Returns:
            Deleted memory or None if not found
        """
        return await self.crud.soft_delete(memory_id)

    async def update_confidence(
        self,
        memory_id: UUID,
        confidence: float,
    ) -> SemanticMemoryModel | None:
        """
        Directly update confidence of a memory.

        Args:
            memory_id: ID of the memory
            confidence: New confidence score (0-1)

        Returns:
            Updated memory or None if not found
        """
        return await self.crud.update(
            memory_id,
            SemanticMemoryUpdate(confidence=max(0, min(1, confidence))),
        )

    async def find_similar(
        self,
        fact: str,
        threshold: float = 0.8,
        limit: int = 5,
    ) -> list[SemanticSearchResult]:
        """
        Find similar existing facts.

        Useful for deduplication before storing new facts.

        Args:
            fact: The fact to find similar to
            threshold: Minimum similarity threshold
            limit: Maximum results

        Returns:
            List of similar facts above threshold
        """
        results = await self.search(query=fact, limit=limit)
        return [r for r in results if r.similarity_score >= threshold]

    async def count(self) -> int:
        """Count active semantic memories."""
        return await self.crud.count()

    def _apply_confidence_decay(
        self,
        memory: SemanticMemoryModel,
    ) -> float:
        """Apply time-based confidence decay."""
        if memory.confidence is None:
            return 0.5

        # Calculate days since last update
        now = datetime.utcnow()
        last_update = memory.updated_at or memory.created_at
        days_since_update = (now - last_update).total_seconds() / 86400

        # Apply exponential decay
        decayed_confidence = memory.confidence * (
            (1 - self.confidence_decay_rate) ** days_since_update
        )

        return max(0, min(1, decayed_confidence))

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

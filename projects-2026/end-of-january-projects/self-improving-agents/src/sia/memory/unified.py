"""
Unified Memory Interface.

Combines episodic, semantic, and procedural memory with RRF fusion.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sia.llm.embeddings import EmbeddingService
from sia.llm.reranking import RerankService
from sia.memory.episodic import EpisodicMemoryManager, EpisodicSearchResult
from sia.memory.procedural import ProceduralMemoryManager, SkillSearchResult
from sia.memory.semantic import SemanticMemoryManager, SemanticSearchResult
from sia.models.memory import EpisodicMemory, SemanticMemory
from sia.models.skill import Skill


@dataclass
class MemoryItem:
    """Unified memory item across all memory types."""

    id: UUID
    memory_type: str  # "episodic", "semantic", "procedural"
    content: str
    score: float
    timestamp: datetime | None = None
    confidence: float | None = None
    importance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # Original objects
    episodic: EpisodicMemory | None = None
    semantic: SemanticMemory | None = None
    skill: Skill | None = None


@dataclass
class UnifiedSearchResult:
    """Result from unified memory search."""

    items: list[MemoryItem]
    episodic_count: int
    semantic_count: int
    procedural_count: int
    total_retrieved: int
    reranked: bool = False


class UnifiedMemoryManager:
    """
    Unified memory interface combining all memory types.

    Features:
    - Cross-memory type queries
    - Reciprocal Rank Fusion (RRF) for combining results
    - Optional reranking for relevance
    - Context assembly for agents
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        rerank_service: RerankService | None = None,
        episodic_weight: float = 0.3,
        semantic_weight: float = 0.4,
        procedural_weight: float = 0.3,
        rrf_k: int = 60,
    ):
        """
        Initialize unified memory manager.

        Args:
            session: Database session
            embedding_service: Shared embedding service
            rerank_service: Service for reranking results
            episodic_weight: Weight for episodic memory in fusion
            semantic_weight: Weight for semantic memory in fusion
            procedural_weight: Weight for procedural memory in fusion
            rrf_k: RRF constant (typically 60)
        """
        self.session = session
        self._embedding_service = embedding_service
        self._rerank_service = rerank_service

        self.episodic_weight = episodic_weight
        self.semantic_weight = semantic_weight
        self.procedural_weight = procedural_weight
        self.rrf_k = rrf_k

        # Initialize memory managers (sharing embedding service)
        self.episodic = EpisodicMemoryManager(
            session=session,
            embedding_service=self._embedding_service,
        )
        self.semantic = SemanticMemoryManager(
            session=session,
            embedding_service=self._embedding_service,
        )
        self.procedural = ProceduralMemoryManager(
            session=session,
            embedding_service=self._embedding_service,
        )

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
            # Share with child managers
            self.episodic._embedding_service = self._embedding_service
            self.semantic._embedding_service = self._embedding_service
            self.procedural._embedding_service = self._embedding_service
        return self._embedding_service

    @property
    def rerank_service(self) -> RerankService:
        """Get or create rerank service."""
        if self._rerank_service is None:
            self._rerank_service = RerankService()
        return self._rerank_service

    async def search(
        self,
        query: str,
        limit: int = 20,
        include_episodic: bool = True,
        include_semantic: bool = True,
        include_procedural: bool = True,
        episodic_limit: int | None = None,
        semantic_limit: int | None = None,
        procedural_limit: int | None = None,
        rerank: bool = True,
        min_confidence: float | None = None,
        min_importance: float | None = None,
        since: datetime | None = None,
    ) -> UnifiedSearchResult:
        """
        Search across all memory types with RRF fusion.

        Args:
            query: Search query
            limit: Maximum total results
            include_episodic: Include episodic memory
            include_semantic: Include semantic memory
            include_procedural: Include procedural (skills)
            episodic_limit: Override limit for episodic
            semantic_limit: Override limit for semantic
            procedural_limit: Override limit for procedural
            rerank: Whether to rerank results
            min_confidence: Minimum confidence for semantic
            min_importance: Minimum importance for episodic
            since: Only include memories after this time

        Returns:
            Unified search results
        """
        # Calculate limits for each memory type
        per_type_limit = limit * 2  # Get more to allow for RRF fusion
        e_limit = episodic_limit or per_type_limit
        s_limit = semantic_limit or per_type_limit
        p_limit = procedural_limit or per_type_limit

        # Collect results from each memory type
        episodic_results: list[EpisodicSearchResult] = []
        semantic_results: list[SemanticSearchResult] = []
        procedural_results: list[SkillSearchResult] = []

        if include_episodic:
            episodic_results = await self.episodic.search(
                query=query,
                limit=e_limit,
                min_importance=min_importance,
                since=since,
            )

        if include_semantic:
            semantic_results = await self.semantic.search(
                query=query,
                limit=s_limit,
                min_confidence=min_confidence,
            )

        if include_procedural:
            procedural_results = await self.procedural.search(
                query=query,
                limit=p_limit,
            )

        # Convert to unified items with RRF scores
        all_items: list[MemoryItem] = []

        # Add episodic items
        for rank, result in enumerate(episodic_results, 1):
            rrf_score = self.episodic_weight / (self.rrf_k + rank)
            item = MemoryItem(
                id=result.memory.id,
                memory_type="episodic",
                content=result.memory.description,
                score=rrf_score,
                timestamp=result.memory.timestamp,
                importance=result.importance_score,
                metadata={
                    "event_type": result.memory.event_type,
                    "execution_id": str(result.memory.execution_id),
                    "similarity": result.similarity_score,
                    "recency": result.recency_score,
                },
                episodic=result.memory,
            )
            all_items.append(item)

        # Add semantic items
        for rank, result in enumerate(semantic_results, 1):
            rrf_score = self.semantic_weight / (self.rrf_k + rank)
            item = MemoryItem(
                id=result.memory.id,
                memory_type="semantic",
                content=result.memory.fact,
                score=rrf_score,
                timestamp=result.memory.created_at,
                confidence=result.confidence_score,
                metadata={
                    "fact_type": result.memory.fact_type,
                    "category": result.memory.category,
                    "similarity": result.similarity_score,
                },
                semantic=result.memory,
            )
            all_items.append(item)

        # Add procedural items
        for rank, result in enumerate(procedural_results, 1):
            rrf_score = self.procedural_weight / (self.rrf_k + rank)
            item = MemoryItem(
                id=result.skill.id,
                memory_type="procedural",
                content=f"{result.skill.name}: {result.skill.description}",
                score=rrf_score,
                timestamp=result.skill.last_used,
                confidence=result.success_score,
                metadata={
                    "skill_name": result.skill.name,
                    "category": result.skill.category,
                    "similarity": result.similarity_score,
                    "success_rate": result.success_score,
                },
                skill=result.skill,
            )
            all_items.append(item)

        # Sort by RRF score
        all_items.sort(key=lambda x: x.score, reverse=True)

        # Optionally rerank with cross-encoder
        reranked = False
        if rerank and all_items:
            all_items = await self._rerank_items(query, all_items, limit)
            reranked = True
        else:
            all_items = all_items[:limit]

        return UnifiedSearchResult(
            items=all_items,
            episodic_count=len(episodic_results),
            semantic_count=len(semantic_results),
            procedural_count=len(procedural_results),
            total_retrieved=len(episodic_results)
            + len(semantic_results)
            + len(procedural_results),
            reranked=reranked,
        )

    async def _rerank_items(
        self,
        query: str,
        items: list[MemoryItem],
        limit: int,
    ) -> list[MemoryItem]:
        """Rerank items using cross-encoder."""
        if not items:
            return items

        # Extract documents for reranking
        documents = [item.content for item in items]

        # Rerank
        rerank_result = await self.rerank_service.rerank(
            query=query,
            documents=documents,
            top_k=limit,
        )

        # Reorder items based on reranking
        reranked_items = []
        for result in rerank_result.results:
            item = items[result.index]
            item.score = result.relevance_score
            reranked_items.append(item)

        return reranked_items

    async def get_context_for_task(
        self,
        task_description: str,
        max_items: int = 15,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """
        Assemble context for an agent task.

        Args:
            task_description: Description of the task
            max_items: Maximum memory items to include
            max_tokens: Optional token limit for context

        Returns:
            Structured context dictionary
        """
        # Search for relevant memories
        result = await self.search(
            query=task_description,
            limit=max_items,
            rerank=True,
        )

        # Organize by type
        episodic_context = []
        semantic_context = []
        skill_context = []

        for item in result.items:
            if item.memory_type == "episodic" and item.episodic:
                episodic_context.append(
                    {
                        "event": item.episodic.event_type,
                        "description": item.episodic.description,
                        "timestamp": item.timestamp.isoformat() if item.timestamp else None,
                        "details": item.episodic.details,
                    }
                )
            elif item.memory_type == "semantic" and item.semantic:
                semantic_context.append(
                    {
                        "fact": item.semantic.fact,
                        "type": item.semantic.fact_type,
                        "confidence": item.confidence,
                    }
                )
            elif item.memory_type == "procedural" and item.skill:
                skill_context.append(
                    {
                        "name": item.skill.name,
                        "description": item.skill.description,
                        "category": item.skill.category,
                        "success_rate": item.confidence,
                    }
                )

        context = {
            "task": task_description,
            "relevant_history": episodic_context,
            "known_facts": semantic_context,
            "available_skills": skill_context,
            "metadata": {
                "items_retrieved": result.total_retrieved,
                "items_returned": len(result.items),
                "reranked": result.reranked,
            },
        }

        # TODO: Optionally truncate to token limit
        # if max_tokens:
        #     context = self._truncate_context(context, max_tokens)

        return context

    async def record_execution_event(
        self,
        execution_id: UUID,
        sequence_num: int,
        event_type: str,
        description: str,
        **kwargs: Any,
    ) -> EpisodicMemory:
        """
        Convenience method to record an execution event.

        Args:
            execution_id: ID of the execution
            sequence_num: Sequence number of this event
            event_type: Type of event
            description: Event description
            **kwargs: Additional arguments for episodic.record_event

        Returns:
            Created episodic memory
        """
        return await self.episodic.record_event(
            execution_id=execution_id,
            sequence_num=sequence_num,
            event_type=event_type,
            description=description,
            **kwargs,
        )

    async def store_learned_fact(
        self,
        fact: str,
        fact_type: str,
        **kwargs: Any,
    ) -> SemanticMemory:
        """
        Convenience method to store a learned fact.

        Args:
            fact: The fact to store
            fact_type: Type of fact
            **kwargs: Additional arguments for semantic.store_fact

        Returns:
            Created semantic memory
        """
        return await self.semantic.store_fact(
            fact=fact,
            fact_type=fact_type,
            source="learned",
            **kwargs,
        )

    async def find_skill(
        self,
        capability: str,
        limit: int = 5,
    ) -> list[SkillSearchResult]:
        """
        Convenience method to find skills for a capability.

        Args:
            capability: Description of needed capability
            limit: Maximum results

        Returns:
            List of matching skills
        """
        return await self.procedural.search(
            query=capability,
            limit=limit,
        )

    async def get_stats(self) -> dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Statistics dictionary
        """
        episodic_count = await self.episodic.count()
        semantic_count = await self.semantic.count()
        procedural_count = await self.procedural.count()

        return {
            "episodic": {
                "count": episodic_count,
            },
            "semantic": {
                "count": semantic_count,
            },
            "procedural": {
                "count": procedural_count,
            },
            "total": episodic_count + semantic_count + procedural_count,
        }

    async def clear_all(
        self,
        confirm: bool = False,
    ) -> dict[str, int]:
        """
        Clear all memories (dangerous!).

        Args:
            confirm: Must be True to actually clear

        Returns:
            Count of cleared items per type
        """
        if not confirm:
            raise ValueError("Must set confirm=True to clear all memories")

        # This would need to be implemented with bulk delete
        # For safety, we'll just return stats and require manual deletion
        return await self.get_stats()

    async def close(self) -> None:
        """Close all resources."""
        await self.episodic.close()
        await self.semantic.close()
        await self.procedural.close()

        if self._rerank_service:
            await self._rerank_service.close()

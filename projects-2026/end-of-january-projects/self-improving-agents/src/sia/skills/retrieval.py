"""
Skill Retrieval System.

Finds and retrieves skills based on capability needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.llm.embeddings import EmbeddingService
from sia.llm.reranking import RerankService
from sia.models.skill import Skill


@dataclass
class RetrievedSkill:
    """A skill retrieved with relevance scoring."""

    skill: Skill
    similarity_score: float
    success_score: float
    recency_score: float
    combined_score: float

    # Additional context
    dependency_count: int = 0
    dependent_count: int = 0


class SkillRetriever:
    """
    Retrieves skills based on semantic search and filtering.

    Features:
    - Semantic search by description
    - Category and tag filtering
    - Success-rate weighted ranking
    - Dependency-aware retrieval
    - Optional reranking
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        rerank_service: RerankService | None = None,
        similarity_weight: float = 0.5,
        success_weight: float = 0.35,
        recency_weight: float = 0.15,
        recency_decay_days: float = 30.0,
    ):
        """
        Initialize skill retriever.

        Args:
            session: Database session
            embedding_service: Service for generating embeddings
            rerank_service: Service for reranking results
            similarity_weight: Weight for semantic similarity
            success_weight: Weight for success rate
            recency_weight: Weight for recency
            recency_decay_days: Days after which recency score is ~0
        """
        self.session = session
        self._embedding_service = embedding_service
        self._rerank_service = rerank_service
        self.similarity_weight = similarity_weight
        self.success_weight = success_weight
        self.recency_weight = recency_weight
        self.recency_decay_days = recency_decay_days

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
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
        limit: int = 10,
        category: str | None = None,
        tags: list[str] | None = None,
        min_success_rate: float | None = None,
        status: str = "active",
        rerank: bool = True,
    ) -> list[RetrievedSkill]:
        """
        Search for skills matching a capability query.

        Args:
            query: Natural language description of needed capability
            limit: Maximum results
            category: Filter by category
            tags: Filter by tags (any match)
            min_success_rate: Minimum success rate filter
            status: Filter by status
            rerank: Whether to rerank results

        Returns:
            List of retrieved skills with scores
        """
        # Generate query embedding
        embedding_result = await self.embedding_service.embed(query)
        query_embedding = embedding_result.embedding

        # Build query with embedding similarity
        stmt = (
            select(
                Skill,
                Skill.embedding.cosine_distance(query_embedding).label("distance"),
            )
            .where(Skill.embedding.isnot(None))
            .where(Skill.status == status)
        )

        if category:
            stmt = stmt.where(Skill.category == category)

        if min_success_rate is not None:
            stmt = stmt.where(Skill.success_rate >= min_success_rate)

        # Get more results than needed for filtering/reranking
        stmt = stmt.order_by("distance").limit(limit * 3)

        result = await self.session.execute(stmt)
        rows = result.all()

        # Calculate combined scores
        now = datetime.utcnow()
        scored_results = []

        for skill, distance in rows:
            # Filter by tags if specified
            if tags and not any(tag in (skill.tags or []) for tag in tags):
                continue

            # Convert distance to similarity
            similarity_score = max(0, 1 - distance)

            # Get success rate score
            success_score = skill.success_rate or 0.5

            # Calculate recency score
            if skill.last_used:
                age_days = (now - skill.last_used).total_seconds() / 86400
                recency_score = max(0, 1 - (age_days / self.recency_decay_days)) ** 2
            else:
                recency_score = 0.3

            # Calculate combined score
            combined_score = (
                self.similarity_weight * similarity_score
                + self.success_weight * success_score
                + self.recency_weight * recency_score
            )

            scored_results.append(
                RetrievedSkill(
                    skill=skill,
                    similarity_score=similarity_score,
                    success_score=success_score,
                    recency_score=recency_score,
                    combined_score=combined_score,
                    dependency_count=len(skill.skill_dependencies or []),
                )
            )

        # Sort by combined score
        scored_results.sort(key=lambda r: r.combined_score, reverse=True)

        # Optionally rerank with cross-encoder
        if rerank and scored_results:
            scored_results = await self._rerank_results(query, scored_results, limit)
        else:
            scored_results = scored_results[:limit]

        return scored_results

    async def _rerank_results(
        self,
        query: str,
        results: list[RetrievedSkill],
        limit: int,
    ) -> list[RetrievedSkill]:
        """Rerank results using cross-encoder."""
        if not results:
            return results

        # Build documents for reranking
        documents = []
        for result in results:
            doc = f"{result.skill.name}: {result.skill.description}"
            documents.append(doc)

        # Rerank
        rerank_result = await self.rerank_service.rerank(
            query=query,
            documents=documents,
            top_k=limit,
        )

        # Reorder based on reranking
        reranked = []
        for item in rerank_result.results:
            result = results[item.index]
            # Update combined score with rerank score
            result.combined_score = (
                0.7 * item.relevance_score + 0.3 * result.combined_score
            )
            reranked.append(result)

        return reranked

    async def get_by_category(
        self,
        category: str,
        limit: int = 50,
        min_success_rate: float | None = None,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get all skills in a category.

        Args:
            category: Category to filter by
            limit: Maximum results
            min_success_rate: Minimum success rate
            status: Filter by status

        Returns:
            List of skills
        """
        stmt = (
            select(Skill)
            .where(Skill.category == category)
            .where(Skill.status == status)
        )

        if min_success_rate is not None:
            stmt = stmt.where(Skill.success_rate >= min_success_rate)

        stmt = stmt.order_by(Skill.success_rate.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_tags(
        self,
        tags: list[str],
        limit: int = 50,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get skills by tags (any match).

        Args:
            tags: Tags to search for
            limit: Maximum results
            status: Filter by status

        Returns:
            List of skills
        """
        stmt = (
            select(Skill)
            .where(Skill.tags.overlap(tags))
            .where(Skill.status == status)
            .order_by(Skill.success_rate.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dependencies(
        self,
        skill_id: UUID,
        recursive: bool = False,
    ) -> list[Skill]:
        """
        Get skills that a skill depends on.

        Args:
            skill_id: ID of the skill
            recursive: Whether to get transitive dependencies

        Returns:
            List of dependency skills
        """
        skill = await self.session.get(Skill, skill_id)
        if not skill or not skill.skill_dependencies:
            return []

        deps_to_fetch = set(skill.skill_dependencies)
        all_deps = []
        seen = set()

        while deps_to_fetch:
            stmt = select(Skill).where(Skill.id.in_(list(deps_to_fetch)))
            result = await self.session.execute(stmt)
            deps = list(result.scalars().all())
            all_deps.extend(deps)

            if not recursive:
                break

            # Get transitive dependencies
            deps_to_fetch = set()
            for dep in deps:
                if dep.id not in seen:
                    seen.add(dep.id)
                    if dep.skill_dependencies:
                        deps_to_fetch.update(
                            d for d in dep.skill_dependencies if d not in seen
                        )

        return all_deps

    async def get_dependents(
        self,
        skill_id: UUID,
    ) -> list[Skill]:
        """
        Get skills that depend on this skill.

        Args:
            skill_id: ID of the skill

        Returns:
            List of dependent skills
        """
        stmt = select(Skill).where(Skill.skill_dependencies.contains([skill_id]))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_most_used(
        self,
        limit: int = 10,
        category: str | None = None,
        days: int | None = None,
    ) -> list[Skill]:
        """
        Get most frequently used skills.

        Args:
            limit: Maximum results
            category: Optional category filter
            days: Only count recent usage (optional)

        Returns:
            List of most used skills
        """
        stmt = select(Skill).where(Skill.status == "active")

        if category:
            stmt = stmt.where(Skill.category == category)

        if days:
            since = datetime.utcnow() - timedelta(days=days)
            stmt = stmt.where(Skill.last_used >= since)

        stmt = stmt.order_by(Skill.usage_count.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_highest_success(
        self,
        limit: int = 10,
        min_usage: int = 5,
        category: str | None = None,
    ) -> list[Skill]:
        """
        Get skills with highest success rate.

        Args:
            limit: Maximum results
            min_usage: Minimum usage count for reliable stats
            category: Optional category filter

        Returns:
            List of most successful skills
        """
        stmt = (
            select(Skill)
            .where(Skill.status == "active")
            .where(Skill.usage_count >= min_usage)
        )

        if category:
            stmt = stmt.where(Skill.category == category)

        stmt = stmt.order_by(Skill.success_rate.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_categories(self) -> list[tuple[str, int]]:
        """
        Get all categories with skill counts.

        Returns:
            List of (category, count) tuples
        """
        stmt = (
            select(Skill.category, func.count(Skill.id))
            .where(Skill.status == "active")
            .where(Skill.category.isnot(None))
            .group_by(Skill.category)
            .order_by(func.count(Skill.id).desc())
        )

        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def close(self) -> None:
        """Close resources."""
        if self._embedding_service:
            await self._embedding_service.close()
        if self._rerank_service:
            await self._rerank_service.close()

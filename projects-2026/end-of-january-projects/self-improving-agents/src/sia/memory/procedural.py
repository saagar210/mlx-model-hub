"""
Procedural Memory System.

Manages retrieval of skills (stored procedures/routines).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.llm.embeddings import EmbeddingService
from sia.models.skill import Skill


@dataclass
class SkillSearchResult:
    """Result from skill search."""

    skill: Skill
    similarity_score: float
    success_score: float
    recency_score: float
    combined_score: float


class ProceduralMemoryManager:
    """
    Manages procedural memory - skills and routines.

    Features:
    - Skill retrieval by category
    - Semantic skill search
    - Success-rate weighted ranking
    - Recency-weighted retrieval
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        similarity_weight: float = 0.5,
        success_weight: float = 0.3,
        recency_weight: float = 0.2,
        recency_decay_days: float = 30.0,
    ):
        """
        Initialize procedural memory manager.

        Args:
            session: Database session
            embedding_service: Service for generating embeddings
            similarity_weight: Weight for similarity in combined score
            success_weight: Weight for success rate in combined score
            recency_weight: Weight for recency in combined score
            recency_decay_days: Days after which recency score is ~0
        """
        self.session = session
        self._embedding_service = embedding_service
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

    async def search(
        self,
        query: str,
        limit: int = 10,
        category: str | None = None,
        subcategory: str | None = None,
        tags: list[str] | None = None,
        min_success_rate: float | None = None,
        status: str = "active",
    ) -> list[SkillSearchResult]:
        """
        Search for skills by semantic similarity.

        Args:
            query: Search query describing needed capability
            limit: Maximum results
            category: Filter by category
            subcategory: Filter by subcategory
            tags: Filter by tags (any match)
            min_success_rate: Minimum success rate filter
            status: Filter by status (default: active)

        Returns:
            List of skill search results with combined scores
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

        if subcategory:
            stmt = stmt.where(Skill.subcategory == subcategory)

        if min_success_rate is not None:
            stmt = stmt.where(Skill.success_rate >= min_success_rate)

        stmt = stmt.order_by("distance").limit(limit * 2)

        result = await self.session.execute(stmt)
        rows = result.all()

        # Calculate combined scores
        now = datetime.utcnow()
        scored_results = []

        for skill, distance in rows:
            # Filter by tags if specified (any match)
            if tags and not any(tag in (skill.tags or []) for tag in tags):
                continue

            # Convert distance to similarity (0-1)
            similarity_score = max(0, 1 - distance)

            # Get success rate score
            success_score = skill.success_rate or 0.5

            # Calculate recency score based on last use
            if skill.last_used:
                age_days = (now - skill.last_used).total_seconds() / 86400
                recency_score = max(0, 1 - (age_days / self.recency_decay_days)) ** 2
            else:
                recency_score = 0.3  # Default for never-used skills

            # Calculate combined score
            combined_score = (
                self.similarity_weight * similarity_score
                + self.success_weight * success_score
                + self.recency_weight * recency_score
            )

            scored_results.append(
                SkillSearchResult(
                    skill=skill,
                    similarity_score=similarity_score,
                    success_score=success_score,
                    recency_score=recency_score,
                    combined_score=combined_score,
                )
            )

        # Sort by combined score and limit
        scored_results.sort(key=lambda r: r.combined_score, reverse=True)
        return scored_results[:limit]

    async def get_by_category(
        self,
        category: str,
        limit: int = 50,
        min_success_rate: float | None = None,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get skills by category.

        Args:
            category: Category to filter by
            limit: Maximum results
            min_success_rate: Minimum success rate filter
            status: Filter by status

        Returns:
            List of skills in category
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
        min_success_rate: float | None = None,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get skills by tags (any match).

        Args:
            tags: Tags to search for
            limit: Maximum results
            min_success_rate: Minimum success rate filter
            status: Filter by status

        Returns:
            List of skills with matching tags
        """
        stmt = (
            select(Skill)
            .where(Skill.tags.overlap(tags))
            .where(Skill.status == status)
        )

        if min_success_rate is not None:
            stmt = stmt.where(Skill.success_rate >= min_success_rate)

        stmt = stmt.order_by(Skill.success_rate.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_most_used(
        self,
        limit: int = 10,
        category: str | None = None,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get most frequently used skills.

        Args:
            limit: Maximum results
            category: Optional category filter
            status: Filter by status

        Returns:
            List of most used skills
        """
        stmt = select(Skill).where(Skill.status == status)

        if category:
            stmt = stmt.where(Skill.category == category)

        stmt = stmt.order_by(Skill.usage_count.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_most_successful(
        self,
        limit: int = 10,
        min_usage: int = 5,
        category: str | None = None,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get skills with highest success rate.

        Args:
            limit: Maximum results
            min_usage: Minimum usage count for reliable stats
            category: Optional category filter
            status: Filter by status

        Returns:
            List of most successful skills
        """
        stmt = (
            select(Skill)
            .where(Skill.status == status)
            .where(Skill.usage_count >= min_usage)
        )

        if category:
            stmt = stmt.where(Skill.category == category)

        stmt = stmt.order_by(Skill.success_rate.desc()).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recently_used(
        self,
        hours: int = 24,
        limit: int = 20,
        status: str = "active",
    ) -> list[Skill]:
        """
        Get recently used skills.

        Args:
            hours: How many hours back to look
            limit: Maximum results
            status: Filter by status

        Returns:
            List of recently used skills
        """
        from datetime import timedelta

        since = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(Skill)
            .where(Skill.status == status)
            .where(Skill.last_used >= since)
            .order_by(Skill.last_used.desc())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_skill(self, skill_id: UUID) -> Skill | None:
        """
        Get a skill by ID.

        Args:
            skill_id: ID of the skill

        Returns:
            Skill or None if not found
        """
        stmt = select(Skill).where(Skill.id == skill_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_skill_by_name(self, name: str) -> Skill | None:
        """
        Get a skill by name.

        Args:
            name: Name of the skill

        Returns:
            Skill or None if not found
        """
        stmt = select(Skill).where(Skill.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_dependencies(self, skill_id: UUID) -> list[Skill]:
        """
        Get skills that this skill depends on.

        Args:
            skill_id: ID of the skill

        Returns:
            List of dependency skills
        """
        skill = await self.get_skill(skill_id)
        if not skill or not skill.skill_dependencies:
            return []

        stmt = select(Skill).where(Skill.id.in_(skill.skill_dependencies))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_dependents(self, skill_id: UUID) -> list[Skill]:
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

    async def count(
        self,
        category: str | None = None,
        status: str | None = None,
    ) -> int:
        """
        Count skills.

        Args:
            category: Optional category filter
            status: Optional status filter

        Returns:
            Count of matching skills
        """
        stmt = select(func.count(Skill.id))

        if category:
            stmt = stmt.where(Skill.category == category)

        if status:
            stmt = stmt.where(Skill.status == status)

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_categories(self) -> list[str]:
        """
        Get all skill categories.

        Returns:
            List of category names
        """
        stmt = (
            select(Skill.category)
            .where(Skill.category.isnot(None))
            .distinct()
            .order_by(Skill.category)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def close(self) -> None:
        """Close resources."""
        if self._embedding_service:
            await self._embedding_service.close()

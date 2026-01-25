"""
Skill CRUD operations.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.skill import Skill
from sia.schemas.skill import SkillCreate, SkillUpdate


class SkillCRUD:
    """CRUD operations for skills."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: SkillCreate) -> Skill:
        """Create a new skill."""
        skill = Skill(
            name=data.name,
            description=data.description,
            category=data.category,
            subcategory=data.subcategory,
            tags=data.tags,
            code=data.code,
            signature=data.signature,
            input_schema=data.input_schema,
            output_schema=data.output_schema,
            python_dependencies=data.python_dependencies,
            skill_dependencies=data.skill_dependencies,
            discovered_from=data.discovered_from,
            extraction_method=data.extraction_method,
            human_curated=data.human_curated,
            example_inputs=data.example_inputs,
            example_outputs=data.example_outputs,
            documentation=data.documentation,
        )

        self.session.add(skill)
        await self.session.flush()
        await self.session.refresh(skill)
        return skill

    async def get(self, skill_id: UUID) -> Skill | None:
        """Get a skill by ID."""
        result = await self.session.execute(
            select(Skill).where(Skill.id == skill_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Skill | None:
        """Get a skill by name."""
        result = await self.session.execute(
            select(Skill).where(Skill.name == name)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        category: str | None = None,
        status: str | None = None,
        tags: list[str] | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Skill]:
        """List skills with optional filters."""
        query = select(Skill)

        if category:
            query = query.where(Skill.category == category)

        if status:
            query = query.where(Skill.status == status)

        if tags:
            # Skills that have any of the specified tags
            query = query.where(Skill.tags.overlap(tags))

        query = query.order_by(Skill.usage_count.desc(), Skill.name)
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, skill_id: UUID, data: SkillUpdate) -> Skill | None:
        """Update a skill."""
        skill = await self.get(skill_id)
        if not skill:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(skill, field, value)

        await self.session.flush()
        await self.session.refresh(skill)
        return skill

    async def deprecate(self, skill_id: UUID, reason: str | None = None) -> Skill | None:
        """Deprecate a skill."""
        skill = await self.get(skill_id)
        if not skill:
            return None

        skill.status = "deprecated"
        skill.deprecated_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(skill)
        return skill

    async def update_embedding(
        self,
        skill_id: UUID,
        embedding: list[float],
        embedding_model: str,
    ) -> Skill | None:
        """Update a skill's embedding."""
        skill = await self.get(skill_id)
        if not skill:
            return None

        skill.embedding = embedding
        skill.embedding_model = embedding_model

        await self.session.flush()
        await self.session.refresh(skill)
        return skill

    async def record_usage(
        self,
        skill_id: UUID,
        success: bool,
        execution_time_ms: float | None = None,
    ) -> Skill | None:
        """Record skill usage for statistics."""
        skill = await self.get(skill_id)
        if not skill:
            return None

        skill.usage_count += 1
        skill.last_used = datetime.utcnow()

        if success:
            skill.last_success = datetime.utcnow()
            # Update success rate
            total = skill.usage_count
            successes = total - skill.failure_count
            skill.success_rate = successes / total if total > 0 else 0
        else:
            skill.last_failure = datetime.utcnow()
            skill.failure_count += 1
            # Update success rate
            total = skill.usage_count
            successes = total - skill.failure_count
            skill.success_rate = successes / total if total > 0 else 0

        if execution_time_ms:
            # Update average execution time
            if skill.avg_execution_time_ms:
                skill.avg_execution_time_ms = (
                    skill.avg_execution_time_ms * (skill.usage_count - 1) + execution_time_ms
                ) / skill.usage_count
            else:
                skill.avg_execution_time_ms = execution_time_ms

        await self.session.flush()
        await self.session.refresh(skill)
        return skill

    async def count(
        self,
        category: str | None = None,
        status: str | None = None,
    ) -> int:
        """Count skills with optional filters."""
        query = select(func.count(Skill.id))

        if category:
            query = query.where(Skill.category == category)

        if status:
            query = query.where(Skill.status == status)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_by_category(self, category: str) -> list[Skill]:
        """Get all active skills in a category."""
        result = await self.session.execute(
            select(Skill)
            .where(Skill.category == category)
            .where(Skill.status == "active")
            .order_by(Skill.success_rate.desc())
        )
        return list(result.scalars().all())

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        min_success_rate: float | None = None,
        category: str | None = None,
    ) -> list[tuple[Skill, float]]:
        """Search skills by embedding similarity."""
        from pgvector.sqlalchemy import Vector

        query = (
            select(
                Skill,
                Skill.embedding.cosine_distance(embedding).label("distance"),
            )
            .where(Skill.embedding.isnot(None))
            .where(Skill.status.in_(["active", "experimental"]))
        )

        if min_success_rate is not None:
            query = query.where(Skill.success_rate >= min_success_rate)

        if category:
            query = query.where(Skill.category == category)

        query = query.order_by("distance").limit(limit)

        result = await self.session.execute(query)
        return [(row[0], row[1]) for row in result.all()]

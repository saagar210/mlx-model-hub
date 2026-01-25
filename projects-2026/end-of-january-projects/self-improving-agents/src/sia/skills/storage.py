"""
Skill Storage System.

Manages persistence and versioning of skills.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud.skill import SkillCRUD
from sia.llm.embeddings import EmbeddingService
from sia.models.skill import Skill
from sia.schemas.skill import SkillCreate, SkillUpdate
from sia.skills.discovery import DiscoveredSkill


class SkillStorage:
    """
    Manages skill storage with embeddings and deduplication.

    Features:
    - Store skills with embeddings for search
    - Deduplicate similar skills
    - Version skills on modification
    - Track skill dependencies
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
        similarity_threshold: float = 0.9,
    ):
        """
        Initialize skill storage.

        Args:
            session: Database session
            embedding_service: Service for generating embeddings
            similarity_threshold: Threshold for considering skills duplicates
        """
        self.session = session
        self.crud = SkillCRUD(session)
        self._embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold

    @property
    def embedding_service(self) -> EmbeddingService:
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = EmbeddingService()
        return self._embedding_service

    async def store(
        self,
        skill: DiscoveredSkill,
        check_duplicate: bool = True,
    ) -> tuple[Skill, bool]:
        """
        Store a discovered skill.

        Args:
            skill: Skill to store
            check_duplicate: Whether to check for duplicates

        Returns:
            Tuple of (stored_skill, is_new)
        """
        # Check for duplicates
        if check_duplicate:
            existing = await self.find_duplicate(skill)
            if existing:
                return existing, False

        # Generate embedding
        embedding_content = self._build_embedding_content(skill)
        embedding_result = await self.embedding_service.embed(embedding_content)

        # Create skill record
        skill_record = await self.crud.create(
            SkillCreate(
                name=skill.name,
                description=skill.description,
                category=skill.category,
                subcategory=skill.subcategory,
                tags=skill.tags,
                code=skill.code,
                signature=skill.signature,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                python_dependencies=skill.python_dependencies,
                discovered_from=skill.source_execution_id,
                extraction_method=skill.extraction_method,
                human_curated=False,
                status="experimental",
            )
        )

        # Update embedding
        await self.crud.update_embedding(
            skill_id=skill_record.id,
            embedding=embedding_result.embedding,
            embedding_model=embedding_result.model,
        )

        return skill_record, True

    async def store_many(
        self,
        skills: list[DiscoveredSkill],
        check_duplicates: bool = True,
    ) -> tuple[list[Skill], int, int]:
        """
        Store multiple skills.

        Args:
            skills: Skills to store
            check_duplicates: Whether to check for duplicates

        Returns:
            Tuple of (stored_skills, new_count, duplicate_count)
        """
        stored = []
        new_count = 0
        duplicate_count = 0

        for skill in skills:
            record, is_new = await self.store(skill, check_duplicate=check_duplicates)
            stored.append(record)
            if is_new:
                new_count += 1
            else:
                duplicate_count += 1

        return stored, new_count, duplicate_count

    async def find_duplicate(
        self,
        skill: DiscoveredSkill,
    ) -> Skill | None:
        """
        Find a duplicate skill by name or code hash.

        Args:
            skill: Skill to check

        Returns:
            Existing skill if duplicate found, None otherwise
        """
        # Check by name
        existing = await self.crud.get_by_name(skill.name)
        if existing:
            return existing

        # Check by code hash
        if skill.code:
            code_hash = hashlib.sha256(skill.code.encode()).hexdigest()[:32]
            existing = await self._find_by_code_hash(code_hash)
            if existing:
                return existing

        return None

    async def _find_by_code_hash(self, code_hash: str) -> Skill | None:
        """Find skill by code hash."""
        from sqlalchemy import select

        # Compute hash of all skill codes and compare
        # This is inefficient but works for small skill libraries
        # TODO: Add code_hash column to skills table for efficient lookup
        result = await self.session.execute(
            select(Skill).where(Skill.status.in_(["experimental", "active"]))
        )
        skills = result.scalars().all()

        for skill in skills:
            if skill.code:
                skill_hash = hashlib.sha256(skill.code.encode()).hexdigest()[:32]
                if skill_hash == code_hash:
                    return skill

        return None

    async def find_similar(
        self,
        skill: DiscoveredSkill,
        limit: int = 5,
    ) -> list[tuple[Skill, float]]:
        """
        Find similar existing skills by embedding similarity.

        Args:
            skill: Skill to find similar to
            limit: Maximum results

        Returns:
            List of (skill, similarity_score) tuples
        """
        # Generate embedding for comparison
        embedding_content = self._build_embedding_content(skill)
        embedding_result = await self.embedding_service.embed(embedding_content)

        # Search by embedding
        results = await self.crud.search_by_embedding(
            embedding=embedding_result.embedding,
            limit=limit,
        )

        # Convert distance to similarity
        return [(skill, 1 - distance) for skill, distance in results]

    async def update(
        self,
        skill_id: UUID,
        updates: dict[str, Any],
    ) -> Skill | None:
        """
        Update a skill.

        Args:
            skill_id: ID of skill to update
            updates: Fields to update

        Returns:
            Updated skill or None if not found
        """
        return await self.crud.update(skill_id, SkillUpdate(**updates))

    async def activate(self, skill_id: UUID) -> Skill | None:
        """
        Activate an experimental skill.

        Args:
            skill_id: ID of skill to activate

        Returns:
            Updated skill or None if not found
        """
        return await self.crud.update(skill_id, SkillUpdate(status="active"))

    async def deprecate(
        self,
        skill_id: UUID,
        reason: str | None = None,
    ) -> Skill | None:
        """
        Deprecate a skill.

        Args:
            skill_id: ID of skill to deprecate
            reason: Optional reason for deprecation

        Returns:
            Updated skill or None if not found
        """
        return await self.crud.update(
            skill_id,
            SkillUpdate(
                status="deprecated",
                deprecated_at=datetime.utcnow(),
            ),
        )

    async def record_usage(
        self,
        skill_id: UUID,
        success: bool,
    ) -> Skill | None:
        """
        Record skill usage.

        Args:
            skill_id: ID of skill used
            success: Whether usage was successful

        Returns:
            Updated skill or None if not found
        """
        return await self.crud.record_usage(skill_id, success)

    async def get(self, skill_id: UUID) -> Skill | None:
        """Get skill by ID."""
        return await self.crud.get(skill_id)

    async def get_by_name(self, name: str) -> Skill | None:
        """Get skill by name."""
        return await self.crud.get_by_name(name)

    async def list(
        self,
        category: str | None = None,
        status: str = "active",
        limit: int = 100,
    ) -> list[Skill]:
        """
        List skills with optional filters.

        Args:
            category: Filter by category
            status: Filter by status
            limit: Maximum results

        Returns:
            List of skills
        """
        return await self.crud.list(
            category=category,
            status=status,
            limit=limit,
        )

    async def delete(self, skill_id: UUID) -> bool:
        """
        Delete a skill (hard delete).

        Args:
            skill_id: ID of skill to delete

        Returns:
            True if deleted, False if not found
        """
        return await self.crud.delete(skill_id)

    def _build_embedding_content(self, skill: DiscoveredSkill) -> str:
        """Build text content for embedding generation."""
        parts = [
            f"Skill: {skill.name}",
            f"Description: {skill.description}",
            f"Category: {skill.category}",
        ]

        if skill.subcategory:
            parts.append(f"Subcategory: {skill.subcategory}")

        if skill.tags:
            parts.append(f"Tags: {', '.join(skill.tags)}")

        if skill.signature:
            parts.append(f"Signature: {skill.signature}")

        return "\n".join(parts)

    async def close(self) -> None:
        """Close resources."""
        if self._embedding_service:
            await self._embedding_service.close()

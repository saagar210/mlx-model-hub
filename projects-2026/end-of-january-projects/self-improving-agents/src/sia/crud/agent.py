"""
Agent CRUD operations.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.agent import Agent
from sia.schemas.agent import AgentCreate, AgentUpdate


class AgentCRUD:
    """CRUD operations for agents."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: AgentCreate) -> Agent:
        """Create a new agent."""
        # Calculate code hash
        code_content = data.code_snapshot or data.original_code
        code_hash = hashlib.sha256(code_content.encode()).hexdigest()

        agent = Agent(
            name=data.name,
            version=data.version,
            description=data.description,
            type=data.type,
            code_module=data.code_module,
            code_snapshot=data.code_snapshot,
            code_hash=code_hash,
            original_code=data.original_code,
            system_prompt=data.system_prompt,
            task_prompt_template=data.task_prompt_template,
            config=data.config,
            max_retries=data.max_retries,
            timeout_seconds=data.timeout_seconds,
            preferred_model=data.preferred_model,
            fallback_models=data.fallback_models,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
        )

        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def get(self, agent_id: UUID) -> Agent | None:
        """Get an agent by ID."""
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        name: str,
        version: str | None = None,
        active_only: bool = True,
    ) -> Agent | None:
        """Get an agent by name and optionally version."""
        query = select(Agent).where(Agent.name == name)

        if version:
            query = query.where(Agent.version == version)
        else:
            # Get latest version
            query = query.order_by(Agent.created_at.desc())

        if active_only:
            query = query.where(Agent.retired_at.is_(None))

        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def list(
        self,
        status: str | None = None,
        type: str | None = None,
        skip: int = 0,
        limit: int = 100,
        include_retired: bool = False,
    ) -> list[Agent]:
        """List agents with optional filters."""
        query = select(Agent)

        if not include_retired:
            query = query.where(Agent.retired_at.is_(None))

        if status:
            query = query.where(Agent.status == status)

        if type:
            query = query.where(Agent.type == type)

        query = query.order_by(Agent.name, Agent.version.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, agent_id: UUID, data: AgentUpdate) -> Agent | None:
        """Update an agent."""
        agent = await self.get(agent_id)
        if not agent:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(agent, field, value)

        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def retire(self, agent_id: UUID) -> Agent | None:
        """Retire an agent (soft delete)."""
        from datetime import datetime

        agent = await self.get(agent_id)
        if not agent:
            return None

        agent.status = "retired"
        agent.retired_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(agent)
        return agent

    async def count(
        self,
        status: str | None = None,
        include_retired: bool = False,
    ) -> int:
        """Count agents with optional filters."""
        from sqlalchemy import func

        query = select(func.count(Agent.id))

        if not include_retired:
            query = query.where(Agent.retired_at.is_(None))

        if status:
            query = query.where(Agent.status == status)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_best_version(self, name: str) -> Agent | None:
        """Get the best performing version of an agent."""
        result = await self.session.execute(
            select(Agent)
            .where(Agent.name == name)
            .where(Agent.status == "active")
            .where(Agent.retired_at.is_(None))
            .where(Agent.total_executions >= 10)  # Minimum sample size
            .order_by(Agent.success_rate.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_version(
        self,
        parent_agent: Agent,
        new_version: str,
        code_snapshot: str,
        **updates: Any,
    ) -> Agent:
        """Create a new version of an agent."""
        code_hash = hashlib.sha256(code_snapshot.encode()).hexdigest()

        agent = Agent(
            name=parent_agent.name,
            version=new_version,
            description=parent_agent.description,
            type=parent_agent.type,
            code_module=parent_agent.code_module,
            code_snapshot=code_snapshot,
            code_hash=code_hash,
            original_code=parent_agent.original_code,
            system_prompt=parent_agent.system_prompt,
            task_prompt_template=parent_agent.task_prompt_template,
            config=parent_agent.config,
            max_retries=parent_agent.max_retries,
            timeout_seconds=parent_agent.timeout_seconds,
            preferred_model=parent_agent.preferred_model,
            fallback_models=parent_agent.fallback_models,
            temperature=parent_agent.temperature,
            max_tokens=parent_agent.max_tokens,
            available_skills=parent_agent.available_skills,
            dspy_optimized_prompts=parent_agent.dspy_optimized_prompts,
            parent_version_id=parent_agent.id,
            status="testing",  # New versions start in testing
            **updates,
        )

        self.session.add(agent)
        await self.session.flush()
        await self.session.refresh(agent)
        return agent

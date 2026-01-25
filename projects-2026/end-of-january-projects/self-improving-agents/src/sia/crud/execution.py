"""
Execution CRUD operations.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.execution import Execution
from sia.schemas.execution import ExecutionCreate, ExecutionUpdate


class ExecutionCRUD:
    """CRUD operations for executions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: ExecutionCreate) -> Execution:
        """Create a new execution record."""
        execution = Execution(
            agent_id=data.agent_id,
            task_type=data.task_type,
            task_description=data.task_description,
            task_params=data.task_params,
            input_data=data.input_data,
            parent_execution_id=data.parent_execution_id,
            root_execution_id=data.parent_execution_id,  # Will be updated if needed
            request_id=data.request_id,
            random_seed=data.random_seed,
        )

        # If this is a subtask, inherit the root execution ID
        if data.parent_execution_id:
            parent = await self.get(data.parent_execution_id)
            if parent:
                execution.root_execution_id = parent.root_execution_id or parent.id

        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def get(self, execution_id: UUID) -> Execution | None:
        """Get an execution by ID."""
        result = await self.session.execute(
            select(Execution).where(Execution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        agent_id: UUID | None = None,
        task_type: str | None = None,
        success: bool | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Execution]:
        """List executions with optional filters."""
        query = select(Execution)

        if agent_id:
            query = query.where(Execution.agent_id == agent_id)

        if task_type:
            query = query.where(Execution.task_type == task_type)

        if success is not None:
            query = query.where(Execution.success == success)

        if since:
            query = query.where(Execution.started_at >= since)

        if until:
            query = query.where(Execution.started_at <= until)

        query = query.order_by(Execution.started_at.desc())
        query = query.offset(skip).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(self, execution_id: UUID, data: ExecutionUpdate) -> Execution | None:
        """Update an execution."""
        execution = await self.get(execution_id)
        if not execution:
            return None

        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(execution, field, value)

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def complete(
        self,
        execution_id: UUID,
        success: bool,
        output_data: dict | None = None,
        error_message: str | None = None,
        error_type: str | None = None,
        **metrics,
    ) -> Execution | None:
        """Mark an execution as complete."""
        execution = await self.get(execution_id)
        if not execution:
            return None

        execution.success = success
        execution.completed_at = datetime.utcnow()
        execution.output_data = output_data
        execution.error_message = error_message
        execution.error_type = error_type

        # Calculate execution time
        if execution.started_at:
            execution.execution_time_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )

        # Set additional metrics
        for key, value in metrics.items():
            if hasattr(execution, key):
                setattr(execution, key, value)

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def add_step(
        self,
        execution_id: UUID,
        step_num: int,
        action: str,
        result: dict,
    ) -> Execution | None:
        """Add an intermediate step to an execution."""
        execution = await self.get(execution_id)
        if not execution:
            return None

        step = {
            "step_num": step_num,
            "action": action,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }

        execution.intermediate_steps = [*execution.intermediate_steps, step]

        await self.session.flush()
        await self.session.refresh(execution)
        return execution

    async def count(
        self,
        agent_id: UUID | None = None,
        success: bool | None = None,
        since: datetime | None = None,
    ) -> int:
        """Count executions with optional filters."""
        query = select(func.count(Execution.id))

        if agent_id:
            query = query.where(Execution.agent_id == agent_id)

        if success is not None:
            query = query.where(Execution.success == success)

        if since:
            query = query.where(Execution.started_at >= since)

        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_recent_successful(
        self,
        agent_id: UUID,
        limit: int = 100,
    ) -> list[Execution]:
        """Get recent successful executions for training data."""
        result = await self.session.execute(
            select(Execution)
            .where(Execution.agent_id == agent_id)
            .where(Execution.success == True)  # noqa: E712
            .order_by(Execution.completed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_agent_stats(self, agent_id: UUID) -> dict:
        """Get execution statistics for an agent."""
        result = await self.session.execute(
            select(
                func.count(Execution.id).label("total"),
                func.count(Execution.id).filter(Execution.success == True).label("successful"),  # noqa: E712
                func.avg(Execution.execution_time_ms).label("avg_time"),
                func.avg(Execution.tokens_total).label("avg_tokens"),
                func.sum(Execution.tokens_total).label("total_tokens"),
            ).where(Execution.agent_id == agent_id)
        )
        row = result.one()

        return {
            "total_executions": row.total or 0,
            "successful_executions": row.successful or 0,
            "success_rate": (row.successful / row.total) if row.total else 0,
            "avg_execution_time_ms": float(row.avg_time) if row.avg_time else 0,
            "avg_tokens_used": float(row.avg_tokens) if row.avg_tokens else 0,
            "total_tokens_used": row.total_tokens or 0,
        }

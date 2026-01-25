"""Execution API routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud import ExecutionCRUD
from sia.db import get_db
from sia.schemas.common import PaginatedResponse
from sia.schemas.execution import ExecutionCreate, ExecutionList, ExecutionRead

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ExecutionList])
async def list_executions(
    agent_id: UUID | None = None,
    task_type: str | None = None,
    success: bool | None = None,
    since: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ExecutionList]:
    """List executions with optional filters."""
    crud = ExecutionCRUD(db)

    executions = await crud.list(
        agent_id=agent_id,
        task_type=task_type,
        success=success,
        since=since,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = await crud.count(agent_id=agent_id, success=success, since=since)

    return PaginatedResponse.create(
        items=[ExecutionList.model_validate(e) for e in executions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ExecutionRead, status_code=201)
async def create_execution(
    data: ExecutionCreate,
    db: AsyncSession = Depends(get_db),
) -> ExecutionRead:
    """Create a new execution record."""
    from sia.crud import AgentCRUD

    # Verify agent exists
    agent_crud = AgentCRUD(db)
    agent = await agent_crud.get(data.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    crud = ExecutionCRUD(db)
    execution = await crud.create(data)

    return ExecutionRead.model_validate(execution)


@router.get("/{execution_id}", response_model=ExecutionRead)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ExecutionRead:
    """Get an execution by ID."""
    crud = ExecutionCRUD(db)
    execution = await crud.get(execution_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionRead.model_validate(execution)


@router.get("/{execution_id}/trace")
async def get_execution_trace(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the full trace of an execution including episodic memories."""
    from sia.crud import EpisodicMemoryCRUD

    exec_crud = ExecutionCRUD(db)
    execution = await exec_crud.get(execution_id)

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    mem_crud = EpisodicMemoryCRUD(db)
    memories = await mem_crud.list_by_execution(execution_id)

    return {
        "execution": ExecutionRead.model_validate(execution),
        "trace": [
            {
                "sequence": m.sequence_num,
                "timestamp": m.timestamp.isoformat(),
                "event_type": m.event_type,
                "description": m.description,
                "details": m.details,
            }
            for m in memories
        ],
        "steps": execution.intermediate_steps,
    }


@router.post("/{execution_id}/complete")
async def complete_execution(
    execution_id: UUID,
    success: bool,
    output_data: dict | None = None,
    error_message: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Mark an execution as complete."""
    crud = ExecutionCRUD(db)

    execution = await crud.complete(
        execution_id=execution_id,
        success=success,
        output_data=output_data,
        error_message=error_message,
    )

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    return ExecutionRead.model_validate(execution)

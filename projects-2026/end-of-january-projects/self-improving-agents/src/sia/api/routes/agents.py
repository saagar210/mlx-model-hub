"""Agent API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud import AgentCRUD
from sia.db import get_db
from sia.schemas.agent import AgentCreate, AgentList, AgentRead, AgentUpdate
from sia.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[AgentList])
async def list_agents(
    status: str | None = None,
    type: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AgentList]:
    """List all agents with optional filters."""
    crud = AgentCRUD(db)

    agents = await crud.list(
        status=status,
        type=type,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = await crud.count(status=status)

    return PaginatedResponse.create(
        items=[AgentList.model_validate(a) for a in agents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AgentRead, status_code=201)
async def create_agent(
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentRead:
    """Create a new agent."""
    crud = AgentCRUD(db)

    # Check if agent with same name/version exists
    existing = await crud.get_by_name(data.name, data.version)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Agent '{data.name}' version '{data.version}' already exists",
        )

    agent = await crud.create(data)
    return AgentRead.model_validate(agent)


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AgentRead:
    """Get an agent by ID."""
    crud = AgentCRUD(db)
    agent = await crud.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentRead.model_validate(agent)


@router.get("/name/{name}", response_model=AgentRead)
async def get_agent_by_name(
    name: str,
    version: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> AgentRead:
    """Get an agent by name (optionally by version)."""
    crud = AgentCRUD(db)
    agent = await crud.get_by_name(name, version)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentRead.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentRead:
    """Update an agent."""
    crud = AgentCRUD(db)
    agent = await crud.update(agent_id, data)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentRead.model_validate(agent)


@router.delete("/{agent_id}", status_code=204)
async def retire_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Retire an agent (soft delete)."""
    crud = AgentCRUD(db)
    agent = await crud.retire(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/{agent_id}/stats")
async def get_agent_stats(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for an agent."""
    from sia.crud import ExecutionCRUD

    agent_crud = AgentCRUD(db)
    agent = await agent_crud.get(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    exec_crud = ExecutionCRUD(db)
    stats = await exec_crud.get_agent_stats(agent_id)

    return {
        "agent_id": str(agent_id),
        "name": agent.name,
        "version": agent.version,
        **stats,
    }

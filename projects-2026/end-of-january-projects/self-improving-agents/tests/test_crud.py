"""Tests for CRUD operations."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud import AgentCRUD, ExecutionCRUD, SkillCRUD
from sia.schemas.agent import AgentCreate
from sia.schemas.execution import ExecutionCreate
from sia.schemas.skill import SkillCreate


@pytest.mark.asyncio
async def test_agent_crud_create(db_session: AsyncSession, sample_agent_data: dict):
    """Test creating an agent."""
    crud = AgentCRUD(db_session)

    # Create unique name for this test
    sample_agent_data["name"] = f"test_agent_create_{id(db_session)}"

    agent = await crud.create(AgentCreate(**sample_agent_data))

    assert agent is not None
    assert agent.name == sample_agent_data["name"]
    assert agent.version == sample_agent_data["version"]
    assert agent.type == sample_agent_data["type"]


@pytest.mark.asyncio
async def test_agent_crud_get(db_session: AsyncSession, sample_agent_data: dict):
    """Test getting an agent by ID."""
    crud = AgentCRUD(db_session)

    sample_agent_data["name"] = f"test_agent_get_{id(db_session)}"
    agent = await crud.create(AgentCreate(**sample_agent_data))

    fetched = await crud.get(agent.id)

    assert fetched is not None
    assert fetched.id == agent.id
    assert fetched.name == agent.name


@pytest.mark.asyncio
async def test_agent_crud_get_by_name(db_session: AsyncSession, sample_agent_data: dict):
    """Test getting an agent by name."""
    crud = AgentCRUD(db_session)

    sample_agent_data["name"] = f"test_agent_byname_{id(db_session)}"
    agent = await crud.create(AgentCreate(**sample_agent_data))

    fetched = await crud.get_by_name(agent.name)

    assert fetched is not None
    assert fetched.name == agent.name


@pytest.mark.asyncio
async def test_agent_crud_list(db_session: AsyncSession, sample_agent_data: dict):
    """Test listing agents."""
    crud = AgentCRUD(db_session)

    # Create a few agents
    for i in range(3):
        data = sample_agent_data.copy()
        data["name"] = f"test_agent_list_{id(db_session)}_{i}"
        await crud.create(AgentCreate(**data))

    agents = await crud.list()

    assert len(agents) >= 3


@pytest.mark.asyncio
async def test_skill_crud_create(db_session: AsyncSession, sample_skill_data: dict):
    """Test creating a skill."""
    crud = SkillCRUD(db_session)

    sample_skill_data["name"] = f"test_skill_create_{id(db_session)}"
    skill = await crud.create(SkillCreate(**sample_skill_data))

    assert skill is not None
    assert skill.name == sample_skill_data["name"]
    assert skill.category == sample_skill_data["category"]


@pytest.mark.asyncio
async def test_skill_crud_get_by_name(db_session: AsyncSession, sample_skill_data: dict):
    """Test getting a skill by name."""
    crud = SkillCRUD(db_session)

    sample_skill_data["name"] = f"test_skill_byname_{id(db_session)}"
    skill = await crud.create(SkillCreate(**sample_skill_data))

    fetched = await crud.get_by_name(skill.name)

    assert fetched is not None
    assert fetched.name == skill.name


@pytest.mark.asyncio
async def test_execution_crud_create(db_session: AsyncSession, sample_agent_data: dict):
    """Test creating an execution."""
    # First create an agent
    agent_crud = AgentCRUD(db_session)
    sample_agent_data["name"] = f"test_agent_exec_{id(db_session)}"
    agent = await agent_crud.create(AgentCreate(**sample_agent_data))

    # Then create an execution
    exec_crud = ExecutionCRUD(db_session)
    execution = await exec_crud.create(ExecutionCreate(
        agent_id=agent.id,
        task_type="test",
        task_description="Test execution",
        input_data={"query": "test"},
    ))

    assert execution is not None
    assert execution.agent_id == agent.id
    assert execution.task_type == "test"


@pytest.mark.asyncio
async def test_execution_crud_complete(db_session: AsyncSession, sample_agent_data: dict):
    """Test completing an execution."""
    # Create agent and execution
    agent_crud = AgentCRUD(db_session)
    sample_agent_data["name"] = f"test_agent_complete_{id(db_session)}"
    agent = await agent_crud.create(AgentCreate(**sample_agent_data))

    exec_crud = ExecutionCRUD(db_session)
    execution = await exec_crud.create(ExecutionCreate(
        agent_id=agent.id,
        task_type="test",
        task_description="Test completion",
        input_data={"query": "test"},
    ))

    # Complete the execution
    completed = await exec_crud.complete(
        execution_id=execution.id,
        success=True,
        output_data={"result": "success"},
    )

    assert completed is not None
    assert completed.success is True
    assert completed.completed_at is not None
    assert completed.output_data == {"result": "success"}

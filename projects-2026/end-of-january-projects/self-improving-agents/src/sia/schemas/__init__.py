"""
SIA Pydantic Schemas

Request/response schemas for API and internal use.
"""

from sia.schemas.agent import AgentCreate, AgentRead, AgentUpdate, AgentList
from sia.schemas.common import PaginationParams, PaginatedResponse
from sia.schemas.execution import ExecutionCreate, ExecutionRead, ExecutionUpdate
from sia.schemas.memory import (
    EpisodicMemoryCreate,
    EpisodicMemoryRead,
    SemanticMemoryCreate,
    SemanticMemoryRead,
)
from sia.schemas.skill import SkillCreate, SkillRead, SkillUpdate, SkillSearch

__all__ = [
    # Agent
    "AgentCreate",
    "AgentRead",
    "AgentUpdate",
    "AgentList",
    # Execution
    "ExecutionCreate",
    "ExecutionRead",
    "ExecutionUpdate",
    # Skill
    "SkillCreate",
    "SkillRead",
    "SkillUpdate",
    "SkillSearch",
    # Memory
    "EpisodicMemoryCreate",
    "EpisodicMemoryRead",
    "SemanticMemoryCreate",
    "SemanticMemoryRead",
    # Common
    "PaginationParams",
    "PaginatedResponse",
]

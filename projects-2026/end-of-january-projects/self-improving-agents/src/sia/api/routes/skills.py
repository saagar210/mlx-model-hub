"""Skill API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sia.crud import SkillCRUD
from sia.db import get_db
from sia.schemas.common import PaginatedResponse
from sia.schemas.skill import SkillCreate, SkillList, SkillRead, SkillSearch, SkillUpdate

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SkillList])
async def list_skills(
    category: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SkillList]:
    """List skills with optional filters."""
    crud = SkillCRUD(db)

    skills = await crud.list(
        category=category,
        status=status,
        skip=(page - 1) * page_size,
        limit=page_size,
    )
    total = await crud.count(category=category, status=status)

    return PaginatedResponse.create(
        items=[SkillList.model_validate(s) for s in skills],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SkillRead, status_code=201)
async def create_skill(
    data: SkillCreate,
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    """Create a new skill."""
    crud = SkillCRUD(db)

    # Check if skill with same name exists
    existing = await crud.get_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Skill '{data.name}' already exists",
        )

    skill = await crud.create(data)
    return SkillRead.model_validate(skill)


@router.get("/{skill_id}", response_model=SkillRead)
async def get_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    """Get a skill by ID."""
    crud = SkillCRUD(db)
    skill = await crud.get(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillRead.model_validate(skill)


@router.get("/name/{name}", response_model=SkillRead)
async def get_skill_by_name(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    """Get a skill by name."""
    crud = SkillCRUD(db)
    skill = await crud.get_by_name(name)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillRead.model_validate(skill)


@router.patch("/{skill_id}", response_model=SkillRead)
async def update_skill(
    skill_id: UUID,
    data: SkillUpdate,
    db: AsyncSession = Depends(get_db),
) -> SkillRead:
    """Update a skill."""
    crud = SkillCRUD(db)
    skill = await crud.update(skill_id, data)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    return SkillRead.model_validate(skill)


@router.delete("/{skill_id}", status_code=204)
async def deprecate_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deprecate a skill."""
    crud = SkillCRUD(db)
    skill = await crud.deprecate(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")


@router.post("/search")
async def search_skills(
    data: SkillSearch,
    db: AsyncSession = Depends(get_db),
):
    """Search skills by description using embeddings."""
    from sia.llm import EmbeddingService

    crud = SkillCRUD(db)

    # Generate query embedding
    embedding_service = EmbeddingService()
    try:
        result = await embedding_service.embed(data.query)
        query_embedding = result.embedding
    finally:
        await embedding_service.close()

    # Search by embedding
    results = await crud.search_by_embedding(
        embedding=query_embedding,
        limit=data.limit,
        min_success_rate=data.min_success_rate,
        category=data.category,
    )

    return {
        "query": data.query,
        "results": [
            {
                "skill": SkillList.model_validate(skill),
                "distance": distance,
                "relevance_score": 1 - distance,  # Convert distance to similarity
            }
            for skill, distance in results
        ],
    }

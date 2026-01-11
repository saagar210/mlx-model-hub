"""Model registry API endpoints."""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import SQLModel, select

from mlx_hub.db.enums import TaskType
from mlx_hub.db.models import Model, ModelVersion
from mlx_hub.db.session import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


# Request/Response schemas
class ModelCreate(SQLModel):
    """Request schema for creating a model."""

    name: str
    task_type: TaskType = TaskType.TEXT_GENERATION
    description: str | None = None
    base_model: str
    tags: dict = {}


class ModelUpdate(SQLModel):
    """Request schema for updating a model."""

    description: str | None = None
    tags: dict | None = None


class ModelResponse(SQLModel):
    """Response schema for a model."""

    id: UUID
    name: str
    task_type: TaskType
    description: str | None
    base_model: str
    tags: dict
    mlflow_experiment_id: str | None
    created_at: datetime
    updated_at: datetime
    version_count: int = 0


class ModelListResponse(SQLModel):
    """Response schema for model list."""

    items: list[ModelResponse]
    total: int
    page: int
    page_size: int


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ModelResponse)
async def create_model(
    model_in: ModelCreate,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> ModelResponse:
    """Register a new model in the hub.

    Creates a new model record and optionally creates an MLflow experiment
    for tracking training runs.
    """
    # Check for duplicate name
    existing = await session.execute(
        select(Model).where(Model.name == model_in.name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model with name '{model_in.name}' already exists",
        )

    # Create model
    model = Model(**model_in.model_dump())
    session.add(model)
    await session.commit()
    await session.refresh(model)

    # Schedule MLflow experiment creation in background
    # This will be implemented when we integrate MLflow (Task 3.3)

    return ModelResponse(
        **model.model_dump(),
        version_count=0,
    )


@router.get("", response_model=ModelListResponse)
async def list_models(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    task_type: TaskType | None = None,
) -> ModelListResponse:
    """List all registered models with pagination."""
    # Build query
    query = select(Model)
    count_query = select(func.count()).select_from(Model)

    if task_type:
        query = query.where(Model.task_type == task_type)
        count_query = count_query.where(Model.task_type == task_type)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Model.created_at.desc())

    result = await session.execute(query)
    models = result.scalars().all()

    # Build response items with version counts
    items = []
    for model in models:
        # Count versions for each model
        version_count_result = await session.execute(
            select(func.count()).select_from(ModelVersion).where(
                ModelVersion.model_id == model.id
            )
        )
        version_count = version_count_result.scalar() or 0

        items.append(ModelResponse(
            **model.model_dump(),
            version_count=version_count,
        ))

    return ModelListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: UUID,
    session: SessionDep,
) -> ModelResponse:
    """Get a specific model by ID."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    # Count versions
    version_count_result = await session.execute(
        select(func.count()).select_from(ModelVersion).where(
            ModelVersion.model_id == model.id
        )
    )
    version_count = version_count_result.scalar() or 0

    return ModelResponse(
        **model.model_dump(),
        version_count=version_count,
    )


@router.patch("/{model_id}", response_model=ModelResponse)
async def update_model(
    model_id: UUID,
    model_update: ModelUpdate,
    session: SessionDep,
) -> ModelResponse:
    """Update a model's description or tags."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    # Update fields
    update_data = model_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)

    model.updated_at = datetime.now(UTC)
    session.add(model)
    await session.commit()
    await session.refresh(model)

    # Count versions
    version_count_result = await session.execute(
        select(func.count()).select_from(ModelVersion).where(
            ModelVersion.model_id == model.id
        )
    )
    version_count = version_count_result.scalar() or 0

    return ModelResponse(
        **model.model_dump(),
        version_count=version_count,
    )


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: UUID,
    session: SessionDep,
) -> None:
    """Delete a model and all its versions."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    await session.delete(model)
    await session.commit()


@router.get("/{model_id}/versions", response_model=list[dict])
async def list_model_versions(
    model_id: UUID,
    session: SessionDep,
) -> list[dict]:
    """Get all versions of a model."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    result = await session.execute(
        select(ModelVersion)
        .where(ModelVersion.model_id == model_id)
        .order_by(ModelVersion.created_at.desc())
    )
    versions = result.scalars().all()

    return [v.model_dump() for v in versions]


@router.get("/{model_id}/history")
async def get_model_history(
    model_id: UUID,
    session: SessionDep,
) -> dict:
    """Get MLflow run history for a model."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    if not model.mlflow_experiment_id:
        return {"runs": [], "experiment_id": None}

    # MLflow integration will be added in Task 3.3
    return {
        "runs": [],
        "experiment_id": model.mlflow_experiment_id,
    }

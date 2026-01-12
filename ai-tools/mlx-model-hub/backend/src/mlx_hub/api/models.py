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
    existing = await session.execute(select(Model).where(Model.name == model_in.name))
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
    # Build base query conditions
    conditions = []
    if task_type:
        conditions.append(Model.task_type == task_type)

    # Get total count
    count_query = select(func.count()).select_from(Model)
    if conditions:
        count_query = count_query.where(*conditions)
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Subquery for version counts - avoids N+1 queries
    version_count_subquery = (
        select(ModelVersion.model_id, func.count(ModelVersion.id).label("version_count"))
        .group_by(ModelVersion.model_id)
        .subquery()
    )

    # Main query with LEFT JOIN to version counts
    query = select(
        Model, func.coalesce(version_count_subquery.c.version_count, 0).label("version_count")
    ).outerjoin(version_count_subquery, Model.id == version_count_subquery.c.model_id)

    if conditions:
        query = query.where(*conditions)

    query = query.order_by(Model.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    result = await session.execute(query)
    rows = result.all()

    # Build response items
    items = [
        ModelResponse(
            **model.model_dump(),
            version_count=version_count,
        )
        for model, version_count in rows
    ]

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
        select(func.count()).select_from(ModelVersion).where(ModelVersion.model_id == model.id)
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
        select(func.count()).select_from(ModelVersion).where(ModelVersion.model_id == model.id)
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


class ExportResponse(SQLModel):
    """Response schema for model export."""

    export_path: str
    inference_url: str
    model_name: str
    registered: bool
    message: str


@router.post("/{model_id}/export", response_model=ExportResponse)
async def export_model_to_inference(
    model_id: UUID,
    session: SessionDep,
) -> ExportResponse:
    """Export a trained model for use in unified-mlx-app.

    Creates a standardized export bundle and registers it with the
    inference server for immediate use.

    Args:
        model_id: UUID of the model to export.
        session: Database session.

    Returns:
        Export response with inference URL and registration status.

    Raises:
        HTTPException: If model not found or no trained version available.
    """
    from mlx_hub.config import get_settings
    from mlx_hub.db.enums import ModelVersionStatus
    from mlx_hub.services.export_service import (
        create_export_bundle,
        register_with_inference_server,
    )

    settings = get_settings()

    # Get model
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    # Get latest READY version with adapter
    result = await session.execute(
        select(ModelVersion)
        .where(
            ModelVersion.model_id == model_id,
            ModelVersion.status == ModelVersionStatus.READY,
            ModelVersion.artifact_path.isnot(None),
        )
        .order_by(ModelVersion.created_at.desc())
        .limit(1)
    )
    version = result.scalars().first()

    if not version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No trained version available for this model",
        )

    # Create export bundle
    try:
        export_path = await create_export_bundle(model, version)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create export bundle: {str(e)}",
        )

    # Register with inference server
    registered = False
    message = "Model exported successfully"

    if settings.inference_auto_register:
        try:
            await register_with_inference_server(export_path)
            registered = True
            message = "Model exported and registered with inference server"
        except ValueError as e:
            logger.warning(f"Failed to register with inference server: {e}")
            message = f"Model exported but registration failed: {str(e)}"

    inference_url = f"{settings.inference_server_url}/v1/chat/completions"

    return ExportResponse(
        export_path=str(export_path),
        inference_url=inference_url,
        model_name=model.name,
        registered=registered,
        message=message,
    )

"""Dataset registry API endpoints."""

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import SQLModel, select

from mlx_hub.config import Settings
from mlx_hub.db.models import Dataset
from mlx_hub.db.session import SessionDep, SettingsDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/datasets", tags=["datasets"])


# Request/Response schemas
class DatasetCreate(SQLModel):
    """Request schema for creating a dataset."""

    name: str
    path: str
    schema_info: dict = {}


class DatasetResponse(SQLModel):
    """Response schema for a dataset."""

    id: UUID
    name: str
    path: str
    checksum: str
    schema_info: dict
    created_at: datetime


class DatasetListResponse(SQLModel):
    """Response schema for dataset list."""

    items: list[DatasetResponse]
    total: int
    page: int
    page_size: int


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def validate_dataset_path(path: str, settings: Settings) -> Path:
    """Validate dataset path is within allowed directories.

    Prevents path traversal attacks by ensuring the resolved path
    is within the configured storage directory.

    Args:
        path: The path to validate.
        settings: Application settings with storage paths.

    Returns:
        Resolved absolute path if valid.

    Raises:
        HTTPException: If path is outside allowed directory or doesn't exist.
    """
    # Resolve to absolute path
    dataset_path = Path(path).resolve()
    allowed_base = settings.storage_datasets_path.resolve()

    # Check path is within allowed directory (prevent path traversal)
    try:
        dataset_path.relative_to(allowed_base)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset path must be within {allowed_base}",
        ) from None

    # Check file exists
    if not dataset_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset file not found: {path}",
        )

    # Check it's a file, not a directory
    if not dataset_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a file: {path}",
        )

    return dataset_path


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DatasetResponse)
async def create_dataset(
    dataset_in: DatasetCreate,
    session: SessionDep,
    settings: SettingsDep,
) -> DatasetResponse:
    """Register a new dataset.

    Validates the dataset file exists, calculates its checksum,
    and detects duplicates by both name and content.
    """
    # Validate path (security + existence check)
    file_path = validate_dataset_path(dataset_in.path, settings)

    # Check for duplicate name
    existing = await session.execute(
        select(Dataset).where(Dataset.name == dataset_in.name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset with name '{dataset_in.name}' already exists",
        )

    # Calculate checksum
    checksum = calculate_checksum(file_path)

    # Check for duplicate checksum (same file content, different name)
    existing_checksum = await session.execute(
        select(Dataset).where(Dataset.checksum == checksum)
    )
    duplicate = existing_checksum.scalars().first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset with same content already exists: '{duplicate.name}'",
        )

    # Create dataset
    dataset = Dataset(
        name=dataset_in.name,
        path=str(file_path),
        checksum=checksum,
        schema_info=dataset_in.schema_info,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)

    logger.info(f"Created dataset '{dataset.name}' with checksum {checksum[:16]}...")

    return DatasetResponse(**dataset.model_dump())


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DatasetListResponse:
    """List all registered datasets with pagination."""
    # Get total count
    count_result = await session.execute(
        select(func.count()).select_from(Dataset)
    )
    total = count_result.scalar() or 0

    # Get paginated results
    query = (
        select(Dataset)
        .order_by(Dataset.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(query)
    datasets = result.scalars().all()

    return DatasetListResponse(
        items=[DatasetResponse(**d.model_dump()) for d in datasets],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    session: SessionDep,
) -> DatasetResponse:
    """Get a specific dataset by ID."""
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    return DatasetResponse(**dataset.model_dump())


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(
    dataset_id: UUID,
    session: SessionDep,
) -> None:
    """Delete a dataset registration.

    Note: This only removes the database record, not the actual file.
    """
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )

    await session.delete(dataset)
    await session.commit()


@router.post("/{dataset_id}/verify", response_model=dict)
async def verify_dataset(
    dataset_id: UUID,
    session: SessionDep,
) -> dict:
    """Verify dataset integrity by recalculating checksum.

    Returns whether the current file matches the stored checksum.
    """
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )

    file_path = Path(dataset.path)
    if not file_path.exists():
        return {
            "valid": False,
            "error": "File not found",
            "stored_checksum": dataset.checksum,
            "current_checksum": None,
        }

    current_checksum = calculate_checksum(file_path)
    is_valid = current_checksum == dataset.checksum

    return {
        "valid": is_valid,
        "stored_checksum": dataset.checksum,
        "current_checksum": current_checksum,
    }

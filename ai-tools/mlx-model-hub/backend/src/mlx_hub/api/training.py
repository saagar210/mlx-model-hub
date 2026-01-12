"""Training job orchestration API endpoints."""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func
from sqlmodel import SQLModel, select

from mlx_hub.db.enums import JobStatus
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob
from mlx_hub.db.session import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["training"])


# Request/Response schemas
class TrainingJobCreate(SQLModel):
    """Request schema for creating a training job."""

    model_id: UUID
    dataset_id: UUID
    config: dict = {
        "lora_rank": 16,
        "lora_alpha": 32,
        "learning_rate": 5e-5,
        "epochs": 3,
        "batch_size": 4,
        "seed": 42,
    }


class TrainingJobResponse(SQLModel):
    """Response schema for a training job."""

    id: UUID
    model_id: UUID
    dataset_id: UUID
    model_version_id: UUID | None
    status: JobStatus
    config: dict
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    heartbeat_at: datetime | None


class TrainingJobListResponse(SQLModel):
    """Response schema for training job list."""

    items: list[TrainingJobResponse]
    total: int
    page: int
    page_size: int


class JobStatusUpdate(SQLModel):
    """Request schema for updating job status."""

    status: JobStatus


@router.post("/jobs", status_code=status.HTTP_201_CREATED, response_model=TrainingJobResponse)
async def create_training_job(
    job_in: TrainingJobCreate,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> TrainingJobResponse:
    """Submit a new training job.

    Creates a job in QUEUED status and triggers the background worker
    to process the job queue.
    """
    # Validate model exists
    model = await session.get(Model, job_in.model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {job_in.model_id} not found",
        )

    # Validate dataset exists
    dataset = await session.get(Dataset, job_in.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {job_in.dataset_id} not found",
        )

    # Create job
    job = TrainingJob(
        model_id=job_in.model_id,
        dataset_id=job_in.dataset_id,
        status=JobStatus.QUEUED,
        config=job_in.config,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    logger.info(f"Created training job {job.id} for model {model.name}")

    # Trigger worker to check queue
    background_tasks.add_task(trigger_worker_check)

    return TrainingJobResponse(**job.model_dump())


@router.get("/jobs", response_model=TrainingJobListResponse)
async def list_training_jobs(
    session: SessionDep,
    job_status: JobStatus | None = None,
    model_id: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TrainingJobListResponse:
    """List training jobs with optional filters."""
    # Build query
    query = select(TrainingJob)
    count_query = select(func.count()).select_from(TrainingJob)

    if job_status:
        query = query.where(TrainingJob.status == job_status)
        count_query = count_query.where(TrainingJob.status == job_status)

    if model_id:
        query = query.where(TrainingJob.model_id == model_id)
        count_query = count_query.where(TrainingJob.model_id == model_id)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    query = (
        query.order_by(TrainingJob.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await session.execute(query)
    jobs = result.scalars().all()

    return TrainingJobListResponse(
        items=[TrainingJobResponse(**j.model_dump()) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/jobs/{job_id}", response_model=TrainingJobResponse)
async def get_training_job(
    job_id: UUID,
    session: SessionDep,
) -> TrainingJobResponse:
    """Get a specific training job by ID."""
    job = await session.get(TrainingJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job {job_id} not found",
        )
    return TrainingJobResponse(**job.model_dump())


@router.post("/jobs/{job_id}/cancel", response_model=TrainingJobResponse)
async def cancel_training_job(
    job_id: UUID,
    session: SessionDep,
) -> TrainingJobResponse:
    """Cancel a queued training job.

    Only jobs in QUEUED status can be cancelled.
    Running jobs cannot be cancelled (would require process termination).
    """
    job = await session.get(TrainingJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job {job_id} not found",
        )

    if job.status != JobStatus.QUEUED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job in {job.status} status. Only QUEUED jobs can be cancelled.",
        )

    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(UTC)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    logger.info(f"Cancelled training job {job_id}")

    return TrainingJobResponse(**job.model_dump())


@router.get("/queue", response_model=list[TrainingJobResponse])
async def get_job_queue(
    session: SessionDep,
) -> list[TrainingJobResponse]:
    """Get all jobs in the queue (QUEUED status) in FIFO order."""
    result = await session.execute(
        select(TrainingJob)
        .where(TrainingJob.status == JobStatus.QUEUED)
        .order_by(TrainingJob.created_at)
    )
    jobs = result.scalars().all()
    return [TrainingJobResponse(**j.model_dump()) for j in jobs]


@router.get("/active", response_model=TrainingJobResponse | None)
async def get_active_job(
    session: SessionDep,
) -> TrainingJobResponse | None:
    """Get the currently running job, if any."""
    result = await session.execute(
        select(TrainingJob).where(TrainingJob.status == JobStatus.RUNNING)
    )
    job = result.scalars().first()
    if not job:
        return None
    return TrainingJobResponse(**job.model_dump())


@router.get("/jobs/{job_id}/version", response_model=dict)
async def get_job_version(
    job_id: UUID,
    session: SessionDep,
) -> dict:
    """Get the model version created by a completed job."""
    job = await session.get(TrainingJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job {job_id} not found",
        )

    if job.status != JobStatus.COMPLETED:
        return {"model_version_id": None, "status": job.status}

    if not job.model_version_id:
        return {"model_version_id": None, "status": job.status}

    version = await session.get(ModelVersion, job.model_version_id)
    if not version:
        return {"model_version_id": job.model_version_id, "version": None}

    return {
        "model_version_id": job.model_version_id,
        "version": version.model_dump(),
    }


async def trigger_worker_check() -> None:
    """Trigger the worker to check the job queue.

    This is called after creating a new job to wake up the worker.
    The actual worker implementation is in training/worker.py.
    """
    from mlx_hub.training.worker import trigger_worker

    await trigger_worker()

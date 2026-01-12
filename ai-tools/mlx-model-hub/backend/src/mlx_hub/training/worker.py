"""Background job worker for training orchestration."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import psutil
from sqlmodel import select

from mlx_hub.config import get_settings
from mlx_hub.db.enums import JobStatus, ModelVersionStatus
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob
from mlx_hub.db.session import get_session_factory

logger = logging.getLogger(__name__)

# Worker state
_worker_running = False
_worker_task: asyncio.Task | None = None
_worker_lock = asyncio.Lock()


async def trigger_worker() -> None:
    """Trigger the worker to check the queue.

    Safe to call multiple times - will only start one worker instance.
    """
    global _worker_running, _worker_task

    async with _worker_lock:
        if _worker_running:
            logger.debug("Worker already running, skipping trigger")
            return

        _worker_running = True
        _worker_task = asyncio.create_task(run_worker())
        logger.info("Worker triggered")


async def run_worker() -> None:
    """Main worker loop - processes jobs from queue in FIFO order.

    Runs until the queue is empty, then stops.
    Only one job runs at a time (single active job constraint).
    """
    global _worker_running
    settings = get_settings()
    session_factory = get_session_factory(settings)

    try:
        while True:
            async with session_factory() as session:
                # Check for already running job (single active job constraint)
                running_result = await session.execute(
                    select(TrainingJob).where(TrainingJob.status == JobStatus.RUNNING)
                )
                running_job = running_result.scalars().first()

                if running_job:
                    logger.debug(f"Job {running_job.id} still running, waiting...")
                    await asyncio.sleep(5)
                    continue

                # Get next queued job (FIFO order by created_at)
                result = await session.execute(
                    select(TrainingJob)
                    .where(TrainingJob.status == JobStatus.QUEUED)
                    .order_by(TrainingJob.created_at)
                    .limit(1)
                )
                job = result.scalars().first()

                if not job:
                    logger.info("No jobs in queue, worker stopping")
                    break

                # Check memory before starting
                if not check_memory_available():
                    logger.warning("Insufficient memory available, waiting...")
                    await asyncio.sleep(30)
                    continue

                # Process the job
                await process_job(session, job)

    except Exception as e:
        logger.error(f"Worker error: {e}")
    finally:
        _worker_running = False
        logger.info("Worker stopped")


async def process_job(session, job: TrainingJob) -> None:
    """Process a single training job.

    Updates job status, runs training, creates model version on success.
    """
    logger.info(f"Starting job {job.id}")

    # Update status to running
    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    job.heartbeat_at = datetime.now(UTC)
    session.add(job)
    await session.commit()

    try:
        # Load model and dataset info
        model = await session.get(Model, job.model_id)
        dataset = await session.get(Dataset, job.dataset_id)

        if not model or not dataset:
            raise ValueError("Model or dataset not found")

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(update_heartbeat(job.id))

        try:
            # Run training (placeholder - will be implemented in Phase 3)
            result = await run_training(model, dataset, job.config)
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

        # Create model version on success
        version = ModelVersion(
            model_id=model.id,
            version=generate_version_number(model.name),
            status=ModelVersionStatus.READY,
            metrics=result.get("metrics", {}),
            artifact_path=result.get("artifact_path"),
        )
        session.add(version)
        await session.commit()
        await session.refresh(version)

        # Auto-export to inference server
        try:
            from mlx_hub.services.export_service import (
                create_export_bundle,
                register_with_inference_server,
            )

            settings = get_settings()
            export_path = await create_export_bundle(model, version)

            if settings.inference_auto_register:
                await register_with_inference_server(export_path)
                logger.info(f"Model {model.name} exported and registered with inference server")
            else:
                logger.info(f"Model {model.name} exported to {export_path}")

        except Exception as e:
            # Non-fatal: training succeeded, but export failed
            logger.warning(f"Export to inference server failed (non-fatal): {e}")

        # Update job on success
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(UTC)
        job.model_version_id = version.id

        logger.info(f"Job {job.id} completed, created version {version.id}")

    except Exception as e:
        logger.error(f"Job {job.id} failed: {e}")
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.now(UTC)

    finally:
        session.add(job)
        await session.commit()


async def update_heartbeat(job_id: UUID) -> None:
    """Update job heartbeat periodically.

    Runs in background while job is processing.
    Allows detection of stale/crashed jobs.
    """
    settings = get_settings()
    session_factory = get_session_factory(settings)

    while True:
        try:
            await asyncio.sleep(30)

            async with session_factory() as session:
                job = await session.get(TrainingJob, job_id)
                if job and job.status == JobStatus.RUNNING:
                    job.heartbeat_at = datetime.now(UTC)
                    session.add(job)
                    await session.commit()
                    logger.debug(f"Updated heartbeat for job {job_id}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Heartbeat update failed: {e}")


def check_memory_available() -> bool:
    """Check if enough memory is available for training.

    Returns True if available memory exceeds the configured MLX limit.
    """
    settings = get_settings()
    available_gb = psutil.virtual_memory().available / (1024**3)
    required_gb = settings.mlx_memory_limit_gb

    is_available = available_gb >= required_gb
    if not is_available:
        logger.warning(
            f"Insufficient memory: {available_gb:.1f}GB available, {required_gb}GB required"
        )
    return is_available


async def run_training(model: Model, dataset: Dataset, config: dict) -> dict:
    """Run the actual training process using MLX TrainingRunner.

    Args:
        model: Model database record.
        dataset: Dataset database record.
        config: Training configuration dictionary.

    Returns:
        Dictionary with metrics and artifact_path.
    """
    from mlx_hub.training.runner import TrainingRunner

    logger.info(f"Training {model.name} with dataset {dataset.name}")
    logger.info(f"Config: {config}")

    runner = TrainingRunner(
        model=model,
        dataset=dataset,
        config=config,
    )

    result = await runner.run()

    return {
        "metrics": result.get("metrics", {}),
        "artifact_path": result.get("artifact_path"),
        "run_id": result.get("run_id"),
    }


def generate_version_number(model_name: str) -> str:
    """Generate a version number for a new model version.

    Uses timestamp-based versioning: v{YYYYMMDD}.{HHMMSS}
    """
    now = datetime.now(UTC)
    return f"v{now.strftime('%Y%m%d')}.{now.strftime('%H%M%S')}"


async def cleanup_stale_jobs() -> None:
    """Mark stale running jobs as failed.

    Jobs with no heartbeat update in 5+ minutes are considered stale.
    Should be called periodically (e.g., on app startup, via scheduler).
    """
    settings = get_settings()
    session_factory = get_session_factory(settings)

    async with session_factory() as session:
        stale_threshold = datetime.now(UTC) - timedelta(minutes=5)

        result = await session.execute(
            select(TrainingJob).where(
                TrainingJob.status == JobStatus.RUNNING,
                TrainingJob.heartbeat_at < stale_threshold,
            )
        )

        stale_jobs = result.scalars().all()
        for job in stale_jobs:
            logger.warning(f"Marking stale job {job.id} as failed (no heartbeat)")
            job.status = JobStatus.FAILED
            job.error_message = "Job timed out (no heartbeat for 5+ minutes)"
            job.completed_at = datetime.now(UTC)
            session.add(job)

        if stale_jobs:
            await session.commit()
            logger.info(f"Cleaned up {len(stale_jobs)} stale jobs")

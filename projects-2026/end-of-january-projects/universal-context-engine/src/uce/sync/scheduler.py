"""
Background sync scheduler using APScheduler.
"""

import asyncio
from datetime import datetime
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from ..core.config import settings
from ..core.logging import get_logger
from .engine import SyncEngine

logger = get_logger(__name__)


class SyncScheduler:
    """
    Schedules periodic sync jobs for each adapter.
    """

    def __init__(self, sync_engine: SyncEngine) -> None:
        """
        Initialize scheduler.

        Args:
            sync_engine: Sync engine to use for jobs
        """
        self.sync_engine = sync_engine
        self.scheduler = AsyncIOScheduler()
        self._job_ids: dict[str, str] = {}

    def start(self) -> None:
        """Start the scheduler."""
        if not settings.sync_enabled:
            logger.info("Sync disabled by configuration")
            return

        # Schedule each adapter based on its sync interval
        for source_type, adapter in self.sync_engine.adapters.items():
            interval = adapter.get_sync_interval()

            job = self.scheduler.add_job(
                self._sync_job,
                IntervalTrigger(seconds=int(interval.total_seconds())),
                args=[source_type],
                id=f"sync_{source_type}",
                name=f"Sync {source_type}",
                replace_existing=True,
            )
            self._job_ids[source_type] = job.id

            logger.info(
                f"Scheduled sync job",
                source=source_type,
                interval_seconds=int(interval.total_seconds()),
            )

        self.scheduler.start()
        logger.info("Sync scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Sync scheduler stopped")

    async def _sync_job(self, source_type: str) -> None:
        """Execute sync job for a source."""
        try:
            logger.debug(f"Starting scheduled sync", source=source_type)
            result = await self.sync_engine.sync_source(source_type)
            logger.debug(f"Completed scheduled sync", source=source_type, result=result)
        except Exception as e:
            logger.error(f"Scheduled sync failed", source=source_type, error=str(e))

    async def trigger_sync(self, source_type: str | None = None) -> dict:
        """
        Manually trigger a sync.

        Args:
            source_type: Optional specific source to sync

        Returns:
            Sync results
        """
        if source_type:
            return await self.sync_engine.sync_source(source_type)
        else:
            return await self.sync_engine.sync_all()

    def get_job_status(self) -> list[dict]:
        """Get status of all scheduled jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        return jobs


__all__ = ["SyncScheduler"]

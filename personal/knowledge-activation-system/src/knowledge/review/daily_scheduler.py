"""Daily review scheduler using asyncio.

Provides scheduling for daily review notifications/reminders at a configurable time.
Uses asyncio for lightweight scheduling without external dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from knowledge.config import get_settings
from knowledge.review.scheduler import get_review_stats

logger = logging.getLogger(__name__)


@dataclass
class ScheduleInfo:
    """Information about the daily review schedule."""

    enabled: bool
    scheduled_time: time
    timezone: str
    next_run: datetime | None
    last_run: datetime | None
    due_count: int
    status: str  # "running", "waiting", "disabled"


class DailyReviewScheduler:
    """
    Scheduler for daily review reminders.

    Uses asyncio sleep-based scheduling for simplicity and reliability.
    No external dependencies like APScheduler required.
    """

    def __init__(
        self,
        hour: int = 9,
        minute: int = 0,
        timezone: str = "America/Los_Angeles",
        on_due_reviews: Callable[..., Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        """
        Initialize the daily scheduler.

        Args:
            hour: Hour to run daily review (0-23)
            minute: Minute to run daily review (0-59)
            timezone: Timezone for scheduling (IANA timezone string)
            on_due_reviews: Async callback when reviews are due
        """
        self.hour = hour
        self.minute = minute
        self.timezone = timezone
        self._tz = ZoneInfo(timezone)
        self._on_due_reviews = on_due_reviews

        self._task: asyncio.Task | None = None
        self._running = False
        self._last_run: datetime | None = None
        self._next_run: datetime | None = None

    def _calculate_next_run(self) -> datetime:
        """Calculate the next scheduled run time."""
        now = datetime.now(self._tz)
        scheduled_today = now.replace(
            hour=self.hour,
            minute=self.minute,
            second=0,
            microsecond=0,
        )

        # If we've already passed today's time, schedule for tomorrow
        if now >= scheduled_today:
            scheduled_today += timedelta(days=1)

        return scheduled_today

    def _seconds_until_next_run(self) -> float:
        """Calculate seconds until next scheduled run."""
        if self._next_run is None:
            self._next_run = self._calculate_next_run()

        now = datetime.now(self._tz)
        delta = self._next_run - now
        return max(0, delta.total_seconds())

    async def _run_daily_check(self) -> None:
        """Run the daily review check."""
        try:
            stats = await get_review_stats()

            logger.info(
                f"Daily review check: {stats.due_now} items due, "
                f"{stats.total_active} active in queue"
            )

            if stats.due_now > 0:
                logger.info(f"Reviews due: {stats.due_now} items waiting for review")

                # Call the callback if provided
                if self._on_due_reviews is not None:
                    await self._on_due_reviews(stats)

            self._last_run = datetime.now(self._tz)

        except Exception as e:
            logger.error(f"Error in daily review check: {e}")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop."""
        logger.info(
            f"Daily review scheduler started - "
            f"scheduled for {self.hour:02d}:{self.minute:02d} {self.timezone}"
        )

        while self._running:
            try:
                # Calculate next run
                self._next_run = self._calculate_next_run()
                wait_seconds = self._seconds_until_next_run()

                logger.debug(
                    f"Next review check in {wait_seconds/3600:.1f} hours "
                    f"at {self._next_run}"
                )

                # Wait until scheduled time
                await asyncio.sleep(wait_seconds)

                # Run the daily check
                if self._running:  # Check again in case we were stopped
                    await self._run_daily_check()

            except asyncio.CancelledError:
                logger.info("Daily review scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(60)

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Daily review scheduler started")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Daily review scheduler stopped")

    async def trigger_now(self) -> None:
        """Manually trigger a review check immediately."""
        logger.info("Manual trigger: running daily review check")
        await self._run_daily_check()

    async def get_schedule_info(self) -> ScheduleInfo:
        """Get information about the current schedule."""
        try:
            stats = await get_review_stats()
            due_count = stats.due_now
        except Exception:
            due_count = 0

        if not self._running:
            status = "disabled"
            next_run = None
        else:
            status = "waiting"
            next_run = self._next_run or self._calculate_next_run()

        return ScheduleInfo(
            enabled=self._running,
            scheduled_time=time(hour=self.hour, minute=self.minute),
            timezone=self.timezone,
            next_run=next_run,
            last_run=self._last_run,
            due_count=due_count,
            status=status,
        )


# Global scheduler instance
_scheduler: DailyReviewScheduler | None = None


def get_daily_scheduler() -> DailyReviewScheduler:
    """Get or create the global daily scheduler instance."""
    global _scheduler
    if _scheduler is None:
        settings = get_settings()
        _scheduler = DailyReviewScheduler(
            hour=settings.review_time_hour,
            minute=settings.review_time_minute,
            timezone=settings.review_timezone,
        )
    return _scheduler


async def start_daily_scheduler() -> None:
    """Start the global daily scheduler if enabled."""
    settings = get_settings()
    if not settings.review_enabled:
        logger.info("Daily review scheduler disabled by configuration")
        return

    scheduler = get_daily_scheduler()
    await scheduler.start()


async def stop_daily_scheduler() -> None:
    """Stop the global daily scheduler."""
    global _scheduler
    if _scheduler is not None:
        await _scheduler.stop()
        _scheduler = None


async def get_schedule_status() -> ScheduleInfo:
    """Get the current schedule status."""
    scheduler = get_daily_scheduler()
    return await scheduler.get_schedule_info()

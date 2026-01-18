"""Review scheduling and queue management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from knowledge.db import get_db
from knowledge.review.fsrs_engine import (
    create_fsrs_card,
    get_review_engine,
    parse_fsrs_state_safe,
    validate_fsrs_state,
)
from knowledge.review.models import ReviewItem, ReviewRating, ReviewResult, ReviewStats

logger = logging.getLogger(__name__)


@dataclass
class ReviewSession:
    """Tracks an active review session."""

    session_id: str
    started_at: datetime
    items_total: int
    items_reviewed: int = 0
    ratings: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.ratings is None:
            self.ratings = {"again": 0, "hard": 0, "good": 0, "easy": 0}

    @property
    def items_remaining(self) -> int:
        """Items left to review."""
        return self.items_total - self.items_reviewed

    @property
    def completion_percentage(self) -> float:
        """Session completion as percentage."""
        if self.items_total == 0:
            return 100.0
        return (self.items_reviewed / self.items_total) * 100

    def record_rating(self, rating: ReviewRating) -> None:
        """Record a rating in the session stats."""
        if self.ratings is not None:
            self.ratings[rating.value] = self.ratings.get(rating.value, 0) + 1
        self.items_reviewed += 1


# =============================================================================
# Queue Operations
# =============================================================================


async def add_to_review_queue(content_id: UUID) -> bool:
    """
    Add content to the review queue.

    Args:
        content_id: ID of content to add

    Returns:
        True if added, False if already in queue
    """
    db = await get_db()

    async with db.acquire() as conn:
        # Check if already in queue
        existing = await conn.fetchval(
            "SELECT 1 FROM review_queue WHERE content_id = $1",
            content_id,
        )
        if existing:
            return False

        # Create new card state
        card_state = create_fsrs_card()

        # Validate state before storing
        is_valid, error = validate_fsrs_state(card_state)
        if not is_valid:
            logger.error(f"Failed to create valid FSRS card state: {error}")
            raise ValueError(f"Invalid FSRS card state: {error}")

        # Insert into queue
        await conn.execute(
            """
            INSERT INTO review_queue (content_id, fsrs_state, next_review, status)
            VALUES ($1, $2::jsonb, $3, 'active')
            """,
            content_id,
            json.dumps(card_state),
            datetime.now(UTC),
        )

    return True


async def get_due_items(
    limit: int = 20,
    include_new: bool = True,
    include_learning: bool = True,
    include_review: bool = True,
) -> list[ReviewItem]:
    """
    Get items due for review.

    Args:
        limit: Maximum number of items to return
        include_new: Include new items never reviewed
        include_learning: Include items in learning phase
        include_review: Include items in review phase

    Returns:
        List of ReviewItem objects sorted by due date (oldest first)
    """
    db = await get_db()

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                r.content_id,
                c.title,
                c.type as content_type,
                r.fsrs_state,
                r.next_review,
                r.last_reviewed,
                (
                    SELECT chunk_text
                    FROM chunks
                    WHERE content_id = r.content_id
                    ORDER BY chunk_index
                    LIMIT 1
                ) as preview_text
            FROM review_queue r
            JOIN content c ON c.id = r.content_id
            WHERE r.status = 'active'
              AND r.next_review <= NOW()
            ORDER BY r.next_review ASC
            LIMIT $1
            """,
            limit,
        )

    items = []
    for row in rows:
        # Use safe parsing with validation
        state, state_data = parse_fsrs_state_safe(row["fsrs_state"])

        item = ReviewItem(
            content_id=row["content_id"],
            title=row["title"],
            content_type=row["content_type"],
            preview_text=row["preview_text"] or "",
            state=state,
            due=row["next_review"],
            stability=state_data.get("stability", 0),
            difficulty=state_data.get("difficulty", 0),
            step=state_data.get("step"),
            last_review=row["last_reviewed"],
            reps=state_data.get("reps", 0),
            lapses=state_data.get("lapses", 0),
        )

        # Filter by state type if requested
        if item.is_new and not include_new:
            continue
        if item.is_learning and not item.is_new and not include_learning:
            continue
        if item.is_review and not include_review:
            continue

        items.append(item)

    return items


async def get_upcoming_items(
    days: int = 7,
    limit: int = 50,
) -> list[ReviewItem]:
    """
    Get items due within the next N days.

    Args:
        days: Number of days to look ahead
        limit: Maximum number of items to return

    Returns:
        List of ReviewItem objects sorted by due date
    """
    db = await get_db()
    future_date = datetime.now(UTC) + timedelta(days=days)

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                r.content_id,
                c.title,
                c.type as content_type,
                r.fsrs_state,
                r.next_review,
                r.last_reviewed,
                (
                    SELECT chunk_text
                    FROM chunks
                    WHERE content_id = r.content_id
                    ORDER BY chunk_index
                    LIMIT 1
                ) as preview_text
            FROM review_queue r
            JOIN content c ON c.id = r.content_id
            WHERE r.status = 'active'
              AND r.next_review <= $1
            ORDER BY r.next_review ASC
            LIMIT $2
            """,
            future_date,
            limit,
        )

    items = []
    for row in rows:
        state, state_data = parse_fsrs_state_safe(row["fsrs_state"])

        items.append(
            ReviewItem(
                content_id=row["content_id"],
                title=row["title"],
                content_type=row["content_type"],
                preview_text=row["preview_text"] or "",
                state=state,
                due=row["next_review"],
                stability=state_data.get("stability", 0),
                difficulty=state_data.get("difficulty", 0),
                step=state_data.get("step"),
                last_review=row["last_reviewed"],
                reps=state_data.get("reps", 0),
                lapses=state_data.get("lapses", 0),
            )
        )

    return items


async def get_review_stats() -> ReviewStats:
    """
    Get comprehensive review queue statistics.

    Returns:
        ReviewStats with detailed queue metrics
    """
    db = await get_db()

    async with db.acquire() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'active') as total_active,
                COUNT(*) FILTER (WHERE status = 'suspended') as suspended_count,
                COUNT(*) FILTER (WHERE status = 'active' AND next_review <= NOW()) as due_now,
                COUNT(*) FILTER (
                    WHERE status = 'active'
                    AND (fsrs_state->>'state')::int = 1
                    AND COALESCE((fsrs_state->>'step')::int, 0) = 0
                ) as new_count,
                COUNT(*) FILTER (
                    WHERE status = 'active'
                    AND (fsrs_state->>'state')::int IN (1, 3)
                ) as learning_count,
                COUNT(*) FILTER (
                    WHERE status = 'active'
                    AND (fsrs_state->>'state')::int = 2
                ) as review_count,
                AVG((fsrs_state->>'stability')::float) FILTER (
                    WHERE status = 'active' AND (fsrs_state->>'stability')::float > 0
                ) as avg_stability,
                AVG((fsrs_state->>'difficulty')::float) FILTER (
                    WHERE status = 'active'
                ) as avg_difficulty,
                COUNT(*) FILTER (
                    WHERE status = 'active'
                    AND last_reviewed >= CURRENT_DATE
                ) as reviews_today
            FROM review_queue
            """
        )

    return ReviewStats(
        total_active=stats["total_active"] or 0,
        due_now=stats["due_now"] or 0,
        new_count=stats["new_count"] or 0,
        learning_count=stats["learning_count"] or 0,
        review_count=stats["review_count"] or 0,
        suspended_count=stats["suspended_count"] or 0,
        average_stability=stats["avg_stability"],
        average_difficulty=stats["avg_difficulty"],
        reviews_today=stats["reviews_today"] or 0,
    )


async def get_review_stats_simple() -> dict[str, Any]:
    """
    Get simple review stats as dictionary (for backward compatibility).

    Returns:
        Dictionary with basic queue stats
    """
    stats = await get_review_stats()
    return {
        "total_active": stats.total_active,
        "due_now": stats.due_now,
        "new": stats.new_count,
        "learning": stats.learning_count,
        "review": stats.review_count,
    }


# =============================================================================
# Review Operations
# =============================================================================


async def submit_review(
    content_id: UUID,
    rating: ReviewRating,
) -> ReviewResult | None:
    """
    Submit a review for a content item.

    Args:
        content_id: ID of content being reviewed
        rating: User's rating

    Returns:
        ReviewResult or None if item not in queue
    """
    db = await get_db()
    engine = get_review_engine()

    async with db.acquire() as conn:
        # Get current state
        row = await conn.fetchrow(
            "SELECT fsrs_state, next_review FROM review_queue WHERE content_id = $1 AND status = 'active'",
            content_id,
        )

        if not row:
            return None

        # Parse current state safely
        _, current_state = parse_fsrs_state_safe(row["fsrs_state"])
        review_time = datetime.now(UTC)

        # Process review
        new_state, result = engine.process_review(current_state, rating, review_time)
        result.content_id = content_id

        # Validate new state before storing
        is_valid, error = validate_fsrs_state(new_state)
        if not is_valid:
            logger.error(f"Invalid FSRS state after review: {error}")
            raise ValueError(f"Review produced invalid state: {error}")

        # Update database
        await conn.execute(
            """
            UPDATE review_queue
            SET fsrs_state = $1::jsonb,
                next_review = $2,
                last_reviewed = $3,
                review_count = review_count + 1
            WHERE content_id = $4
            """,
            json.dumps(new_state),
            new_state["due"],
            review_time,
            content_id,
        )

    return result


async def get_item_state(content_id: UUID) -> dict[str, Any] | None:
    """
    Get the FSRS state for a specific item.

    Args:
        content_id: ID of content to get state for

    Returns:
        FSRS state dictionary or None if not found
    """
    db = await get_db()

    async with db.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT fsrs_state FROM review_queue WHERE content_id = $1",
            content_id,
        )

    if not row or not row["fsrs_state"]:
        return None

    return row["fsrs_state"]


# =============================================================================
# Queue Management
# =============================================================================


async def suspend_item(content_id: UUID) -> bool:
    """
    Suspend an item from review.

    Args:
        content_id: ID of content to suspend

    Returns:
        True if suspended, False if not found
    """
    db = await get_db()

    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE review_queue SET status = 'suspended' WHERE content_id = $1 AND status = 'active'",
            content_id,
        )

    return "UPDATE 1" in result


async def unsuspend_item(content_id: UUID) -> bool:
    """
    Unsuspend an item for review.

    Args:
        content_id: ID of content to unsuspend

    Returns:
        True if unsuspended, False if not found
    """
    db = await get_db()

    async with db.acquire() as conn:
        result = await conn.execute(
            "UPDATE review_queue SET status = 'active' WHERE content_id = $1 AND status = 'suspended'",
            content_id,
        )

    return "UPDATE 1" in result


async def remove_from_queue(content_id: UUID) -> bool:
    """
    Remove an item from the review queue entirely.

    Args:
        content_id: ID of content to remove

    Returns:
        True if removed, False if not found
    """
    db = await get_db()

    async with db.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM review_queue WHERE content_id = $1",
            content_id,
        )

    return "DELETE 1" in result


async def reset_item(content_id: UUID) -> bool:
    """
    Reset an item's FSRS state to new card.

    Args:
        content_id: ID of content to reset

    Returns:
        True if reset, False if not found
    """
    db = await get_db()
    card_state = create_fsrs_card()

    async with db.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE review_queue
            SET fsrs_state = $1::jsonb,
                next_review = NOW(),
                last_reviewed = NULL,
                review_count = 0
            WHERE content_id = $2
            """,
            json.dumps(card_state),
            content_id,
        )

    return "UPDATE 1" in result


# =============================================================================
# Daily Review Quota
# =============================================================================


class DailyQuotaManager:
    """Manages daily review quotas and session tracking."""

    def __init__(
        self,
        max_new_per_day: int = 20,
        max_reviews_per_day: int = 100,
    ):
        """
        Initialize quota manager.

        Args:
            max_new_per_day: Maximum new items to introduce per day
            max_reviews_per_day: Maximum total reviews per day
        """
        self.max_new_per_day = max_new_per_day
        self.max_reviews_per_day = max_reviews_per_day

    async def get_remaining_quota(self) -> dict[str, int]:
        """
        Get remaining review quota for today.

        Returns:
            Dictionary with remaining new and review quotas
        """
        stats = await get_review_stats()

        remaining_new = max(0, self.max_new_per_day - stats.new_count)
        remaining_total = max(0, self.max_reviews_per_day - stats.reviews_today)

        return {
            "remaining_new": remaining_new,
            "remaining_reviews": remaining_total,
            "reviews_today": stats.reviews_today,
        }

    async def get_session_items(
        self,
        max_items: int | None = None,
    ) -> list[ReviewItem]:
        """
        Get items for a review session respecting quotas.

        Args:
            max_items: Override max items for this session

        Returns:
            List of ReviewItem for the session
        """
        quota = await self.get_remaining_quota()
        limit = min(
            max_items or self.max_reviews_per_day,
            quota["remaining_reviews"],
        )

        if limit <= 0:
            return []

        return await get_due_items(limit=limit)


# Global quota manager
_quota_manager: DailyQuotaManager | None = None


def get_quota_manager() -> DailyQuotaManager:
    """Get or create the global quota manager."""
    global _quota_manager
    if _quota_manager is None:
        _quota_manager = DailyQuotaManager()
    return _quota_manager

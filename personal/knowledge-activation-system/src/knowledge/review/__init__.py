"""
FSRS-based spaced repetition review system.

This package provides a complete spaced repetition implementation using
the FSRS (Free Spaced Repetition Scheduler) algorithm for optimal knowledge retention.

Components:
- models: Pydantic models for review data (ReviewItem, ReviewResult, ReviewStats)
- fsrs_engine: Core FSRS integration (ReviewEngine, card state management)
- scheduler: Queue management and scheduling (get_due_items, submit_review)

Example usage:
    from knowledge.review import (
        get_due_items,
        submit_review,
        get_review_stats,
        ReviewRating,
    )

    # Get items due for review
    items = await get_due_items(limit=20)

    # Submit a review
    result = await submit_review(content_id, ReviewRating.GOOD)

    # Get statistics
    stats = await get_review_stats()
"""

from __future__ import annotations

# Models
from knowledge.review.models import (
    FSRSState,
    NextIntervals,
    ReviewItem,
    ReviewRating,
    ReviewResult,
    ReviewSession,
    ReviewStats,
)

# FSRS Engine
from knowledge.review.fsrs_engine import (
    RATING_MAP,
    ReviewEngine,
    card_to_dict,
    create_fsrs_card,
    dict_to_card,
    get_review_engine,
    parse_fsrs_state_safe,
    reset_review_engine,
    validate_fsrs_state,
)

# Scheduler
from knowledge.review.scheduler import (
    DailyQuotaManager,
    add_to_review_queue,
    get_due_items,
    get_item_state,
    get_quota_manager,
    get_review_stats,
    get_review_stats_simple,
    get_upcoming_items,
    remove_from_queue,
    reset_item,
    submit_review,
    suspend_item,
    unsuspend_item,
)

# Daily Scheduler
from knowledge.review.daily_scheduler import (
    DailyReviewScheduler,
    ScheduleInfo,
    get_daily_scheduler,
    get_schedule_status,
    start_daily_scheduler,
    stop_daily_scheduler,
)

__all__ = [
    # Models
    "FSRSState",
    "NextIntervals",
    "ReviewItem",
    "ReviewRating",
    "ReviewResult",
    "ReviewSession",
    "ReviewStats",
    # FSRS Engine
    "RATING_MAP",
    "ReviewEngine",
    "card_to_dict",
    "create_fsrs_card",
    "dict_to_card",
    "get_review_engine",
    "parse_fsrs_state_safe",
    "reset_review_engine",
    "validate_fsrs_state",
    # Scheduler
    "DailyQuotaManager",
    "add_to_review_queue",
    "get_due_items",
    "get_item_state",
    "get_quota_manager",
    "get_review_stats",
    "get_review_stats_simple",
    "get_upcoming_items",
    "remove_from_queue",
    "reset_item",
    "submit_review",
    "suspend_item",
    "unsuspend_item",
    # Daily Scheduler
    "DailyReviewScheduler",
    "ScheduleInfo",
    "get_daily_scheduler",
    "get_schedule_status",
    "start_daily_scheduler",
    "stop_daily_scheduler",
]

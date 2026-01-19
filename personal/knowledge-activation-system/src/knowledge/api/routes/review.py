"""Review routes for spaced repetition."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from knowledge.api.auth import require_scope
from knowledge.api.schemas import (
    ReviewDueResponse,
    ReviewIntervalsResponse,
    ReviewQueueItem,
    ReviewStatsResponse,
    ScheduleStatusResponse,
    SubmitReviewRequest,
    SubmitReviewResponse,
)
from knowledge.api.utils import handle_exceptions
from knowledge.review import (
    ReviewRating,
    add_to_review_queue,
    get_due_items,
    get_item_state,
    get_review_engine,
    get_review_stats_simple,
    get_schedule_status,
    remove_from_queue,
    submit_review,
    suspend_item,
    unsuspend_item,
)

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/due", response_model=ReviewDueResponse, dependencies=[Depends(require_scope("review"))])
@handle_exceptions("get_due_reviews")
async def get_due_reviews(limit: int = 20) -> ReviewDueResponse:
    """
    Get items due for review.

    Returns a list of content items that are due for review,
    sorted by due date (oldest first).
    """
    items = await get_due_items(limit=limit)

    return ReviewDueResponse(
        items=[
            ReviewQueueItem(
                content_id=item.content_id,
                title=item.title,
                content_type=item.content_type,
                preview_text=item.preview_text,
                state=item.state.name,
                due=item.due,
                stability=item.stability,
                difficulty=item.difficulty,
                is_new=item.is_new,
                is_learning=item.is_learning,
                is_review=item.is_review,
                last_review=item.last_review,
            )
            for item in items
        ],
        total=len(items),
    )


@router.get("/stats", response_model=ReviewStatsResponse, dependencies=[Depends(require_scope("review"))])
@handle_exceptions("get_review_stats")
async def get_stats() -> ReviewStatsResponse:
    """
    Get review queue statistics.

    Returns counts of active items, due items, and items by state.
    """
    stats = await get_review_stats_simple()

    return ReviewStatsResponse(
        total_active=stats["total_active"],
        due_now=stats["due_now"],
        new=stats["new"],
        learning=stats["learning"],
        review=stats["review"],
    )


@router.post("/{content_id}", response_model=SubmitReviewResponse, dependencies=[Depends(require_scope("review"))])
@handle_exceptions("submit_review")
async def submit_content_review(
    content_id: UUID,
    request: SubmitReviewRequest,
) -> SubmitReviewResponse:
    """
    Submit a review for a content item.

    The rating should be one of: again, hard, good, easy.
    Returns the updated FSRS state and next due date.
    """
    # Convert API rating to internal rating
    rating_map = {
        "again": ReviewRating.AGAIN,
        "hard": ReviewRating.HARD,
        "good": ReviewRating.GOOD,
        "easy": ReviewRating.EASY,
    }
    rating = rating_map.get(request.rating.value)

    if rating is None:
        raise HTTPException(status_code=400, detail=f"Invalid rating: {request.rating}")

    result = await submit_review(content_id, rating)

    if result is None:
        raise HTTPException(status_code=404, detail="Item not in review queue")

    return SubmitReviewResponse(
        content_id=result.content_id,
        rating=result.rating.value,
        old_state=result.old_state.name,
        new_state=result.new_state.name,
        old_due=result.old_due,
        new_due=result.new_due,
        review_time=result.review_time,
    )


@router.get("/{content_id}/intervals", response_model=ReviewIntervalsResponse, dependencies=[Depends(require_scope("review"))])
@handle_exceptions("get_review_intervals")
async def get_next_intervals(content_id: UUID) -> ReviewIntervalsResponse:
    """
    Preview the next due dates for each possible rating.

    Useful for showing the user what interval they'll get
    for each rating option.
    """
    card_state = await get_item_state(content_id)

    if card_state is None:
        raise HTTPException(status_code=404, detail="Item not in review queue")

    engine = get_review_engine()
    intervals = engine.get_next_intervals(card_state)

    return ReviewIntervalsResponse(
        again=intervals[ReviewRating.AGAIN],
        hard=intervals[ReviewRating.HARD],
        good=intervals[ReviewRating.GOOD],
        easy=intervals[ReviewRating.EASY],
    )


@router.post("/{content_id}/add", dependencies=[Depends(require_scope("review"))])
@handle_exceptions("add_to_review_queue")
async def add_to_queue(content_id: UUID) -> dict[str, str]:
    """
    Add a content item to the review queue.

    Returns success status.
    """
    success = await add_to_review_queue(content_id)

    if not success:
        raise HTTPException(status_code=409, detail="Item already in queue")

    return {"status": "added", "content_id": str(content_id)}


@router.post("/{content_id}/suspend", dependencies=[Depends(require_scope("review"))])
@handle_exceptions("suspend_review")
async def suspend_review(content_id: UUID) -> dict[str, str]:
    """
    Suspend an item from the review queue.

    The item won't appear in due reviews until unsuspended.
    """
    success = await suspend_item(content_id)

    if not success:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"status": "suspended", "content_id": str(content_id)}


@router.post("/{content_id}/unsuspend", dependencies=[Depends(require_scope("review"))])
@handle_exceptions("unsuspend_review")
async def unsuspend_review(content_id: UUID) -> dict[str, str]:
    """
    Unsuspend an item in the review queue.

    The item will resume appearing in due reviews.
    """
    success = await unsuspend_item(content_id)

    if not success:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"status": "unsuspended", "content_id": str(content_id)}


@router.delete("/{content_id}", dependencies=[Depends(require_scope("review"))])
@handle_exceptions("remove_from_review")
async def remove_from_review(content_id: UUID) -> dict[str, str]:
    """
    Remove an item from the review queue entirely.

    This is permanent - the item's FSRS state will be lost.
    """
    success = await remove_from_queue(content_id)

    if not success:
        raise HTTPException(status_code=404, detail="Item not found")

    return {"status": "removed", "content_id": str(content_id)}


@router.get("/schedule/status", response_model=ScheduleStatusResponse, dependencies=[Depends(require_scope("review"))])
@handle_exceptions("get_review_schedule")
async def get_schedule() -> ScheduleStatusResponse:
    """
    Get the daily review schedule status.

    Returns the configured schedule time, next run time,
    and current queue statistics.
    """
    info = await get_schedule_status()

    return ScheduleStatusResponse(
        enabled=info.enabled,
        scheduled_time=info.scheduled_time.strftime("%H:%M"),
        timezone=info.timezone,
        next_run=info.next_run,
        last_run=info.last_run,
        due_count=info.due_count,
        status=info.status,
    )

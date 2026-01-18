"""Webhook Support API (P22: Event Notifications).

Provides endpoints for:
- Registering webhook endpoints
- Managing webhook subscriptions
- Webhook delivery with retry logic
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from knowledge.api.auth import require_scope
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# =============================================================================
# Types and Schemas
# =============================================================================


class WebhookEvent(str, Enum):
    """Supported webhook event types."""

    CONTENT_CREATED = "content.created"
    CONTENT_UPDATED = "content.updated"
    CONTENT_DELETED = "content.deleted"
    SEARCH_PERFORMED = "search.performed"
    REVIEW_COMPLETED = "review.completed"
    INGEST_COMPLETED = "ingest.completed"


class WebhookStatus(str, Enum):
    """Webhook subscription status."""

    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"  # Too many failures


class WebhookCreate(BaseModel):
    """Create webhook subscription request."""

    url: HttpUrl = Field(..., description="Endpoint URL to receive events")
    events: list[WebhookEvent] = Field(..., min_length=1, description="Events to subscribe to")
    secret: str | None = Field(default=None, min_length=16, max_length=256, description="Shared secret for HMAC signing")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Custom metadata")


class WebhookUpdate(BaseModel):
    """Update webhook subscription request."""

    url: HttpUrl | None = None
    events: list[WebhookEvent] | None = None
    status: WebhookStatus | None = None
    metadata: dict[str, Any] | None = None


class WebhookResponse(BaseModel):
    """Webhook subscription response."""

    id: str
    url: str
    events: list[str]
    status: str
    created_at: str
    last_triggered: str | None = None
    failure_count: int = 0
    metadata: dict[str, Any] = {}


class WebhookDelivery(BaseModel):
    """Webhook delivery record."""

    id: str
    webhook_id: str
    event: str
    status_code: int | None = None
    success: bool
    error: str | None = None
    delivered_at: str


class WebhookTestResult(BaseModel):
    """Webhook test result."""

    success: bool
    status_code: int | None = None
    response_time_ms: float | None = None
    error: str | None = None


# =============================================================================
# In-Memory Storage (for MVP - replace with DB in production)
# =============================================================================


_webhooks: dict[str, dict] = {}
_deliveries: list[dict] = []
_delivery_lock = asyncio.Lock()


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=WebhookResponse)
async def create_webhook(
    request: WebhookCreate,
    _: bool = Depends(require_scope("admin")),
) -> WebhookResponse:
    """
    Create a new webhook subscription.

    Requires admin scope. The webhook will receive POST requests
    for subscribed events with HMAC-SHA256 signature if secret provided.
    """
    webhook_id = str(uuid4())
    now = datetime.now(UTC)

    webhook = {
        "id": webhook_id,
        "url": str(request.url),
        "events": [e.value for e in request.events],
        "secret": request.secret,
        "status": WebhookStatus.ACTIVE.value,
        "created_at": now.isoformat(),
        "last_triggered": None,
        "failure_count": 0,
        "metadata": request.metadata,
    }

    _webhooks[webhook_id] = webhook

    logger.info(
        "webhook_created",
        webhook_id=webhook_id,
        url=str(request.url),
        events=webhook["events"],
    )

    return WebhookResponse(
        id=webhook_id,
        url=webhook["url"],
        events=webhook["events"],
        status=webhook["status"],
        created_at=webhook["created_at"],
        metadata=webhook["metadata"],
    )


@router.get("", response_model=list[WebhookResponse])
async def list_webhooks(
    _: bool = Depends(require_scope("admin")),
) -> list[WebhookResponse]:
    """List all webhook subscriptions."""
    return [
        WebhookResponse(
            id=w["id"],
            url=w["url"],
            events=w["events"],
            status=w["status"],
            created_at=w["created_at"],
            last_triggered=w["last_triggered"],
            failure_count=w["failure_count"],
            metadata=w["metadata"],
        )
        for w in _webhooks.values()
    ]


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    _: bool = Depends(require_scope("admin")),
) -> WebhookResponse:
    """Get webhook subscription details."""
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    return WebhookResponse(
        id=webhook["id"],
        url=webhook["url"],
        events=webhook["events"],
        status=webhook["status"],
        created_at=webhook["created_at"],
        last_triggered=webhook["last_triggered"],
        failure_count=webhook["failure_count"],
        metadata=webhook["metadata"],
    )


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    request: WebhookUpdate,
    _: bool = Depends(require_scope("admin")),
) -> WebhookResponse:
    """Update webhook subscription."""
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if request.url is not None:
        webhook["url"] = str(request.url)
    if request.events is not None:
        webhook["events"] = [e.value for e in request.events]
    if request.status is not None:
        webhook["status"] = request.status.value
        if request.status == WebhookStatus.ACTIVE:
            webhook["failure_count"] = 0  # Reset on reactivation
    if request.metadata is not None:
        webhook["metadata"] = request.metadata

    logger.info("webhook_updated", webhook_id=webhook_id)

    return WebhookResponse(
        id=webhook["id"],
        url=webhook["url"],
        events=webhook["events"],
        status=webhook["status"],
        created_at=webhook["created_at"],
        last_triggered=webhook["last_triggered"],
        failure_count=webhook["failure_count"],
        metadata=webhook["metadata"],
    )


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    _: bool = Depends(require_scope("admin")),
) -> dict:
    """Delete webhook subscription."""
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    del _webhooks[webhook_id]
    logger.info("webhook_deleted", webhook_id=webhook_id)

    return {"deleted": True, "id": webhook_id}


@router.post("/{webhook_id}/test", response_model=WebhookTestResult)
async def test_webhook(
    webhook_id: str,
    _: bool = Depends(require_scope("admin")),
) -> WebhookTestResult:
    """
    Send a test event to the webhook endpoint.

    Sends a test ping event to verify the webhook is reachable.
    """
    webhook = _webhooks.get(webhook_id)
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "event": "webhook.test",
        "timestamp": datetime.now(UTC).isoformat(),
        "webhook_id": webhook_id,
        "test": True,
    }

    result = await _deliver_webhook(webhook, test_payload)

    return WebhookTestResult(
        success=result["success"],
        status_code=result.get("status_code"),
        response_time_ms=result.get("response_time_ms"),
        error=result.get("error"),
    )


@router.get("/{webhook_id}/deliveries", response_model=list[WebhookDelivery])
async def get_webhook_deliveries(
    webhook_id: str,
    limit: int = 50,
    _: bool = Depends(require_scope("admin")),
) -> list[WebhookDelivery]:
    """Get recent delivery attempts for a webhook."""
    if webhook_id not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    webhook_deliveries = [
        d for d in _deliveries
        if d["webhook_id"] == webhook_id
    ][-limit:]

    return [
        WebhookDelivery(
            id=d["id"],
            webhook_id=d["webhook_id"],
            event=d["event"],
            status_code=d.get("status_code"),
            success=d["success"],
            error=d.get("error"),
            delivered_at=d["delivered_at"],
        )
        for d in reversed(webhook_deliveries)
    ]


# =============================================================================
# Webhook Delivery Functions
# =============================================================================


async def trigger_webhook_event(
    event: WebhookEvent,
    payload: dict[str, Any],
) -> None:
    """
    Trigger webhooks for an event.

    Called internally when events occur. Delivers to all
    active webhooks subscribed to the event.
    """
    event_value = event.value

    for webhook in _webhooks.values():
        if webhook["status"] != WebhookStatus.ACTIVE.value:
            continue
        if event_value not in webhook["events"]:
            continue

        # Deliver asynchronously (fire and forget with retry)
        asyncio.create_task(_deliver_with_retry(webhook, event_value, payload))


async def _deliver_with_retry(
    webhook: dict,
    event: str,
    payload: dict[str, Any],
    max_retries: int = 3,
) -> None:
    """Deliver webhook with exponential backoff retry."""
    full_payload = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": payload,
    }

    for attempt in range(max_retries):
        result = await _deliver_webhook(webhook, full_payload)

        # Record delivery attempt
        async with _delivery_lock:
            _deliveries.append({
                "id": str(uuid4()),
                "webhook_id": webhook["id"],
                "event": event,
                "status_code": result.get("status_code"),
                "success": result["success"],
                "error": result.get("error"),
                "delivered_at": datetime.now(UTC).isoformat(),
            })

            # Trim old deliveries (keep last 1000 per webhook)
            if len(_deliveries) > 10000:
                _deliveries[:] = _deliveries[-5000:]

        if result["success"]:
            webhook["last_triggered"] = datetime.now(UTC).isoformat()
            webhook["failure_count"] = 0
            return

        # Exponential backoff: 1s, 2s, 4s
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

    # All retries failed
    webhook["failure_count"] = webhook.get("failure_count", 0) + 1

    # Auto-pause after 10 consecutive failures
    if webhook["failure_count"] >= 10:
        webhook["status"] = WebhookStatus.FAILED.value
        logger.warning(
            "webhook_auto_paused",
            webhook_id=webhook["id"],
            failure_count=webhook["failure_count"],
        )


async def _deliver_webhook(
    webhook: dict,
    payload: dict[str, Any],
) -> dict:
    """Deliver a single webhook request."""
    import time

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "KAS-Webhook/1.0",
        "X-Webhook-ID": webhook["id"],
    }

    # Add HMAC signature if secret configured
    if webhook.get("secret"):
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(
            webhook["secret"].encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Webhook-Signature"] = f"sha256={signature}"

    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook["url"],
                json=payload,
                headers=headers,
            )

        response_time = (time.time() - start_time) * 1000

        success = 200 <= response.status_code < 300

        if not success:
            logger.warning(
                "webhook_delivery_failed",
                webhook_id=webhook["id"],
                status_code=response.status_code,
            )

        return {
            "success": success,
            "status_code": response.status_code,
            "response_time_ms": response_time,
        }

    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timeout",
            "response_time_ms": (time.time() - start_time) * 1000,
        }
    except httpx.RequestError as e:
        return {
            "success": False,
            "error": f"Request error: {str(e)[:100]}",
        }
    except Exception as e:
        logger.error("webhook_delivery_error", error=str(e))
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)[:100]}",
        }

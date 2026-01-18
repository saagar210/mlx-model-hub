"""Webhook system for external integrations.

Provides:
- Webhook registration and management
- Async delivery with retries
- HMAC signature generation and verification (timing-attack safe)
- Delivery history and metrics
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DeliveryStatus(str, Enum):
    """Webhook delivery status."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookEvent:
    """An event to be sent via webhook."""

    type: str
    data: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str = ""
    event_id: str = ""
    url: str = ""
    status: DeliveryStatus = DeliveryStatus.PENDING
    status_code: int | None = None
    response_body: str | None = None
    error: str | None = None
    attempts: int = 0
    created_at: float = field(default_factory=time.time)
    delivered_at: float | None = None
    next_retry_at: float | None = None


@dataclass
class Webhook:
    """Webhook configuration."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    events: list[str] = field(default_factory=list)  # Event types to receive
    secret: str = ""  # For signing payloads
    enabled: bool = True
    description: str = ""
    headers: dict[str, str] = field(default_factory=dict)  # Custom headers
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Retry configuration
    max_retries: int = 3
    retry_delay: float = 60.0  # seconds

    def matches_event(self, event_type: str) -> bool:
        """Check if this webhook should receive an event type."""
        if not self.events:
            return True  # Wildcard: receives all events

        for pattern in self.events:
            if pattern == event_type:
                return True
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                if event_type.startswith(prefix):
                    return True

        return False

    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for payload."""
        if not self.secret:
            return ""
        return hmac.new(
            self.secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

    def verify_signature(self, payload: str, signature: str) -> bool:
        """
        Verify an HMAC signature using constant-time comparison.

        This prevents timing attacks that could leak information
        about the secret.

        Args:
            payload: The payload that was signed
            signature: The signature to verify (hex string, with or without 'sha256=' prefix)

        Returns:
            True if signature is valid
        """
        if not self.secret:
            return False

        # Strip common prefix if present
        if signature.startswith("sha256="):
            signature = signature[7:]

        expected = self.generate_signature(payload)

        # Use constant-time comparison
        return secrets.compare_digest(signature, expected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "events": self.events,
            "enabled": self.enabled,
            "description": self.description,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class WebhookManager:
    """
    Manages webhook registration and delivery.

    Features:
    - Webhook registration and management
    - Event-to-webhook matching
    - Async delivery with retries
    - Payload signing
    - Delivery history
    """

    def __init__(
        self,
        max_deliveries_history: int = 1000,
        default_timeout: float = 30.0,
    ):
        """
        Initialize webhook manager.

        Args:
            max_deliveries_history: Maximum deliveries to keep in history
            default_timeout: Default request timeout in seconds
        """
        self.max_deliveries_history = max_deliveries_history
        self.default_timeout = default_timeout

        self._webhooks: dict[str, Webhook] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._pending_retries: asyncio.Queue[WebhookDelivery] = asyncio.Queue()
        self._retry_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._running = False

        # Metrics
        self._delivered_count = 0
        self._failed_count = 0

    async def start(self) -> None:
        """Start the webhook manager."""
        if self._running:
            return

        self._running = True
        self._retry_task = asyncio.create_task(self._retry_loop())
        logger.info("Webhook manager started")

    async def stop(self) -> None:
        """Stop the webhook manager."""
        self._running = False

        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

        logger.info("Webhook manager stopped")

    def register(self, webhook: Webhook) -> str:
        """Register a new webhook."""
        self._webhooks[webhook.id] = webhook
        logger.info(f"Registered webhook: {webhook.id} -> {webhook.url}")
        return webhook.id

    def unregister(self, webhook_id: str) -> bool:
        """Unregister a webhook."""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            logger.info(f"Unregistered webhook: {webhook_id}")
            return True
        return False

    def get_webhook(self, webhook_id: str) -> Webhook | None:
        """Get a webhook by ID."""
        return self._webhooks.get(webhook_id)

    def list_webhooks(self) -> list[Webhook]:
        """List all webhooks."""
        return list(self._webhooks.values())

    async def dispatch(self, event: WebhookEvent) -> list[str]:
        """
        Dispatch an event to all matching webhooks.

        Args:
            event: Event to dispatch

        Returns:
            List of delivery IDs
        """
        delivery_ids = []

        for webhook in self._webhooks.values():
            if not webhook.enabled:
                continue

            if not webhook.matches_event(event.type):
                continue

            delivery = WebhookDelivery(
                webhook_id=webhook.id,
                event_id=event.id,
                url=webhook.url,
            )

            # Deliver asynchronously
            asyncio.create_task(self._deliver(webhook, event, delivery))
            delivery_ids.append(delivery.id)

        return delivery_ids

    async def _deliver(
        self,
        webhook: Webhook,
        event: WebhookEvent,
        delivery: WebhookDelivery,
    ) -> None:
        """Attempt to deliver an event to a webhook."""
        delivery.attempts += 1

        # Prepare payload
        payload = json.dumps(event.to_dict(), default=str)

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "KnowledgeEngine-Webhook/1.0",
            "X-Webhook-Event": event.type,
            "X-Webhook-Delivery": delivery.id,
            **webhook.headers,
        }

        # Add signature if secret is set
        if webhook.secret:
            signature = webhook.generate_signature(payload)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook.url,
                    content=payload,
                    headers=headers,
                    timeout=self.default_timeout,
                )

                delivery.status_code = response.status_code
                delivery.response_body = response.text[:1000]  # Truncate

                if response.is_success:
                    delivery.status = DeliveryStatus.DELIVERED
                    delivery.delivered_at = time.time()
                    self._delivered_count += 1
                    logger.debug(
                        f"Webhook delivered: {delivery.id} -> {webhook.url}"
                    )
                else:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )

        except Exception as e:
            delivery.error = str(e)
            logger.warning(f"Webhook delivery failed: {delivery.id} - {e}")

            # Schedule retry if under limit
            if delivery.attempts < webhook.max_retries:
                delivery.status = DeliveryStatus.RETRYING
                delay = webhook.retry_delay * (2 ** (delivery.attempts - 1))
                delivery.next_retry_at = time.time() + delay
                await self._pending_retries.put(delivery)
            else:
                delivery.status = DeliveryStatus.FAILED
                self._failed_count += 1

        # Store delivery record
        async with self._lock:
            self._deliveries.append(delivery)
            if len(self._deliveries) > self.max_deliveries_history:
                self._deliveries.pop(0)

    async def _retry_loop(self) -> None:
        """Background loop for retrying failed deliveries."""
        while self._running:
            try:
                # Wait for pending retry
                delivery = await asyncio.wait_for(
                    self._pending_retries.get(),
                    timeout=10.0,
                )

                # Wait until retry time
                if delivery.next_retry_at:
                    wait_time = delivery.next_retry_at - time.time()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)

                # Get webhook
                webhook = self._webhooks.get(delivery.webhook_id)
                if not webhook or not webhook.enabled:
                    delivery.status = DeliveryStatus.FAILED
                    continue

                # Reconstruct event (simplified)
                event = WebhookEvent(
                    id=delivery.event_id,
                    type="retry",  # Would need to store original event
                    data={},
                )

                # Retry delivery
                await self._deliver(webhook, event, delivery)

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Retry loop error: {e}")

    def get_deliveries(
        self,
        webhook_id: str | None = None,
        status: DeliveryStatus | None = None,
        limit: int = 100,
    ) -> list[WebhookDelivery]:
        """Get delivery history."""
        deliveries = self._deliveries

        if webhook_id:
            deliveries = [d for d in deliveries if d.webhook_id == webhook_id]

        if status:
            deliveries = [d for d in deliveries if d.status == status]

        return list(reversed(deliveries[-limit:]))

    def get_stats(self) -> dict[str, Any]:
        """Get webhook statistics."""
        status_counts = dict.fromkeys(DeliveryStatus, 0)
        for delivery in self._deliveries:
            status_counts[delivery.status] += 1

        return {
            "webhooks": len(self._webhooks),
            "enabled_webhooks": sum(1 for w in self._webhooks.values() if w.enabled),
            "total_delivered": self._delivered_count,
            "total_failed": self._failed_count,
            "pending_retries": self._pending_retries.qsize(),
            "delivery_counts": {s.value: c for s, c in status_counts.items()},
        }

    async def test_webhook(self, webhook_id: str) -> WebhookDelivery:
        """Send a test event to a webhook."""
        webhook = self._webhooks.get(webhook_id)
        if not webhook:
            raise ValueError(f"Webhook not found: {webhook_id}")

        event = WebhookEvent(
            type="webhook.test",
            data={
                "message": "This is a test event",
                "webhook_id": webhook_id,
            },
        )

        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_id=event.id,
            url=webhook.url,
        )

        await self._deliver(webhook, event, delivery)
        return delivery

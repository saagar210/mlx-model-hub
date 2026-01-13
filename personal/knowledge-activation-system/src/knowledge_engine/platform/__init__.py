"""Application platform for extensibility and plugin architecture."""

from knowledge_engine.platform.plugin import (
    Plugin,
    PluginManager,
    PluginConfig,
    PluginState,
    hook,
)
from knowledge_engine.platform.events import (
    EventBus,
    Event,
    EventHandler,
    subscribe,
)
from knowledge_engine.platform.webhooks import (
    WebhookManager,
    Webhook,
    WebhookEvent,
    WebhookDelivery,
)

__all__ = [
    "Plugin",
    "PluginManager",
    "PluginConfig",
    "PluginState",
    "hook",
    "EventBus",
    "Event",
    "EventHandler",
    "subscribe",
    "WebhookManager",
    "Webhook",
    "WebhookEvent",
    "WebhookDelivery",
]

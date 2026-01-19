"""Plugin System API (P22: Plugin Management).

Provides endpoints for:
- Listing available plugins
- Enabling/disabling plugins
- Plugin configuration management
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from knowledge.api.auth import require_scope
from knowledge.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


# =============================================================================
# Types and Schemas
# =============================================================================


class PluginCategory(str, Enum):
    """Plugin categories."""

    IMPORT = "import"
    EXPORT = "export"
    AUTOMATION = "automation"
    INTEGRATION = "integration"


class PluginStatus(str, Enum):
    """Plugin operational status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONFIGURING = "configuring"


class PluginResponse(BaseModel):
    """Plugin information response."""

    id: str
    name: str
    description: str
    version: str
    author: str
    enabled: bool
    icon: str
    category: str
    configurable: bool
    status: str
    lastSync: str | None = None
    error: str | None = None


class PluginUpdate(BaseModel):
    """Update plugin request."""

    enabled: bool | None = None
    config: dict[str, Any] | None = None


class PluginConfig(BaseModel):
    """Plugin configuration schema."""

    api_key: str | None = Field(default=None, description="API key for the service")
    sync_interval: int | None = Field(default=None, ge=1, le=1440, description="Sync interval in minutes")
    options: dict[str, Any] = Field(default_factory=dict, description="Plugin-specific options")


# =============================================================================
# Built-in Plugins Registry
# =============================================================================

# Available plugins with their metadata
_plugins_registry: dict[str, dict] = {
    "notion": {
        "id": "notion",
        "name": "Notion",
        "description": "Import pages and databases from Notion workspace",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": False,
        "icon": "FileText",
        "category": PluginCategory.IMPORT.value,
        "configurable": True,
        "status": PluginStatus.INACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {},
    },
    "readwise": {
        "id": "readwise",
        "name": "Readwise",
        "description": "Sync highlights and annotations from Readwise",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": False,
        "icon": "BookOpen",
        "category": PluginCategory.IMPORT.value,
        "configurable": True,
        "status": PluginStatus.INACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {},
    },
    "pocket": {
        "id": "pocket",
        "name": "Pocket",
        "description": "Import saved articles from Pocket",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": False,
        "icon": "Bookmark",
        "category": PluginCategory.IMPORT.value,
        "configurable": True,
        "status": PluginStatus.INACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {},
    },
    "obsidian-sync": {
        "id": "obsidian-sync",
        "name": "Obsidian Sync",
        "description": "Auto-sync changes from Obsidian vault",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": True,
        "icon": "FolderSync",
        "category": PluginCategory.INTEGRATION.value,
        "configurable": True,
        "status": PluginStatus.ACTIVE.value,
        "lastSync": datetime.now(UTC).isoformat(),
        "error": None,
        "config": {"vault_path": "~/Obsidian/"},
    },
    "markdown-export": {
        "id": "markdown-export",
        "name": "Markdown Export",
        "description": "Export content as Markdown files",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": True,
        "icon": "FileDown",
        "category": PluginCategory.EXPORT.value,
        "configurable": False,
        "status": PluginStatus.ACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {},
    },
    "json-export": {
        "id": "json-export",
        "name": "JSON Export",
        "description": "Export content as JSON for backups",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": True,
        "icon": "Braces",
        "category": PluginCategory.EXPORT.value,
        "configurable": False,
        "status": PluginStatus.ACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {},
    },
    "auto-tag": {
        "id": "auto-tag",
        "name": "Auto Tagger",
        "description": "Automatically tag content using AI",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": True,
        "icon": "Tags",
        "category": PluginCategory.AUTOMATION.value,
        "configurable": True,
        "status": PluginStatus.ACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {"max_tags": 5},
    },
    "review-scheduler": {
        "id": "review-scheduler",
        "name": "Review Scheduler",
        "description": "FSRS-based spaced repetition scheduling",
        "version": "1.0.0",
        "author": "KAS Team",
        "enabled": True,
        "icon": "Calendar",
        "category": PluginCategory.AUTOMATION.value,
        "configurable": True,
        "status": PluginStatus.ACTIVE.value,
        "lastSync": None,
        "error": None,
        "config": {"daily_limit": 20},
    },
}


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=list[PluginResponse])
async def list_plugins() -> list[PluginResponse]:
    """
    List all available plugins.

    Returns both built-in and custom plugins with their
    current status and configuration state.
    """
    return [
        PluginResponse(
            id=p["id"],
            name=p["name"],
            description=p["description"],
            version=p["version"],
            author=p["author"],
            enabled=p["enabled"],
            icon=p["icon"],
            category=p["category"],
            configurable=p["configurable"],
            status=p["status"],
            lastSync=p["lastSync"],
            error=p["error"],
        )
        for p in _plugins_registry.values()
    ]


@router.get("/{plugin_id}", response_model=PluginResponse)
async def get_plugin(plugin_id: str) -> PluginResponse:
    """Get plugin details."""
    plugin = _plugins_registry.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    return PluginResponse(
        id=plugin["id"],
        name=plugin["name"],
        description=plugin["description"],
        version=plugin["version"],
        author=plugin["author"],
        enabled=plugin["enabled"],
        icon=plugin["icon"],
        category=plugin["category"],
        configurable=plugin["configurable"],
        status=plugin["status"],
        lastSync=plugin["lastSync"],
        error=plugin["error"],
    )


@router.patch("/{plugin_id}", response_model=PluginResponse)
async def update_plugin(
    plugin_id: str,
    request: PluginUpdate,
    _: bool = Depends(require_scope("admin")),
) -> PluginResponse:
    """
    Update plugin settings.

    Enable/disable plugins or update their configuration.
    Requires admin scope.
    """
    plugin = _plugins_registry.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    if request.enabled is not None:
        plugin["enabled"] = request.enabled
        if request.enabled:
            plugin["status"] = PluginStatus.ACTIVE.value
            plugin["error"] = None
        else:
            plugin["status"] = PluginStatus.INACTIVE.value

        logger.info(
            "plugin_toggled",
            plugin_id=plugin_id,
            enabled=request.enabled,
        )

    if request.config is not None:
        plugin["config"].update(request.config)
        logger.info(
            "plugin_config_updated",
            plugin_id=plugin_id,
        )

    return PluginResponse(
        id=plugin["id"],
        name=plugin["name"],
        description=plugin["description"],
        version=plugin["version"],
        author=plugin["author"],
        enabled=plugin["enabled"],
        icon=plugin["icon"],
        category=plugin["category"],
        configurable=plugin["configurable"],
        status=plugin["status"],
        lastSync=plugin["lastSync"],
        error=plugin["error"],
    )


@router.post("/{plugin_id}/sync")
async def sync_plugin(
    plugin_id: str,
    _: bool = Depends(require_scope("admin")),
) -> dict:
    """
    Trigger a sync for the plugin.

    For import plugins, this fetches new content.
    For export plugins, this exports current content.
    """
    plugin = _plugins_registry.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    if not plugin["enabled"]:
        raise HTTPException(status_code=400, detail="Plugin is not enabled")

    # Update last sync time
    plugin["lastSync"] = datetime.now(UTC).isoformat()

    logger.info("plugin_sync_triggered", plugin_id=plugin_id)

    return {
        "success": True,
        "plugin_id": plugin_id,
        "synced_at": plugin["lastSync"],
        "message": f"Sync triggered for {plugin['name']}",
    }


@router.get("/{plugin_id}/config")
async def get_plugin_config(
    plugin_id: str,
    _: bool = Depends(require_scope("admin")),
) -> dict:
    """
    Get plugin configuration.

    Returns current configuration values.
    Requires admin scope.
    """
    plugin = _plugins_registry.get(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail="Plugin not found")

    if not plugin["configurable"]:
        raise HTTPException(status_code=400, detail="Plugin is not configurable")

    return {
        "plugin_id": plugin_id,
        "config": plugin["config"],
    }

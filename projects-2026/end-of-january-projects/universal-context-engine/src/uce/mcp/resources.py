"""
MCP resource definitions for Universal Context Engine.
"""

from typing import Any

# Resource definitions for MCP server
RESOURCES = [
    {
        "uri": "context://recent",
        "name": "Recent Context",
        "description": "Activity from the last hour across all sources",
        "mimeType": "text/plain",
    },
    {
        "uri": "context://working",
        "name": "Working Context",
        "description": "Current work context including git, browser, and recent documents",
        "mimeType": "text/plain",
    },
    {
        "uri": "context://entities",
        "name": "Active Entities",
        "description": "Most frequently mentioned entities in recent context",
        "mimeType": "text/plain",
    },
]


def get_resource_definition(uri: str) -> dict[str, Any] | None:
    """Get resource definition by URI."""
    for resource in RESOURCES:
        if resource["uri"] == uri:
            return resource
    return None


def list_resources() -> list[dict[str, Any]]:
    """Get all resource definitions."""
    return RESOURCES


__all__ = ["RESOURCES", "get_resource_definition", "list_resources"]

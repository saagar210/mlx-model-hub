"""
MCP tool definitions for Universal Context Engine.
"""

from typing import Any

# Tool definitions for MCP server
TOOLS = [
    {
        "name": "search_context",
        "description": "Search unified context across all sources (KAS, Git, Browser). Returns relevant context items ranked by relevance. Use this for finding specific information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query - what you're looking for",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by sources: kas, git, browser (optional)",
                },
                "hours": {
                    "type": "integer",
                    "description": "Only include context from last N hours (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (default 20)",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_recent_context",
        "description": "Get recent activity across all context sources. Useful for understanding 'what was I working on?' or catching up after a break.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "How many hours back to look (default 24)",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by sources: kas, git, browser (optional)",
                },
            },
        },
    },
    {
        "name": "get_entity_context",
        "description": "Get all context related to a specific entity (technology, tool, concept). Shows mentions across all sources. Use this when you need comprehensive information about a specific topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {
                    "type": "string",
                    "description": "Entity name to look up (e.g., 'OAuth', 'FastAPI', 'PostgreSQL')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 30)",
                },
            },
            "required": ["entity"],
        },
    },
    {
        "name": "get_working_context",
        "description": "Get current working context: recent git changes, open browser tabs, recent agent work. Best for understanding current state and what's actively being worked on.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_related_context",
        "description": "Find context items related to a specific item by ID. Useful for exploring connections and understanding how things relate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "ID of the context item to find related items for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10)",
                },
            },
            "required": ["item_id"],
        },
    },
]


def get_tool_definition(name: str) -> dict[str, Any] | None:
    """Get tool definition by name."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def list_tools() -> list[dict[str, Any]]:
    """Get all tool definitions."""
    return TOOLS


__all__ = ["TOOLS", "get_tool_definition", "list_tools"]

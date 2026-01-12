#!/usr/bin/env python3
"""
Knowledge Activation System MCP Server.

Exposes the Knowledge Activation System to Claude Desktop via MCP protocol.
Uses FastMCP for tool and resource definitions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
    Resource,
    ResourceTemplate,
)
from pydantic import BaseModel, Field

# Add src to path for knowledge imports
sys.path.insert(0, str(__file__).replace("/mcp-server/server.py", "/src"))

from knowledge.config import get_settings
from knowledge.db import Database, get_db, close_db
from knowledge.search import hybrid_search, SearchResult
from knowledge.review import (
    ReviewRating,
    get_due_items,
    get_review_stats,
    submit_review,
)

# Configure logging to stderr (important for MCP - stdout is for protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Create MCP server instance
server = Server("knowledge-activation")

# Global database instance
_db: Database | None = None


async def get_database() -> Database:
    """Get or create database connection."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
        logger.info("Database connection established")
    return _db


async def cleanup_database() -> None:
    """Cleanup database connection."""
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None
        logger.info("Database connection closed")


# =============================================================================
# Tool Input Models
# =============================================================================


class SearchKnowledgeInput(BaseModel):
    """Input for search_knowledge tool."""

    query: str = Field(..., description="Search query text")
    limit: int = Field(10, description="Number of results to return (default: 10)")
    content_type: str | None = Field(
        None, description="Filter by content type (youtube, bookmark, file, note)"
    )


class GetContentInput(BaseModel):
    """Input for get_content tool."""

    content_id: str = Field(..., description="UUID of the content to retrieve")


class ListRecentInput(BaseModel):
    """Input for list_recent tool."""

    days: int = Field(7, description="Number of days to look back (default: 7)")
    limit: int = Field(20, description="Maximum items to return (default: 20)")


class RecordReviewInput(BaseModel):
    """Input for record_review tool."""

    content_id: str = Field(..., description="UUID of the content being reviewed")
    rating: int = Field(
        ...,
        ge=1,
        le=4,
        description="Rating: 1=Again (forgot), 2=Hard, 3=Good, 4=Easy",
    )


class GetDueReviewsInput(BaseModel):
    """Input for get_due_reviews tool."""

    limit: int = Field(10, description="Maximum items to return (default: 10)")


# =============================================================================
# Tool Definitions
# =============================================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_knowledge",
            description=(
                "Search the knowledge base using hybrid search (BM25 + vector similarity). "
                "Returns relevant content with titles, snippets, and relevance scores."
            ),
            inputSchema=SearchKnowledgeInput.model_json_schema(),
        ),
        Tool(
            name="get_content",
            description=(
                "Get full details of a content item by ID. "
                "Returns title, summary, metadata, chunks, and source information."
            ),
            inputSchema=GetContentInput.model_json_schema(),
        ),
        Tool(
            name="list_recent",
            description=(
                "List recently added content items. "
                "Useful for seeing what's new in the knowledge base."
            ),
            inputSchema=ListRecentInput.model_json_schema(),
        ),
        Tool(
            name="get_stats",
            description=(
                "Get database statistics including total items, counts by type, "
                "chunk counts, and review queue status."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="record_review",
            description=(
                "Submit a spaced repetition review rating for a content item. "
                "Ratings: 1=Again (forgot), 2=Hard, 3=Good, 4=Easy. "
                "Returns the next review date."
            ),
            inputSchema=RecordReviewInput.model_json_schema(),
        ),
        Tool(
            name="get_due_reviews",
            description=(
                "Get content items that are due for spaced repetition review. "
                "Returns items sorted by due date with preview text."
            ),
            inputSchema=GetDueReviewsInput.model_json_schema(),
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "search_knowledge":
            return await handle_search_knowledge(arguments)
        elif name == "get_content":
            return await handle_get_content(arguments)
        elif name == "list_recent":
            return await handle_list_recent(arguments)
        elif name == "get_stats":
            return await handle_get_stats()
        elif name == "record_review":
            return await handle_record_review(arguments)
        elif name == "get_due_reviews":
            return await handle_get_due_reviews(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.exception(f"Error in tool {name}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_search_knowledge(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle search_knowledge tool."""
    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)
    content_type = arguments.get("content_type")

    if not query:
        return [TextContent(type="text", text="Error: query is required")]

    db = await get_database()
    results = await hybrid_search(query, limit=limit, db=db)

    # Filter by content type if specified
    if content_type:
        results = [r for r in results if r.content_type == content_type]

    if not results:
        return [TextContent(type="text", text=f"No results found for: {query}")]

    # Format results
    output_lines = [f"Found {len(results)} results for: {query}\n"]

    for i, result in enumerate(results, 1):
        snippet = (
            result.chunk_text[:200] + "..."
            if result.chunk_text and len(result.chunk_text) > 200
            else result.chunk_text or "No preview available"
        )
        output_lines.append(
            f"{i}. [{result.content_type}] {result.title}\n"
            f"   ID: {result.content_id}\n"
            f"   Score: {result.score:.4f}\n"
            f"   Snippet: {snippet}\n"
        )

    return [TextContent(type="text", text="\n".join(output_lines))]


async def handle_get_content(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_content tool."""
    content_id_str = arguments.get("content_id", "")

    if not content_id_str:
        return [TextContent(type="text", text="Error: content_id is required")]

    try:
        content_id = UUID(content_id_str)
    except ValueError:
        return [TextContent(type="text", text=f"Error: Invalid UUID: {content_id_str}")]

    db = await get_database()
    content = await db.get_content_by_id(content_id)

    if not content:
        return [TextContent(type="text", text=f"Content not found: {content_id}")]

    # Get chunks
    chunks = await db.get_chunks_by_content_id(content_id)

    # Format output
    output = {
        "id": str(content.id),
        "title": content.title,
        "type": content.type,
        "filepath": content.filepath,
        "url": content.url,
        "summary": content.summary,
        "tags": content.tags,
        "metadata": content.metadata,
        "created_at": content.created_at.isoformat(),
        "updated_at": content.updated_at.isoformat(),
        "chunk_count": len(chunks),
        "chunks": [
            {
                "index": c.chunk_index,
                "text": c.chunk_text[:500] + "..." if len(c.chunk_text) > 500 else c.chunk_text,
                "source_ref": c.source_ref,
            }
            for c in chunks[:5]  # Limit to first 5 chunks
        ],
    }

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def handle_list_recent(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle list_recent tool."""
    days = arguments.get("days", 7)
    limit = arguments.get("limit", 20)

    db = await get_database()
    cutoff = datetime.utcnow() - timedelta(days=days)

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, type, summary, created_at
            FROM content
            WHERE deleted_at IS NULL AND created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            cutoff,
            limit,
        )

    if not rows:
        return [TextContent(type="text", text=f"No content added in the last {days} days")]

    output_lines = [f"Recently added content (last {days} days):\n"]

    for row in rows:
        summary_preview = (
            row["summary"][:100] + "..."
            if row["summary"] and len(row["summary"]) > 100
            else row["summary"] or "No summary"
        )
        output_lines.append(
            f"- [{row['type']}] {row['title']}\n"
            f"  ID: {row['id']}\n"
            f"  Added: {row['created_at'].strftime('%Y-%m-%d %H:%M')}\n"
            f"  Summary: {summary_preview}\n"
        )

    return [TextContent(type="text", text="\n".join(output_lines))]


async def handle_get_stats() -> list[TextContent]:
    """Handle get_stats tool."""
    db = await get_database()
    stats = await db.get_stats()

    output = {
        "total_content": stats["total_content"],
        "total_chunks": stats["total_chunks"],
        "content_by_type": stats["content_by_type"],
        "review_queue": {
            "active": stats["review_active"],
            "due": stats["review_due"],
        },
    }

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def handle_record_review(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle record_review tool."""
    content_id_str = arguments.get("content_id", "")
    rating_int = arguments.get("rating")

    if not content_id_str:
        return [TextContent(type="text", text="Error: content_id is required")]

    if rating_int is None or rating_int < 1 or rating_int > 4:
        return [TextContent(type="text", text="Error: rating must be 1-4")]

    try:
        content_id = UUID(content_id_str)
    except ValueError:
        return [TextContent(type="text", text=f"Error: Invalid UUID: {content_id_str}")]

    # Map integer rating to ReviewRating enum
    rating_map = {
        1: ReviewRating.AGAIN,
        2: ReviewRating.HARD,
        3: ReviewRating.GOOD,
        4: ReviewRating.EASY,
    }
    rating = rating_map[rating_int]

    # Initialize database for review module
    await get_database()

    result = await submit_review(content_id, rating)

    if result is None:
        return [TextContent(type="text", text=f"Content not in review queue: {content_id}")]

    output = {
        "content_id": str(result.content_id),
        "rating": result.rating.value,
        "old_state": result.old_state.name,
        "new_state": result.new_state.name,
        "next_review": result.new_due.isoformat(),
        "review_time": result.review_time.isoformat(),
    }

    return [TextContent(type="text", text=json.dumps(output, indent=2))]


async def handle_get_due_reviews(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_due_reviews tool."""
    limit = arguments.get("limit", 10)

    # Initialize database for review module
    await get_database()

    items = await get_due_items(limit=limit)

    if not items:
        return [TextContent(type="text", text="No items due for review")]

    output_lines = [f"Items due for review ({len(items)} items):\n"]

    for item in items:
        preview = (
            item.preview_text[:150] + "..."
            if len(item.preview_text) > 150
            else item.preview_text or "No preview"
        )
        state_label = "New" if item.is_new else ("Learning" if item.is_learning else "Review")
        output_lines.append(
            f"- [{item.content_type}] {item.title}\n"
            f"  ID: {item.content_id}\n"
            f"  State: {state_label} | Stability: {item.stability:.1f} | Difficulty: {item.difficulty:.1f}\n"
            f"  Due: {item.due.strftime('%Y-%m-%d %H:%M')}\n"
            f"  Preview: {preview}\n"
        )

    return [TextContent(type="text", text="\n".join(output_lines))]


# =============================================================================
# Resource Definitions
# =============================================================================


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return [
        Resource(
            uri="knowledge://stats",
            name="Knowledge Base Statistics",
            description="Current database statistics including item counts and review queue status",
            mimeType="application/json",
        ),
        Resource(
            uri="knowledge://recent",
            name="Recently Added Content",
            description="Content added in the last 7 days",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource."""
    if uri == "knowledge://stats":
        return await read_stats_resource()
    elif uri == "knowledge://recent":
        return await read_recent_resource()
    else:
        raise ValueError(f"Unknown resource: {uri}")


async def read_stats_resource() -> str:
    """Read stats resource."""
    db = await get_database()
    stats = await db.get_stats()

    output = {
        "total_content": stats["total_content"],
        "total_chunks": stats["total_chunks"],
        "content_by_type": stats["content_by_type"],
        "review_queue": {
            "active": stats["review_active"],
            "due": stats["review_due"],
        },
    }

    return json.dumps(output, indent=2)


async def read_recent_resource() -> str:
    """Read recent content resource."""
    db = await get_database()
    cutoff = datetime.utcnow() - timedelta(days=7)

    async with db.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, title, type, summary, created_at
            FROM content
            WHERE deleted_at IS NULL AND created_at >= $1
            ORDER BY created_at DESC
            LIMIT 20
            """,
            cutoff,
        )

    items = [
        {
            "id": str(row["id"]),
            "title": row["title"],
            "type": row["type"],
            "summary": row["summary"],
            "created_at": row["created_at"].isoformat(),
        }
        for row in rows
    ]

    return json.dumps({"items": items, "count": len(items)}, indent=2)


# =============================================================================
# Main Entry Point
# =============================================================================


async def main() -> None:
    """Run the MCP server."""
    logger.info("Starting Knowledge Activation System MCP Server")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    finally:
        await cleanup_database()
        logger.info("MCP Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())

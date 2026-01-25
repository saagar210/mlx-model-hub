"""MCP Server implementation for Knowledge Engine.

This server exposes the Knowledge Engine capabilities to Claude Desktop
and Claude Code via the Model Context Protocol (MCP).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    TextContent,
    Tool,
)

from knowledge_engine.config import get_settings
from knowledge_engine.core.engine import KnowledgeEngine
from knowledge_engine.models.documents import DocumentCreate, DocumentType
from knowledge_engine.models.memory import MemoryCreate, MemoryType
from knowledge_engine.models.search import HybridSearchRequest
from knowledge_engine.models.query import QueryRequest

logger = logging.getLogger(__name__)

# Global engine instance for MCP server
_engine: KnowledgeEngine | None = None


async def get_engine() -> KnowledgeEngine:
    """Get or create the Knowledge Engine instance."""
    global _engine
    if _engine is None:
        _engine = KnowledgeEngine(get_settings())
        await _engine.initialize()
    return _engine


def create_mcp_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("knowledge-engine")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="knowledge_search",
                description="Search the knowledge base with hybrid retrieval (vector + graph + BM25)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace to search (default: 'default')",
                            "default": "default",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of results to return (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="knowledge_query",
                description="Ask a question and get an answer with citations using RAG",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "The question to answer",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace to query (default: 'default')",
                            "default": "default",
                        },
                        "include_citations": {
                            "type": "boolean",
                            "description": "Include source citations (default: true)",
                            "default": True,
                        },
                    },
                    "required": ["question"],
                },
            ),
            Tool(
                name="knowledge_ingest",
                description="Add content to the knowledge base",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The content to ingest",
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional title for the content",
                        },
                        "document_type": {
                            "type": "string",
                            "description": "Type of document (text, markdown, code, note)",
                            "enum": ["text", "markdown", "code", "note"],
                            "default": "text",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace to store in (default: 'default')",
                            "default": "default",
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="knowledge_remember",
                description="Store a memory for later recall",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "The memory content to store",
                        },
                        "memory_type": {
                            "type": "string",
                            "description": "Type of memory (fact, preference, context, procedure)",
                            "enum": ["fact", "preference", "context", "procedure"],
                            "default": "fact",
                        },
                        "context": {
                            "type": "string",
                            "description": "Optional context about when/why this was stored",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace to store in (default: 'default')",
                            "default": "default",
                        },
                        "importance": {
                            "type": "number",
                            "description": "Importance score 0-1 (default: 0.5)",
                            "default": 0.5,
                        },
                    },
                    "required": ["content"],
                },
            ),
            Tool(
                name="knowledge_recall",
                description="Recall memories relevant to a query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query to find relevant memories",
                        },
                        "namespace": {
                            "type": "string",
                            "description": "Namespace to search (default: 'default')",
                            "default": "default",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of memories to return (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        engine = await get_engine()

        try:
            if name == "knowledge_search":
                request = HybridSearchRequest(
                    query=arguments["query"],
                    namespace=arguments.get("namespace", "default"),
                    limit=arguments.get("limit", 10),
                    rerank=True,
                    include_graph=True,
                )
                result = await engine.search(request)

                # Format results
                output = f"Found {result.total_results} results for '{result.query}':\n\n"
                for i, item in enumerate(result.items, 1):
                    output += f"{i}. **{item.title or 'Untitled'}** (score: {item.score:.3f})\n"
                    output += f"   {item.content[:200]}...\n\n"

                return [TextContent(type="text", text=output)]

            elif name == "knowledge_query":
                request = QueryRequest(
                    question=arguments["question"],
                    namespace=arguments.get("namespace", "default"),
                    include_citations=arguments.get("include_citations", True),
                )
                result = await engine.query(request)

                # Format response
                output = f"**Answer** (confidence: {result.confidence.value})\n\n"
                output += f"{result.answer}\n\n"

                if result.citations:
                    output += "**Sources:**\n"
                    for i, citation in enumerate(result.citations, 1):
                        output += f"{i}. {citation.title or 'Source'}"
                        if citation.source:
                            output += f" ({citation.source})"
                        output += "\n"

                return [TextContent(type="text", text=output)]

            elif name == "knowledge_ingest":
                doc_type = DocumentType(arguments.get("document_type", "text"))
                doc = DocumentCreate(
                    content=arguments["content"],
                    title=arguments.get("title"),
                    document_type=doc_type,
                    namespace=arguments.get("namespace", "default"),
                )
                result = await engine.ingest_document(doc)

                return [
                    TextContent(
                        type="text",
                        text=f"Ingested document '{result.title or result.id}' "
                        f"with {result.chunk_count} chunks",
                    )
                ]

            elif name == "knowledge_remember":
                memory_type = MemoryType(arguments.get("memory_type", "fact"))
                memory = MemoryCreate(
                    content=arguments["content"],
                    memory_type=memory_type,
                    context=arguments.get("context"),
                    namespace=arguments.get("namespace", "default"),
                    importance=arguments.get("importance", 0.5),
                )
                result = await engine.store_memory(memory)

                return [
                    TextContent(
                        type="text",
                        text=f"Stored memory {result.id} ({result.memory_type.value})",
                    )
                ]

            elif name == "knowledge_recall":
                memories = await engine.recall_memories(
                    query=arguments["query"],
                    namespace=arguments.get("namespace", "default"),
                    limit=arguments.get("limit", 10),
                )

                if not memories:
                    return [TextContent(type="text", text="No relevant memories found.")]

                output = f"Found {len(memories)} relevant memories:\n\n"
                for i, memory in enumerate(memories, 1):
                    output += f"{i}. [{memory.memory_type.value}] {memory.content[:200]}"
                    if len(memory.content) > 200:
                        output += "..."
                    output += f"\n   (importance: {memory.importance:.1f})\n\n"

                return [TextContent(type="text", text=output)]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            logger.exception("Tool call failed: %s", e)
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available resources."""
        return [
            Resource(
                uri="knowledge://health",
                name="Health Status",
                description="Current health status of Knowledge Engine components",
            ),
            Resource(
                uri="knowledge://namespaces",
                name="Namespaces",
                description="List of available namespaces",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Read a resource."""
        engine = await get_engine()

        if uri == "knowledge://health":
            health = await engine.health_check()
            output = "**Knowledge Engine Health**\n\n"
            for component, status in health.items():
                emoji = "✅" if status else "❌"
                output += f"{emoji} {component}: {'healthy' if status else 'unhealthy'}\n"
            return output

        elif uri == "knowledge://namespaces":
            # TODO: Implement namespace listing
            return "**Namespaces**\n\n- default"

        return f"Unknown resource: {uri}"

    return server


async def run_mcp_server() -> None:
    """Run the MCP server."""
    server = create_mcp_server()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for MCP server."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()

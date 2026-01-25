#!/usr/bin/env python3
"""
Universal Context Engine MCP Server.

Exposes UCE capabilities to Claude Code via Model Context Protocol.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from uuid import UUID

import asyncpg

from ..core.config import settings
from ..search.hybrid_search import HybridSearchEngine
from ..models.search import SearchQuery
from .tools import TOOLS
from .resources import RESOURCES


class UCEMCPServer:
    """MCP Server for Universal Context Engine."""

    def __init__(self) -> None:
        """Initialize server (connections created on startup)."""
        self.pg_pool: asyncpg.Pool | None = None
        self.search_engine: HybridSearchEngine | None = None

    async def initialize(self) -> None:
        """Initialize database connections."""
        db_url = settings.database_url.replace("+asyncpg", "")
        self.pg_pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=10,
        )
        self.search_engine = HybridSearchEngine(
            self.pg_pool,
            ollama_url=settings.ollama_url,
            embedding_model=settings.embedding_model,
        )

    async def close(self) -> None:
        """Close connections."""
        if self.pg_pool:
            await self.pg_pool.close()

    async def handle_request(self, request: dict) -> dict:
        """Handle incoming MCP request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                return self._handle_initialize(request_id)
            elif method == "tools/list":
                return self._handle_list_tools(request_id)
            elif method == "tools/call":
                result = await self._handle_call_tool(params)
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            elif method == "resources/list":
                return self._handle_list_resources(request_id)
            elif method == "resources/read":
                result = await self._handle_read_resource(params)
                return {"jsonrpc": "2.0", "id": request_id, "result": result}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(e)},
            }

    def _handle_initialize(self, request_id: int | str | None) -> dict:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                    "resources": {},
                },
                "serverInfo": {
                    "name": "universal-context-engine",
                    "version": settings.app_version,
                },
            },
        }

    def _handle_list_tools(self, request_id: int | str | None) -> dict:
        """Handle tools/list request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOLS},
        }

    async def _handle_call_tool(self, params: dict) -> dict:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "search_context":
            return await self._search_context(arguments)
        elif tool_name == "get_recent_context":
            return await self._get_recent_context(arguments)
        elif tool_name == "get_entity_context":
            return await self._get_entity_context(arguments)
        elif tool_name == "get_working_context":
            return await self._get_working_context()
        elif tool_name == "get_related_context":
            return await self._get_related_context(arguments)
        else:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
            }

    def _handle_list_resources(self, request_id: int | str | None) -> dict:
        """Handle resources/list request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"resources": RESOURCES},
        }

    async def _handle_read_resource(self, params: dict) -> dict:
        """Handle resources/read request."""
        uri = params.get("uri")

        if uri == "context://recent":
            result = await self._get_recent_context({"hours": 1})
            return {"contents": [{"uri": uri, **result["content"][0]}]}
        elif uri == "context://working":
            result = await self._get_working_context()
            return {"contents": [{"uri": uri, **result["content"][0]}]}
        elif uri == "context://entities":
            result = await self._get_active_entities()
            return {"contents": [{"uri": uri, **result["content"][0]}]}
        else:
            return {"contents": [{"uri": uri, "text": f"Unknown resource: {uri}"}]}

    async def _search_context(self, args: dict) -> dict:
        """Search unified context."""
        if not self.search_engine:
            return {"content": [{"type": "text", "text": "Search engine not initialized"}], "isError": True}

        query = SearchQuery(
            query=args["query"],
            sources=args.get("sources"),
            since=datetime.utcnow() - timedelta(hours=args["hours"]) if args.get("hours") else None,
        )

        response = await self.search_engine.search(query, limit=args.get("limit", 20))

        formatted = []
        for result in response.results:
            item = result.item
            time_str = item.temporal.t_valid.strftime("%Y-%m-%d %H:%M")
            entities_str = ", ".join(item.entities[:5]) if item.entities else "none"

            formatted.append(
                f"**[{item.source}:{item.content_type}]** ({time_str})\n"
                f"### {item.title}\n"
                f"{item.content[:500]}{'...' if len(item.content) > 500 else ''}\n"
                f"*Entities: {entities_str} | Score: {result.score:.3f}*\n"
                f"---"
            )

        output = f"## Search Results for: {query.query}\n"
        output += f"*Found {response.total} items in {response.search_time_ms:.0f}ms*\n\n"
        output += "\n\n".join(formatted) if formatted else "No results found."

        return {"content": [{"type": "text", "text": output}]}

    async def _get_recent_context(self, args: dict) -> dict:
        """Get recent context activity."""
        hours = args.get("hours", 24)
        sources = args.get("sources")

        if not self.pg_pool:
            return {"content": [{"type": "text", "text": "Database not initialized"}], "isError": True}

        async with self.pg_pool.acquire() as conn:
            params: list = [datetime.utcnow() - timedelta(hours=hours)]
            source_filter = ""
            if sources:
                source_filter = "AND source = ANY($2)"
                params.append(sources)

            rows = await conn.fetch(
                f"""
                SELECT source, content_type, title, content, t_valid, entities
                FROM context_items
                WHERE t_valid >= $1
                  AND t_expired IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                  {source_filter}
                ORDER BY t_valid DESC
                LIMIT 50
                """,
                *params,
            )

        formatted = [f"## Recent Context (last {hours} hours)\n"]

        # Group by source
        by_source: dict[str, list] = {}
        for row in rows:
            source = row["source"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(row)

        for source, items in by_source.items():
            formatted.append(f"\n### {source.upper()} ({len(items)} items)")
            for row in items[:10]:
                time_str = row["t_valid"].strftime("%H:%M")
                formatted.append(f"- [{time_str}] {row['title'][:60]}")

        return {"content": [{"type": "text", "text": "\n".join(formatted)}]}

    async def _get_entity_context(self, args: dict) -> dict:
        """Get context for a specific entity."""
        entity = args["entity"]
        limit = args.get("limit", 30)

        if not self.pg_pool:
            return {"content": [{"type": "text", "text": "Database not initialized"}], "isError": True}

        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source, content_type, title, content, t_valid
                FROM context_items
                WHERE $1 = ANY(entities)
                  AND t_expired IS NULL
                ORDER BY t_valid DESC
                LIMIT $2
                """,
                entity.lower(),
                limit,
            )

        formatted = [f"## Context for Entity: {entity}\n"]
        formatted.append(f"*Found {len(rows)} mentions*\n")

        for row in rows:
            time_str = row["t_valid"].strftime("%Y-%m-%d %H:%M")
            formatted.append(
                f"### [{row['source']}] {row['title']}\n"
                f"*{time_str}*\n"
                f"{row['content'][:400]}{'...' if len(row['content']) > 400 else ''}\n"
            )

        return {"content": [{"type": "text", "text": "\n".join(formatted)}]}

    async def _get_working_context(self) -> dict:
        """Get current working context."""
        output = ["## Current Working Context\n"]

        if not self.pg_pool:
            return {"content": [{"type": "text", "text": "Database not initialized"}], "isError": True}

        async with self.pg_pool.acquire() as conn:
            # Recent git activity
            git_rows = await conn.fetch(
                """
                SELECT title, content, t_valid FROM context_items
                WHERE source = 'git' AND t_valid >= NOW() - INTERVAL '4 hours'
                  AND t_expired IS NULL
                ORDER BY t_valid DESC LIMIT 5
                """
            )

            if git_rows:
                output.append("### Recent Git Activity")
                for row in git_rows:
                    output.append(f"- {row['title'][:70]}")

            # Browser tabs
            browser_rows = await conn.fetch(
                """
                SELECT title, metadata FROM context_items
                WHERE source = 'browser' AND t_expired IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY t_valid DESC LIMIT 5
                """
            )

            if browser_rows:
                output.append("\n### Open Tabs")
                for row in browser_rows:
                    url = (row["metadata"] or {}).get("url", "")
                    output.append(f"- {row['title'][:50]} ({url[:30]})")

            # Recent KAS documents
            kas_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (source_id) title, t_valid FROM context_items
                WHERE source = 'kas' AND t_valid >= NOW() - INTERVAL '24 hours'
                  AND t_expired IS NULL
                ORDER BY source_id, t_valid DESC
                LIMIT 5
                """
            )

            if kas_rows:
                output.append("\n### Recent Documents")
                for row in kas_rows:
                    output.append(f"- {row['title'][:60]}")

            # Active entities
            entity_rows = await conn.fetch(
                """
                SELECT unnest(entities) as entity, count(*) as cnt
                FROM context_items
                WHERE t_valid >= NOW() - INTERVAL '24 hours'
                  AND t_expired IS NULL
                GROUP BY entity
                ORDER BY cnt DESC
                LIMIT 10
                """
            )

            if entity_rows:
                output.append("\n### Active Entities")
                entities = [f"{row['entity']} ({row['cnt']})" for row in entity_rows]
                output.append(", ".join(entities))

        return {"content": [{"type": "text", "text": "\n".join(output)}]}

    async def _get_related_context(self, args: dict) -> dict:
        """Find related context items."""
        item_id = args["item_id"]
        limit = args.get("limit", 10)

        if not self.search_engine:
            return {"content": [{"type": "text", "text": "Search engine not initialized"}], "isError": True}

        try:
            results = await self.search_engine.search_similar(UUID(item_id), limit)
        except ValueError:
            return {"content": [{"type": "text", "text": f"Invalid item ID: {item_id}"}], "isError": True}

        formatted = [f"## Related Context Items\n"]

        for result in results:
            item = result.item
            formatted.append(
                f"### [{item.source}] {item.title}\n"
                f"{item.content[:300]}...\n"
                f"*Similarity: {result.score:.3f}*\n"
            )

        return {"content": [{"type": "text", "text": "\n".join(formatted)}]}

    async def _get_active_entities(self) -> dict:
        """Get most active entities."""
        if not self.pg_pool:
            return {"content": [{"type": "text", "text": "Database not initialized"}], "isError": True}

        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT canonical_name, display_name, entity_type, mention_count
                FROM entities
                WHERE last_seen_at >= NOW() - INTERVAL '7 days'
                ORDER BY mention_count DESC
                LIMIT 20
                """
            )

        output = ["## Active Entities (Last 7 Days)\n"]
        for row in rows:
            output.append(
                f"- **{row['display_name']}** ({row['entity_type']}) - {row['mention_count']} mentions"
            )

        return {"content": [{"type": "text", "text": "\n".join(output)}]}

    async def run(self) -> None:
        """Run the MCP server (stdio transport)."""
        await self.initialize()

        # Read from stdin, write to stdout
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                if not line:
                    break

                request = json.loads(line.strip())
                response = await self.handle_request(request)

                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(e)},
                }
                print(json.dumps(error_response), flush=True)

        await self.close()


async def main() -> None:
    """Main entry point."""
    server = UCEMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())

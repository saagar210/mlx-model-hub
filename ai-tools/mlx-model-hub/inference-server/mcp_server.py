#!/usr/bin/env python3
"""Standalone MCP server for Claude Desktop integration.

This script runs as a stdio-based MCP server that Claude Desktop can communicate with.
It provides access to local MLX models for text, vision, speech, and transcription.

Usage:
    python mcp_server.py

Claude Desktop Configuration (~/.config/claude/claude_desktop_config.json):
{
    "mcpServers": {
        "unified-mlx": {
            "command": "python",
            "args": ["/path/to/unified-mlx-app/mcp_server.py"]
        }
    }
}
"""

import asyncio
import json
import logging
import sys
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(__file__).replace("/mcp_server.py", "/src"))

from unified_mlx_app.mcp.server import mcp_server
from unified_mlx_app.mcp.tools import TOOLS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("/tmp/unified-mlx-mcp.log")],
)
logger = logging.getLogger(__name__)


class StdioMCPServer:
    """MCP server communicating via stdio (JSON-RPC 2.0)."""

    def __init__(self):
        self.server = mcp_server

    async def handle_request(self, request: dict) -> dict:
        """Handle a JSON-RPC request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        logger.info(f"Received request: {method}")

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "notifications/initialized":
                # Client notification, no response needed
                return None
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")

            return self._success_response(req_id, result)

        except Exception as e:
            logger.error(f"Error handling {method}: {e}")
            return self._error_response(req_id, -32000, str(e))

    def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
            },
            "serverInfo": {
                "name": "unified-mlx",
                "version": "0.1.0",
            },
        }

    def _handle_tools_list(self) -> dict:
        """Handle tools/list request."""
        return {"tools": TOOLS}

    async def _handle_tools_call(self, params: dict) -> dict:
        """Handle tools/call request."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        result = await self.server.call_tool(name, arguments)
        return result

    def _success_response(self, req_id: Any, result: Any) -> dict:
        """Create a success response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result,
        }

    def _error_response(self, req_id: Any, code: int, message: str) -> dict:
        """Create an error response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    async def run(self):
        """Run the stdio server."""
        logger.info("Starting Unified MLX MCP server (stdio mode)")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, reader, asyncio.get_event_loop())

        while True:
            try:
                # Read line from stdin
                line = await reader.readline()
                if not line:
                    break

                line = line.decode("utf-8").strip()
                if not line:
                    continue

                logger.debug(f"Received: {line}")

                # Parse JSON-RPC request
                request = json.loads(line)
                response = await self.handle_request(request)

                if response:
                    # Write response to stdout
                    response_str = json.dumps(response) + "\n"
                    writer.write(response_str.encode("utf-8"))
                    await writer.drain()
                    logger.debug(f"Sent: {response_str.strip()}")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except Exception as e:
                logger.error(f"Error in main loop: {e}")


def main():
    """Main entry point."""
    server = StdioMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()

"""FastAPI routes for MCP HTTP endpoint."""

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from .server import mcp_server

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mcp", tags=["MCP"])


class ToolCallRequest(BaseModel):
    """Request to call an MCP tool."""

    name: str
    arguments: dict[str, Any] = {}


class ToolCallResponse(BaseModel):
    """Response from an MCP tool call."""

    content: list[dict] | None = None
    error: str | None = None
    isError: bool = False


@router.get("/tools")
async def list_tools():
    """List available MCP tools."""
    return {"tools": mcp_server.list_tools()}


@router.post("/call")
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Call an MCP tool."""
    logger.info(f"MCP tool call: {request.name}")
    result = await mcp_server.call_tool(request.name, request.arguments)
    return ToolCallResponse(**result)


@router.get("/info")
async def mcp_info():
    """Get MCP server information."""
    return {
        "name": "unified-mlx",
        "version": "0.1.0",
        "description": "Local MLX models for text, vision, speech, and transcription",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False,
        },
    }

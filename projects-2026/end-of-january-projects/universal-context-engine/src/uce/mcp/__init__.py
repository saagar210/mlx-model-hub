"""UCE MCP server."""

from .server import UCEMCPServer, main
from .tools import TOOLS, list_tools
from .resources import RESOURCES, list_resources

__all__ = [
    "UCEMCPServer",
    "main",
    "TOOLS",
    "list_tools",
    "RESOURCES",
    "list_resources",
]

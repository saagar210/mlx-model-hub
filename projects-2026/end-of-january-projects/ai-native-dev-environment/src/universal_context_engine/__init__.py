"""Universal Context Engine - Persistent memory and orchestration for AI development."""

__version__ = "0.1.0"

# Export mcp server instance for verification
from .server import mcp

__all__ = ["mcp", "__version__"]

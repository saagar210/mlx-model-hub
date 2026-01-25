"""FastAPI dependencies for Knowledge Engine."""

from fastapi import Request

from knowledge_engine.core.engine import KnowledgeEngine


def get_engine(request: Request) -> KnowledgeEngine:
    """Dependency to get the Knowledge Engine instance."""
    return request.app.state.engine

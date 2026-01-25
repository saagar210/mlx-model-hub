"""
Langfuse integration for LocalCrew (CrewAI-based) workflows.

Provides decorators and utilities for tracing crew executions, agent tasks,
and LLM generations to Langfuse for observability and evaluation.

Usage:
    from localcrew.integrations.langfuse_client import trace_crew, trace_agent, trace_generation

    @trace_crew("research_crew")
    async def run_research(topic: str):
        ...

    @trace_agent("researcher")
    async def research_task(query: str):
        ...
"""

from __future__ import annotations

import os
import logging
from functools import wraps
from typing import Any, Callable, Optional, TypeVar
from datetime import datetime
from uuid import uuid4

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

logger = logging.getLogger(__name__)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


def get_langfuse_client() -> Optional[Langfuse]:
    """
    Initialize and return a Langfuse client.

    Returns None if Langfuse is disabled or not configured.
    """
    if not os.getenv("LANGFUSE_ENABLED", "true").lower() in ("true", "1", "yes"):
        logger.debug("Langfuse disabled via LANGFUSE_ENABLED")
        return None

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://localhost:3002")

    if not public_key or not secret_key:
        logger.warning("Langfuse keys not configured, tracing disabled")
        return None

    try:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            flush_at=10,  # Flush after 10 events
            flush_interval=5,  # Or every 5 seconds
        )
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        return None


# Global client instance (lazy initialization)
_langfuse: Optional[Langfuse] = None


def get_client() -> Optional[Langfuse]:
    """Get or create the global Langfuse client."""
    global _langfuse
    if _langfuse is None:
        _langfuse = get_langfuse_client()
    return _langfuse


def trace_crew(crew_name: str, version: str = "1.0"):
    """
    Decorator to trace entire crew execution.

    Creates a top-level trace for the crew run, capturing:
    - Crew name and version
    - Start/end times
    - Final output
    - Nested agent spans

    Args:
        crew_name: Name of the crew (e.g., "research_crew", "task_decomposition")
        version: Version string for the crew

    Example:
        @trace_crew("research_crew")
        async def run_research(topic: str) -> str:
            # Crew execution logic
            return result
    """
    def decorator(func: F) -> F:
        @wraps(func)
        @observe(name=crew_name)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Update trace with crew metadata
            langfuse_context.update_current_trace(
                metadata={
                    "crew_name": crew_name,
                    "version": version,
                    "started_at": datetime.utcnow().isoformat(),
                },
                tags=["localcrew", crew_name],
            )

            try:
                result = await func(*args, **kwargs)
                langfuse_context.update_current_trace(
                    output=str(result)[:5000] if result else None,  # Truncate for storage
                )
                return result
            except Exception as e:
                langfuse_context.update_current_trace(
                    metadata={"error": str(e), "error_type": type(e).__name__},
                    tags=["error"],
                )
                raise

        @wraps(func)
        @observe(name=crew_name)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_trace(
                metadata={
                    "crew_name": crew_name,
                    "version": version,
                    "started_at": datetime.utcnow().isoformat(),
                },
                tags=["localcrew", crew_name],
            )

            try:
                result = func(*args, **kwargs)
                langfuse_context.update_current_trace(
                    output=str(result)[:5000] if result else None,
                )
                return result
            except Exception as e:
                langfuse_context.update_current_trace(
                    metadata={"error": str(e), "error_type": type(e).__name__},
                    tags=["error"],
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def trace_agent(agent_name: str):
    """
    Decorator to trace individual agent tasks within a crew.

    Creates a span for the agent's work, nested under the crew trace.

    Args:
        agent_name: Name of the agent (e.g., "researcher", "writer")

    Example:
        @trace_agent("researcher")
        async def research_task(query: str) -> dict:
            # Agent task logic
            return {"findings": [...]}
    """
    def decorator(func: F) -> F:
        @wraps(func)
        @observe(name=f"agent_{agent_name}")
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_observation(
                metadata={"agent": agent_name}
            )
            return await func(*args, **kwargs)

        @wraps(func)
        @observe(name=f"agent_{agent_name}")
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_observation(
                metadata={"agent": agent_name}
            )
            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def trace_generation(model: str = "qwen2.5:14b"):
    """
    Decorator for LLM generation calls.

    Captures the prompt, completion, model info, and token usage.

    Args:
        model: Model identifier (e.g., "mlx/qwen2.5:14b", "ollama/llama3")

    Example:
        @trace_generation(model="mlx/qwen2.5:14b")
        async def generate(prompt: str) -> str:
            # LLM generation logic
            return completion
    """
    def decorator(func: F) -> F:
        @wraps(func)
        @observe(as_type="generation")
        async def async_wrapper(prompt: str, *args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_observation(
                model=model,
                input=prompt[:2000],  # Truncate input for storage
            )

            result = await func(prompt, *args, **kwargs)

            langfuse_context.update_current_observation(
                output=result[:2000] if result else None,  # Truncate output
                usage={
                    "input": len(prompt.split()),  # Approximate word count
                    "output": len(result.split()) if result else 0,
                },
            )
            return result

        @wraps(func)
        @observe(as_type="generation")
        def sync_wrapper(prompt: str, *args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_observation(
                model=model,
                input=prompt[:2000],
            )

            result = func(prompt, *args, **kwargs)

            langfuse_context.update_current_observation(
                output=result[:2000] if result else None,
                usage={
                    "input": len(prompt.split()),
                    "output": len(result.split()) if result else 0,
                },
            )
            return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


def trace_tool(tool_name: str):
    """
    Decorator to trace tool/function calls by agents.

    Args:
        tool_name: Name of the tool being used

    Example:
        @trace_tool("web_search")
        async def search_web(query: str) -> list:
            # Tool execution
            return results
    """
    def decorator(func: F) -> F:
        @wraps(func)
        @observe(name=f"tool_{tool_name}")
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_observation(
                metadata={"tool": tool_name},
                input={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
            )

            result = await func(*args, **kwargs)

            langfuse_context.update_current_observation(
                output=str(result)[:1000] if result else None,
            )
            return result

        @wraps(func)
        @observe(name=f"tool_{tool_name}")
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_context.update_current_observation(
                metadata={"tool": tool_name},
                input={"args": str(args)[:500], "kwargs": str(kwargs)[:500]},
            )

            result = func(*args, **kwargs)

            langfuse_context.update_current_observation(
                output=str(result)[:1000] if result else None,
            )
            return result

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


class LangfuseCrewCallback:
    """
    Callback handler for CrewAI that sends events to Langfuse.

    Use this for more fine-grained control over tracing, or when
    you can't use decorators.

    Example:
        callback = LangfuseCrewCallback(session_id="research-123")

        callback.on_agent_start("researcher", "Find information about AI trends")
        callback.on_llm_call(prompt, completion, "qwen2.5:14b", {"input": 100, "output": 50})
        callback.on_agent_end("Found 5 relevant sources")

        callback.on_crew_end("Research complete with summary")
    """

    def __init__(self, session_id: Optional[str] = None, crew_name: str = "crew_execution"):
        self.client = get_client()
        self.session_id = session_id or str(uuid4())
        self.trace = None
        self.current_span = None

        if self.client:
            self.trace = self.client.trace(
                name=crew_name,
                session_id=self.session_id,
            )

    def on_agent_start(self, agent_name: str, task: str) -> None:
        """Called when an agent starts a task."""
        if self.trace:
            self.current_span = self.trace.span(
                name=f"agent_{agent_name}",
                metadata={"task": task[:500]},
            )

    def on_llm_call(
        self,
        prompt: str,
        completion: str,
        model: str,
        tokens: Optional[dict] = None,
    ) -> None:
        """Called for each LLM interaction."""
        if self.current_span:
            self.current_span.generation(
                name="llm_call",
                model=model,
                input=prompt[:2000],
                output=completion[:2000],
                usage={
                    "input": tokens.get("input", 0) if tokens else 0,
                    "output": tokens.get("output", 0) if tokens else 0,
                },
            )

    def on_tool_use(self, tool_name: str, input_data: dict, output: str) -> None:
        """Called when agent uses a tool."""
        if self.current_span:
            self.current_span.span(
                name=f"tool_{tool_name}",
                input=str(input_data)[:500],
                output=output[:1000],
            )

    def on_agent_end(self, result: str) -> None:
        """Called when agent completes task."""
        if self.current_span:
            self.current_span.end(output=result[:2000] if result else None)
            self.current_span = None

    def on_crew_end(self, final_output: str) -> None:
        """Called when crew execution completes."""
        if self.trace:
            self.trace.update(output=final_output[:5000] if final_output else None)
        if self.client:
            self.client.flush()

    def score(self, name: str, value: float, comment: Optional[str] = None) -> None:
        """Add a score to the current trace."""
        if self.client and self.trace:
            self.client.score(
                trace_id=self.trace.id,
                name=name,
                value=value,
                comment=comment,
            )


def flush() -> None:
    """Flush any pending events to Langfuse."""
    client = get_client()
    if client:
        client.flush()


def shutdown() -> None:
    """Shutdown the Langfuse client gracefully."""
    global _langfuse
    if _langfuse:
        _langfuse.flush()
        _langfuse.shutdown()
        _langfuse = None

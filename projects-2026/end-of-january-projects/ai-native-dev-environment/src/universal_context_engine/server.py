"""FastMCP server for Universal Context Engine."""

import subprocess
from datetime import datetime

from fastmcp import FastMCP

from .config import settings
from .context_store import context_store
from .embedding import embedding_client, generate_client
from .logging import with_error_boundary, log_exception, logger
from .models import ContextItem, ContextType, SearchResult

# Initialize FastMCP server
mcp = FastMCP(
    name="Universal Context Engine",
    instructions="Persistent memory and orchestration for AI-native development. "
    "Use save_context to persist information, search_context for retrieval, "
    "and recall_work to summarize recent activity.",
)


def get_git_info() -> tuple[str | None, str | None]:
    """Get current git project path and branch."""
    try:
        # Get git root directory
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        project = result.stdout.strip() if result.returncode == 0 else None

        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = result.stdout.strip() if result.returncode == 0 else None

        return project, branch
    except Exception:
        return None, None


# =============================================================================
# Phase 1: Core Context Tools
# =============================================================================


@mcp.tool()
@with_error_boundary("save_context")
async def save_context(
    content: str,
    context_type: str = "context",
    project: str | None = None,
    metadata: dict | None = None,
) -> dict:
    """Save a context item with semantic embedding for later retrieval.

    Use this to persist important information across sessions:
    - Decisions made during development
    - Patterns established in the codebase
    - Session summaries
    - Blockers encountered

    Args:
        content: The content to save (will be embedded for semantic search)
        context_type: One of: session, decision, pattern, context, blocker, error
        project: Project path (auto-detected from git if not provided)
        metadata: Additional key-value metadata

    Returns:
        The saved context item with its ID
    """
    # Auto-detect project from git if not provided
    if not project:
        project, branch = get_git_info()
    else:
        _, branch = get_git_info()

    # Parse context type
    try:
        ctx_type = ContextType(context_type)
    except ValueError:
        ctx_type = ContextType.CONTEXT

    item = await context_store.save(
        content=content,
        context_type=ctx_type,
        project=project,
        branch=branch,
        metadata=metadata,
    )

    return {
        "id": item.id,
        "content": item.content[:200] + "..." if len(item.content) > 200 else item.content,
        "type": item.context_type.value,
        "project": item.project,
        "branch": item.branch,
        "timestamp": item.timestamp.isoformat(),
    }


@mcp.tool()
@with_error_boundary("search_context")
async def search_context(
    query: str,
    type_filter: str | None = None,
    project: str | None = None,
    limit: int = 5,
) -> list[dict]:
    """Search for context items using semantic similarity.

    Find relevant past context, decisions, patterns, or session notes
    based on meaning rather than exact keyword matching.

    Args:
        query: Natural language search query
        type_filter: Filter by type: session, decision, pattern, context, blocker, error
        project: Filter by project path (auto-detected if not provided)
        limit: Maximum number of results (default 5)

    Returns:
        List of matching context items with relevance scores
    """
    # Auto-detect project if not provided
    if project is None:
        project, _ = get_git_info()

    # Parse type filter
    ctx_type = None
    if type_filter:
        try:
            ctx_type = ContextType(type_filter)
        except ValueError:
            pass

    results = await context_store.search(
        query=query,
        context_type=ctx_type,
        project=project,
        limit=limit,
    )

    return [
        {
            "id": r.item.id,
            "content": r.item.content[:300] + "..." if len(r.item.content) > 300 else r.item.content,
            "type": r.item.context_type.value,
            "project": r.item.project,
            "score": round(r.score, 3),
            "timestamp": r.item.timestamp.isoformat(),
        }
        for r in results
    ]


@mcp.tool()
@with_error_boundary("get_recent")
async def get_recent(
    project: str | None = None,
    hours: int = 24,
    type_filter: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Get recent context items from the last N hours.

    Useful for reviewing what was done recently without
    needing a specific search query.

    Args:
        project: Filter by project (auto-detected if not provided)
        hours: Look back this many hours (default 24)
        type_filter: Filter by type: session, decision, pattern, context, blocker, error
        limit: Maximum number of results (default 10)

    Returns:
        List of recent context items sorted by timestamp
    """
    # Auto-detect project if not provided
    if project is None:
        project, _ = get_git_info()

    # Parse type filter
    ctx_type = None
    if type_filter:
        try:
            ctx_type = ContextType(type_filter)
        except ValueError:
            pass

    items = await context_store.get_recent(
        project=project,
        hours=hours,
        context_type=ctx_type,
        limit=limit,
    )

    return [
        {
            "id": item.id,
            "content": item.content[:300] + "..." if len(item.content) > 300 else item.content,
            "type": item.context_type.value,
            "project": item.project,
            "branch": item.branch,
            "timestamp": item.timestamp.isoformat(),
        }
        for item in items
    ]


@mcp.tool()
@with_error_boundary("recall_work")
async def recall_work(project: str | None = None) -> dict:
    """Recall what you were working on - summarizes recent context.

    Use this at the start of a session to quickly understand:
    - What was done in recent sessions
    - Decisions that were made
    - Any blockers or errors encountered
    - Patterns that were established

    Args:
        project: Project to recall (auto-detected if not provided)

    Returns:
        Summary of recent work including sessions, decisions, and blockers
    """
    # Auto-detect project if not provided
    if project is None:
        project, branch = get_git_info()
    else:
        _, branch = get_git_info()

    # Get recent items of each type
    sessions = await context_store.get_recent(
        project=project, hours=72, context_type=ContextType.SESSION, limit=5
    )
    decisions = await context_store.get_recent(
        project=project, hours=168, context_type=ContextType.DECISION, limit=5
    )
    blockers = await context_store.get_recent(
        project=project, hours=168, context_type=ContextType.BLOCKER, limit=5
    )
    errors = await context_store.get_recent(
        project=project, hours=48, context_type=ContextType.ERROR, limit=3
    )

    # Get stats
    stats = await context_store.get_stats()

    # Build summary
    summary_parts = []

    if sessions:
        summary_parts.append("**Recent Sessions:**")
        for s in sessions[:3]:
            summary_parts.append(f"- {s.timestamp.strftime('%Y-%m-%d %H:%M')}: {s.content[:150]}...")

    if decisions:
        summary_parts.append("\n**Recent Decisions:**")
        for d in decisions[:3]:
            summary_parts.append(f"- {d.content[:150]}...")

    if blockers:
        summary_parts.append("\n**Active Blockers:**")
        for b in blockers:
            summary_parts.append(f"- {b.content[:150]}...")

    if errors:
        summary_parts.append("\n**Recent Errors:**")
        for e in errors[:2]:
            summary_parts.append(f"- {e.content[:100]}...")

    if not summary_parts:
        summary_parts.append("No recent context found for this project.")
        summary_parts.append("Start saving context with `save_context` to build your memory.")

    return {
        "project": project,
        "branch": branch,
        "summary": "\n".join(summary_parts),
        "stats": stats,
        "total_items": sum(stats.values()),
    }


@mcp.tool()
@with_error_boundary("context_stats")
async def context_stats() -> dict:
    """Get statistics about stored context.

    Returns counts of items by type and total storage info.

    Returns:
        Dictionary with context statistics
    """
    stats = await context_store.get_stats()
    return {
        "items_by_type": stats,
        "total_items": sum(stats.values()),
        "storage_path": str(settings.chromadb_path),
    }


# =============================================================================
# Phase 2: Session Lifecycle Management
# =============================================================================

from .session import session_manager


@mcp.tool()
@with_error_boundary("start_session")
async def start_session(project: str | None = None) -> dict:
    """Start a new development session with context loading.

    Call this at the beginning of a work session to:
    - Initialize session tracking
    - Load recent context from previous sessions
    - See any active blockers

    Args:
        project: Optional project path override (auto-detected from git)

    Returns:
        Session info with recent context loaded
    """
    return await session_manager.start_session(project=project)


@mcp.tool()
@with_error_boundary("end_session")
async def end_session(
    conversation_excerpt: str = "",
    files_modified: list[str] | None = None,
) -> dict:
    """End the current session with automatic summarization.

    Call this at the end of a work session to:
    - Generate a summary using local LLM
    - Extract and save key decisions
    - Persist session context for future recall

    Args:
        conversation_excerpt: Key points or summary of what was done
        files_modified: List of files that were modified

    Returns:
        Session summary with extracted decisions
    """
    return await session_manager.end_session(
        conversation_excerpt=conversation_excerpt,
        files_modified=files_modified,
    )


@mcp.tool()
@with_error_boundary("capture_decision")
async def capture_decision(
    decision: str,
    category: str | None = None,
    rationale: str | None = None,
) -> dict:
    """Capture an architectural or technical decision.

    Use this to record important decisions for future reference:
    - API design choices
    - Database schema decisions
    - Architecture patterns adopted
    - Technology selections

    Args:
        decision: The decision that was made
        category: Category like "architecture", "api", "database", "security"
        rationale: Why this decision was made

    Returns:
        Saved decision info
    """
    return await session_manager.capture_decision(
        decision=decision,
        category=category,
        rationale=rationale,
    )


@mcp.tool()
@with_error_boundary("capture_blocker")
async def capture_blocker(
    description: str,
    severity: str = "medium",
    context: str | None = None,
) -> dict:
    """Record a blocker or issue for follow-up.

    Use this to track issues that need attention:
    - Technical blockers
    - Dependencies on others
    - Unanswered questions
    - Issues to investigate later

    Args:
        description: What the blocker is
        severity: "low", "medium", or "high"
        context: Additional context about the blocker

    Returns:
        Saved blocker info
    """
    return await session_manager.capture_blocker(
        description=description,
        severity=severity,
        context=context,
    )


@mcp.tool()
@with_error_boundary("get_blockers")
async def get_blockers(
    project: str | None = None,
    include_resolved: bool = False,
) -> list[dict]:
    """Get active blockers that need attention.

    Review blockers from the past week to see what needs follow-up.

    Args:
        project: Filter by project (auto-detected if not provided)
        include_resolved: Whether to include resolved blockers

    Returns:
        List of blockers with severity and status
    """
    return await session_manager.get_blockers(
        project=project,
        include_resolved=include_resolved,
    )


# =============================================================================
# Phase 3: KAS + LocalCrew Integration
# =============================================================================

from .adapters import kas_adapter, localcrew_adapter
from .embedding import embedding_client


@mcp.tool()
@with_error_boundary("unified_search")
async def unified_search(
    query: str,
    sources: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """Search across context store and KAS knowledge base.

    Combines results from local context (sessions, decisions, patterns)
    with the KAS knowledge base for comprehensive search.

    Args:
        query: Natural language search query
        sources: Which sources to search: "context", "kas", or both (default)
        limit: Maximum total results

    Returns:
        Merged and deduplicated results from all sources
    """
    sources = sources or ["context", "kas"]
    results = []

    # Search local context
    if "context" in sources:
        context_results = await context_store.search(
            query=query,
            limit=limit,
        )
        for r in context_results:
            results.append({
                "source": "context",
                "id": r.item.id,
                "title": r.item.context_type.value,
                "content": r.item.content[:300] + "..." if len(r.item.content) > 300 else r.item.content,
                "score": r.score,
                "timestamp": r.item.timestamp.isoformat(),
            })

    # Search KAS
    if "kas" in sources:
        kas_results = await kas_adapter.search(query=query, limit=limit)
        for r in kas_results:
            results.append({
                "source": "kas",
                "id": r.id,
                "title": r.title,
                "content": r.content[:300] + "..." if len(r.content) > 300 else r.content,
                "score": r.score,
                "tags": r.tags,
            })

    # Sort by score and limit
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:limit]


@mcp.tool()
@with_error_boundary("research")
async def research(
    topic: str,
    depth: str = "medium",
    context: str | None = None,
) -> dict:
    """Trigger LocalCrew research crew for a topic.

    Uses the LocalCrew research crew to gather comprehensive
    information about a topic using multiple AI agents.

    Args:
        topic: What to research
        depth: "quick", "medium", or "deep"
        context: Optional additional context

    Returns:
        Research results from the crew
    """
    result = await localcrew_adapter.research(
        topic=topic,
        depth=depth,
        context=context,
    )

    return {
        "topic": topic,
        "depth": depth,
        "result": result,
    }


@mcp.tool()
@with_error_boundary("decompose_task")
async def decompose_task(
    task: str,
    context: str | None = None,
) -> dict:
    """Break down a task into subtasks using LocalCrew.

    Uses AI agents to analyze a task and break it into
    manageable, actionable subtasks with dependencies.

    Args:
        task: The task to decompose
        context: Optional additional context

    Returns:
        List of subtasks with priorities and dependencies
    """
    subtasks = await localcrew_adapter.decompose(
        task=task,
        context=context,
    )

    return {
        "task": task,
        "subtasks": [
            {
                "id": s.id,
                "description": s.description,
                "priority": s.priority,
                "dependencies": s.dependencies,
                "complexity": s.estimated_complexity,
            }
            for s in subtasks
        ],
        "count": len(subtasks),
    }


@mcp.tool()
@with_error_boundary("ingest_to_kas")
async def ingest_to_kas(
    content: str,
    title: str,
    tags: list[str] | None = None,
) -> dict:
    """Add content to the KAS knowledge base.

    Ingests content into KAS for future retrieval.
    Useful for saving research results, documentation,
    or other knowledge for long-term storage.

    Args:
        content: The content to ingest
        title: A title for the content
        tags: Optional tags for categorization

    Returns:
        ID of the ingested item
    """
    try:
        item_id = await kas_adapter.ingest(
            content=content,
            title=title,
            tags=tags,
            source="universal-context-engine",
        )
        return {
            "success": True,
            "id": item_id,
            "title": title,
            "tags": tags or [],
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
@with_error_boundary("service_status")
async def service_status() -> dict:
    """Check health of all connected services.

    Returns the status of:
    - Ollama (embedding/generation)
    - KAS (knowledge base)
    - LocalCrew (AI crews)
    - Redis (session cache)

    Returns:
        Health status of each service
    """
    import redis.asyncio as aioredis

    services = {}

    # Check Ollama
    try:
        ollama_ok = await embedding_client.health_check()
        services["ollama"] = {
            "status": "healthy" if ollama_ok else "unhealthy",
            "url": settings.ollama_base_url,
        }
    except Exception as e:
        services["ollama"] = {"status": "unhealthy", "error": str(e)}

    # Check KAS
    kas_health = await kas_adapter.health()
    services["kas"] = {
        "status": kas_health["status"],
        "url": settings.kas_base_url,
        **({} if kas_health["status"] == "healthy" else {"error": kas_health.get("error")}),
    }

    # Check LocalCrew
    localcrew_health = await localcrew_adapter.health()
    services["localcrew"] = {
        "status": localcrew_health["status"],
        "url": settings.localcrew_base_url,
        **({} if localcrew_health["status"] == "healthy" else {"error": localcrew_health.get("error")}),
    }

    # Check Redis
    try:
        redis_client = aioredis.from_url(settings.redis_url)
        await redis_client.ping()
        services["redis"] = {"status": "healthy", "url": settings.redis_url}
        await redis_client.aclose()
    except Exception as e:
        services["redis"] = {"status": "unhealthy", "url": settings.redis_url, "error": str(e)}

    # Overall status
    all_healthy = all(s["status"] == "healthy" for s in services.values())

    return {
        "overall": "healthy" if all_healthy else "degraded",
        "services": services,
    }


# =============================================================================
# Phase 4: Intent Router
# =============================================================================

from .router import classify_intent, handle_intent


@mcp.tool()
@with_error_boundary("smart_request")
async def smart_request(request: str) -> dict:
    """Automatically route a natural language request.

    Analyzes the request and routes it to the appropriate handler:
    - "Research how GraphRAG works" → Research crew
    - "What was I working on yesterday?" → Session recall
    - "Search for authentication docs" → Unified search
    - "Break down the login feature" → Task decomposition
    - "Fix this error" → Debug assistance

    Args:
        request: Natural language request

    Returns:
        Result from the appropriate handler
    """
    # Classify the intent
    intent = await classify_intent(request)

    # Handle the intent
    result = await handle_intent(intent)

    return {
        "request": request,
        "classified_as": intent.type.value,
        "confidence": intent.confidence,
        **result,
    }


@mcp.tool()
@with_error_boundary("explain_routing")
async def explain_routing(request: str) -> dict:
    """Explain how a request would be routed without executing it.

    Useful for understanding the routing logic before committing
    to an action.

    Args:
        request: Natural language request to analyze

    Returns:
        Explanation of how the request would be handled
    """
    # Classify the intent
    intent = await classify_intent(request)

    intent_descriptions = {
        "research": "Route to LocalCrew research crew for deep topic exploration",
        "recall": "Search recent session context to understand previous work",
        "knowledge": "Search both local context and KAS knowledge base",
        "decompose": "Use LocalCrew to break task into subtasks",
        "debug": "Search error history and provide debugging assistance",
        "save": "Save content to persistent context store",
        "unknown": "Intent unclear - may need more specific phrasing",
    }

    return {
        "request": request,
        "intent": intent.type.value,
        "confidence": intent.confidence,
        "extracted_topic": intent.extracted_topic,
        "reasoning": intent.reasoning,
        "would_do": intent_descriptions.get(intent.type.value, "Unknown action"),
        "suggestion": "Use `smart_request` to execute this routing",
    }


# =============================================================================
# Phase 5: Feedback & Quality Tracking
# =============================================================================

from .feedback import feedback_tracker, get_metrics, export_training_data as _export_training_data


@mcp.tool()
@with_error_boundary("feedback_helpful")
async def feedback_helpful(interaction_id: str | None = None) -> dict:
    """Mark the last interaction (or a specific one) as helpful.

    Provide feedback to help improve the system over time.
    Helpful interactions may be used for optimization.

    Args:
        interaction_id: Optional ID of specific interaction, or None for last

    Returns:
        Confirmation of feedback recorded
    """
    success = feedback_tracker.mark_helpful(interaction_id)
    return {
        "success": success,
        "feedback": "helpful",
        "message": "Feedback recorded. Thank you!" if success else "Could not record feedback.",
    }


@mcp.tool()
@with_error_boundary("feedback_not_helpful")
async def feedback_not_helpful(
    interaction_id: str | None = None,
    reason: str | None = None,
) -> dict:
    """Mark the last interaction (or a specific one) as not helpful.

    Provide feedback with an optional reason to help improve the system.

    Args:
        interaction_id: Optional ID of specific interaction, or None for last
        reason: Optional reason why it wasn't helpful

    Returns:
        Confirmation of feedback recorded
    """
    success = feedback_tracker.mark_not_helpful(interaction_id, reason)
    return {
        "success": success,
        "feedback": "not_helpful",
        "reason": reason,
        "message": "Feedback recorded. We'll work to improve." if success else "Could not record feedback.",
    }


@mcp.tool()
@with_error_boundary("quality_stats")
async def quality_stats() -> dict:
    """Get quality metrics and feedback statistics.

    View overall system performance including:
    - Success rates
    - Average latency
    - Feedback rates
    - Per-tool breakdown

    Returns:
        Quality metrics dictionary
    """
    metrics = get_metrics()
    return {
        "total_interactions": metrics.total_interactions,
        "feedback": {
            "helpful": metrics.helpful_count,
            "not_helpful": metrics.not_helpful_count,
            "rate": round(metrics.feedback_rate * 100, 1),
            "helpful_rate": round(metrics.helpful_rate * 100, 1),
        },
        "performance": {
            "avg_latency_ms": round(metrics.avg_latency_ms, 1),
            "error_rate": round(metrics.error_rate * 100, 1),
        },
        "by_tool": metrics.by_tool or {},
    }


@mcp.tool()
@with_error_boundary("export_feedback_data")
async def export_feedback_data(
    tool: str | None = None,
    min_examples: int = 10,
) -> dict:
    """Export training data from helpful interactions.

    Exports input/output pairs for DSPy optimization or analysis.
    Only includes interactions that were marked as helpful.

    Args:
        tool: Filter by specific tool, or None for all
        min_examples: Minimum examples required (default 10)

    Returns:
        Export result with path or data
    """
    result = _export_training_data(
        tool=tool,
        min_examples=min_examples,
        only_helpful=True,
    )
    return result


# =============================================================================
# Phase 7: Data Hygiene Tools
# =============================================================================

from .context_store import run_retention_cleanup


@mcp.tool()
@with_error_boundary("retention_cleanup")
async def retention_cleanup() -> dict:
    """Run data retention cleanup based on configured policies.

    Removes context items and feedback older than the retention periods
    configured in settings:
    - context_retention_days (default: 90)
    - feedback_retention_days (default: 180)
    - session_retention_days (default: 30)

    Set UCE_PRODUCTION_MODE=true to enable production safeguards.

    Returns:
        Summary of deleted items by category
    """
    from .config import settings

    result = await run_retention_cleanup()
    return {
        "deleted": result,
        "retention_policy": {
            "context_days": settings.context_retention_days,
            "feedback_days": settings.feedback_retention_days,
            "session_days": settings.session_retention_days,
        },
        "production_mode": settings.production_mode,
    }


# =============================================================================
# Server Entry Point
# =============================================================================


async def cleanup_resources():
    """Clean up HTTP clients and resources on shutdown."""
    from .context_store import cleanup_executor

    # Close HTTP clients
    await embedding_client.close()
    await generate_client.close()
    await kas_adapter.close()
    await localcrew_adapter.close()

    # Shutdown executor
    await cleanup_executor()

    logger.info("Resources cleaned up successfully")


def main():
    """Run the MCP server."""
    import atexit
    import asyncio

    # Register cleanup handler
    def sync_cleanup():
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(cleanup_resources())
            loop.close()
        except Exception as e:
            # Best effort cleanup, don't crash on exit
            pass

    atexit.register(sync_cleanup)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

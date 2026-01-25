"""Intent handlers for executing classified intents."""

from typing import Any

from ..adapters import kas_adapter, localcrew_adapter
from ..context_store import context_store
from ..models import ContextType
from ..session import session_manager
from .classifier import Intent, IntentType


class IntentHandler:
    """Handles execution of classified intents."""

    async def handle_research(self, intent: Intent) -> dict[str, Any]:
        """Handle research intent."""
        topic = intent.extracted_topic or "general topic"
        depth = "medium"

        # Determine depth from params if available
        if intent.extracted_params:
            depth = intent.extracted_params.get("depth", "medium")

        result = await localcrew_adapter.research(
            topic=topic,
            depth=depth,
        )

        return {
            "intent": "research",
            "topic": topic,
            "depth": depth,
            "result": result,
        }

    async def handle_recall(self, intent: Intent) -> dict[str, Any]:
        """Handle recall intent (what was I working on?)."""
        # Get recent context
        sessions = await context_store.get_recent(
            hours=72,
            context_type=ContextType.SESSION,
            limit=5,
        )
        decisions = await context_store.get_recent(
            hours=168,
            context_type=ContextType.DECISION,
            limit=5,
        )
        blockers = await context_store.get_recent(
            hours=168,
            context_type=ContextType.BLOCKER,
            limit=5,
        )

        summary_parts = []
        if sessions:
            summary_parts.append("**Recent Sessions:**")
            for s in sessions[:3]:
                summary_parts.append(f"- {s.timestamp.strftime('%Y-%m-%d %H:%M')}: {s.content[:150]}...")

        if decisions:
            summary_parts.append("\n**Decisions Made:**")
            for d in decisions[:3]:
                summary_parts.append(f"- {d.content[:150]}...")

        if blockers:
            summary_parts.append("\n**Active Blockers:**")
            for b in blockers:
                summary_parts.append(f"- {b.content[:150]}...")

        return {
            "intent": "recall",
            "summary": "\n".join(summary_parts) if summary_parts else "No recent activity found.",
            "sessions_count": len(sessions),
            "decisions_count": len(decisions),
            "blockers_count": len(blockers),
        }

    async def handle_knowledge(self, intent: Intent) -> dict[str, Any]:
        """Handle knowledge search intent."""
        query = intent.extracted_topic or ""
        if not query:
            return {
                "intent": "knowledge",
                "error": "No search query provided",
            }

        # Search both context and KAS
        context_results = await context_store.search(query=query, limit=5)
        kas_results = await kas_adapter.search(query=query, limit=5)

        results = []
        for r in context_results:
            results.append({
                "source": "context",
                "content": r.item.content[:200],
                "score": r.score,
            })
        for r in kas_results:
            results.append({
                "source": "kas",
                "title": r.title,
                "content": r.content[:200],
                "score": r.score,
            })

        # Sort by score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return {
            "intent": "knowledge",
            "query": query,
            "results": results[:10],
            "total": len(results),
        }

    async def handle_decompose(self, intent: Intent) -> dict[str, Any]:
        """Handle task decomposition intent."""
        task = intent.extracted_topic or ""
        if not task:
            return {
                "intent": "decompose",
                "error": "No task provided to decompose",
            }

        subtasks = await localcrew_adapter.decompose(task=task)

        return {
            "intent": "decompose",
            "task": task,
            "subtasks": [
                {
                    "id": s.id,
                    "description": s.description,
                    "priority": s.priority,
                    "dependencies": s.dependencies,
                }
                for s in subtasks
            ],
            "count": len(subtasks),
        }

    async def handle_debug(self, intent: Intent) -> dict[str, Any]:
        """Handle debug intent (error analysis)."""
        error_context = intent.extracted_topic or ""

        # Search for similar errors in context
        if error_context:
            similar_errors = await context_store.search(
                query=error_context,
                context_type=ContextType.ERROR,
                limit=5,
            )
        else:
            similar_errors = []

        # Get recent errors
        recent_errors = await context_store.get_recent(
            hours=48,
            context_type=ContextType.ERROR,
            limit=5,
        )

        return {
            "intent": "debug",
            "context": error_context,
            "similar_errors": [
                {"content": e.item.content[:200], "score": e.score}
                for e in similar_errors
            ],
            "recent_errors": [
                {"content": e.content[:200], "timestamp": e.timestamp.isoformat()}
                for e in recent_errors
            ],
            "suggestion": "Consider saving the error with `save_context` for future reference.",
        }

    async def handle_save(self, intent: Intent) -> dict[str, Any]:
        """Handle save intent."""
        content = intent.extracted_topic or ""
        if not content:
            return {
                "intent": "save",
                "error": "No content provided to save",
            }

        item = await context_store.save(
            content=content,
            context_type=ContextType.CONTEXT,
        )

        return {
            "intent": "save",
            "saved": True,
            "id": item.id,
            "content_preview": content[:100],
        }

    async def handle(self, intent: Intent) -> dict[str, Any]:
        """Route intent to appropriate handler.

        Args:
            intent: The classified intent.

        Returns:
            Handler result.
        """
        handlers = {
            IntentType.RESEARCH: self.handle_research,
            IntentType.RECALL: self.handle_recall,
            IntentType.KNOWLEDGE: self.handle_knowledge,
            IntentType.DECOMPOSE: self.handle_decompose,
            IntentType.DEBUG: self.handle_debug,
            IntentType.SAVE: self.handle_save,
        }

        handler = handlers.get(intent.type)
        if handler:
            result = await handler(intent)
            result["confidence"] = intent.confidence
            result["reasoning"] = intent.reasoning
            return result

        return {
            "intent": "unknown",
            "original_text": intent.extracted_topic,
            "confidence": intent.confidence,
            "suggestion": "Try being more specific or use one of the direct tools.",
        }


# Default handler instance
_handler = IntentHandler()


async def handle_intent(intent: Intent) -> dict[str, Any]:
    """Execute the appropriate handler for an intent.

    Args:
        intent: The classified intent to handle.

    Returns:
        Handler result dictionary.
    """
    return await _handler.handle(intent)

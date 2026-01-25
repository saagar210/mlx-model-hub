"""Interaction tracking for quality feedback."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import chromadb
from chromadb.config import Settings as ChromaSettings

from ..config import settings
from ..logging import logger


@dataclass
class InteractionLog:
    """Log entry for a tool interaction."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tool: str = ""
    input_params: dict[str, Any] = field(default_factory=dict)
    output: str = ""
    latency_ms: int = 0
    error: str | None = None
    user_feedback: Literal["helpful", "not_helpful"] | None = None
    feedback_reason: str | None = None


class FeedbackTracker:
    """Tracks interactions and feedback for quality monitoring."""

    def __init__(self, persist_directory: str | None = None):
        self._persist_dir = persist_directory or str(settings.chromadb_path)
        self._client: chromadb.PersistentClient | None = None
        self._collection: chromadb.Collection | None = None
        self._last_interaction_id: str | None = None

    def _ensure_client(self) -> chromadb.Collection:
        """Lazily initialize the ChromaDB client and collection."""
        if self._collection is None:
            settings.ensure_directories()

            # In production mode, disable allow_reset
            allow_reset = not settings.production_mode
            if settings.production_mode:
                logger.info("FeedbackTracker: Production mode, reset disabled")

            self._client = chromadb.PersistentClient(
                path=self._persist_dir,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=allow_reset,
                ),
            )
            self._collection = self._client.get_or_create_collection(
                name="uce_feedback",
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def log_interaction(
        self,
        tool: str,
        input_params: dict[str, Any],
        output: Any,
        latency_ms: int,
        error: str | None = None,
    ) -> str:
        """Log an interaction.

        Args:
            tool: Name of the tool called.
            input_params: Input parameters to the tool.
            output: Output from the tool.
            latency_ms: Execution time in milliseconds.
            error: Error message if any.

        Returns:
            ID of the logged interaction.
        """
        log = InteractionLog(
            tool=tool,
            input_params=input_params,
            output=str(output)[:2000],  # Truncate long outputs
            latency_ms=latency_ms,
            error=error,
        )

        # Store in ChromaDB
        # Create a simple embedding based on tool and params
        content = f"{tool}: {str(input_params)[:500]}"
        collection = self._ensure_client()

        collection.add(
            ids=[log.id],
            documents=[content],
            metadatas=[{
                "tool": log.tool,
                "timestamp": log.timestamp.isoformat(),
                "latency_ms": log.latency_ms,
                "has_error": error is not None,
                "output_preview": log.output[:200],
            }],
        )

        self._last_interaction_id = log.id
        return log.id

    def mark_helpful(self, interaction_id: str | None = None) -> bool:
        """Mark an interaction as helpful.

        Args:
            interaction_id: ID of interaction, or None for last interaction.

        Returns:
            True if updated successfully.
        """
        target_id = interaction_id or self._last_interaction_id
        if not target_id:
            return False

        try:
            collection = self._ensure_client()
            # Get existing metadata
            result = collection.get(ids=[target_id], include=["metadatas"])
            if not result["ids"]:
                return False

            metadata = result["metadatas"][0] if result["metadatas"] else {}
            metadata["feedback"] = "helpful"
            metadata["feedback_timestamp"] = datetime.now(UTC).isoformat()

            collection.update(
                ids=[target_id],
                metadatas=[metadata],
            )
            return True
        except Exception:
            return False

    def mark_not_helpful(
        self,
        interaction_id: str | None = None,
        reason: str | None = None,
    ) -> bool:
        """Mark an interaction as not helpful.

        Args:
            interaction_id: ID of interaction, or None for last interaction.
            reason: Optional reason for negative feedback.

        Returns:
            True if updated successfully.
        """
        target_id = interaction_id or self._last_interaction_id
        if not target_id:
            return False

        try:
            collection = self._ensure_client()
            # Get existing metadata
            result = collection.get(ids=[target_id], include=["metadatas"])
            if not result["ids"]:
                return False

            metadata = result["metadatas"][0] if result["metadatas"] else {}
            metadata["feedback"] = "not_helpful"
            metadata["feedback_reason"] = reason or ""
            metadata["feedback_timestamp"] = datetime.now(UTC).isoformat()

            collection.update(
                ids=[target_id],
                metadatas=[metadata],
            )
            return True
        except Exception:
            return False

    def get_interactions(
        self,
        tool: str | None = None,
        feedback_filter: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get logged interactions.

        Args:
            tool: Filter by tool name.
            feedback_filter: Filter by feedback ("helpful", "not_helpful", None for all).
            limit: Maximum number of results.

        Returns:
            List of interaction dictionaries.
        """
        # Build where clause
        where = {}
        if tool:
            where["tool"] = tool
        if feedback_filter:
            where["feedback"] = feedback_filter

        try:
            collection = self._ensure_client()
            results = collection.get(
                where=where if where else None,
                limit=limit,
                include=["metadatas", "documents"],
            )

            interactions = []
            if results["ids"]:
                for i, id_ in enumerate(results["ids"]):
                    meta = results["metadatas"][i] if results["metadatas"] else {}
                    doc = results["documents"][i] if results["documents"] else ""
                    interactions.append({
                        "id": id_,
                        "content": doc,
                        **meta,
                    })

            return interactions
        except Exception:
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get overall feedback statistics.

        Returns:
            Dictionary with feedback stats.
        """
        try:
            collection = self._ensure_client()
            total = collection.count()

            # Get helpful count
            helpful = collection.get(
                where={"feedback": "helpful"},
                include=[],
            )
            helpful_count = len(helpful["ids"]) if helpful["ids"] else 0

            # Get not helpful count
            not_helpful = collection.get(
                where={"feedback": "not_helpful"},
                include=[],
            )
            not_helpful_count = len(not_helpful["ids"]) if not_helpful["ids"] else 0

            # Get by tool
            all_interactions = collection.get(include=["metadatas"])
            tool_counts: dict[str, int] = {}
            total_latency = 0
            latency_count = 0

            if all_interactions["metadatas"]:
                for meta in all_interactions["metadatas"]:
                    tool = meta.get("tool", "unknown")
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1
                    if "latency_ms" in meta:
                        total_latency += meta["latency_ms"]
                        latency_count += 1

            return {
                "total_interactions": total,
                "helpful": helpful_count,
                "not_helpful": not_helpful_count,
                "no_feedback": total - helpful_count - not_helpful_count,
                "feedback_rate": (helpful_count + not_helpful_count) / total if total > 0 else 0,
                "helpful_rate": helpful_count / (helpful_count + not_helpful_count) if (helpful_count + not_helpful_count) > 0 else 0,
                "avg_latency_ms": total_latency / latency_count if latency_count > 0 else 0,
                "by_tool": tool_counts,
            }
        except Exception as e:
            return {"error": str(e)}


# Default tracker instance
feedback_tracker = FeedbackTracker()


def log_interaction(
    tool: str,
    input_params: dict[str, Any],
    output: Any,
    latency_ms: int,
    error: str | None = None,
) -> str:
    """Log an interaction using the default tracker.

    Args:
        tool: Name of the tool called.
        input_params: Input parameters to the tool.
        output: Output from the tool.
        latency_ms: Execution time in milliseconds.
        error: Error message if any.

    Returns:
        ID of the logged interaction.
    """
    return feedback_tracker.log_interaction(
        tool=tool,
        input_params=input_params,
        output=output,
        latency_ms=latency_ms,
        error=error,
    )

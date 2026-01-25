"""Session management for Universal Context Engine."""

import subprocess
import uuid
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis

from .config import settings
from .context_store import context_store
from .models import ContextType, SessionCapture, SessionSummary
from .summarizer import extract_decisions, summarize_session


class SessionManager:
    """Manages development session lifecycle."""

    def __init__(self):
        self._redis: redis.Redis | None = None
        self._current_session_id: str | None = None

    async def _get_redis(self) -> redis.Redis | None:
        """Get or create Redis connection (returns None if unavailable)."""
        if self._redis is None:
            try:
                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception:
                self._redis = None
        return self._redis

    def _get_git_info(self) -> tuple[str | None, str | None]:
        """Get current git project path and branch."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            project = result.stdout.strip() if result.returncode == 0 else None

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

    async def start_session(self, project: str | None = None) -> dict[str, Any]:
        """Start a new development session.

        Args:
            project: Optional project path override.

        Returns:
            Session info including recent context.
        """
        session_id = str(uuid.uuid4())[:8]
        self._current_session_id = session_id

        # Get git info
        git_project, git_branch = self._get_git_info()
        project = project or git_project

        # Try to store session in Redis
        redis_client = await self._get_redis()
        if redis_client:
            try:
                await redis_client.hset(
                    f"session:{session_id}",
                    mapping={
                        "project": project or "",
                        "branch": git_branch or "",
                        "started": datetime.now(UTC).isoformat(),
                    },
                )
                await redis_client.expire(f"session:{session_id}", 86400)  # 24 hours
            except Exception:
                pass  # Redis is optional

        # Load recent context for this project
        recent_sessions = await context_store.get_recent(
            project=project,
            hours=72,
            context_type=ContextType.SESSION,
            limit=3,
        )
        recent_decisions = await context_store.get_recent(
            project=project,
            hours=168,
            context_type=ContextType.DECISION,
            limit=5,
        )
        active_blockers = await context_store.get_recent(
            project=project,
            hours=168,
            context_type=ContextType.BLOCKER,
            limit=5,
        )

        return {
            "session_id": session_id,
            "project": project,
            "branch": git_branch,
            "started": datetime.now(UTC).isoformat(),
            "recent_context": {
                "sessions": [
                    {"timestamp": s.timestamp.isoformat(), "content": s.content[:200]}
                    for s in recent_sessions
                ],
                "decisions": [
                    {"timestamp": d.timestamp.isoformat(), "content": d.content[:200]}
                    for d in recent_decisions
                ],
                "blockers": [
                    {"timestamp": b.timestamp.isoformat(), "content": b.content[:200]}
                    for b in active_blockers
                ],
            },
        }

    async def end_session(
        self,
        conversation_excerpt: str = "",
        files_modified: list[str] | None = None,
    ) -> dict[str, Any]:
        """End the current session, summarize, and save.

        Args:
            conversation_excerpt: Summary or excerpt of the conversation.
            files_modified: List of files modified during the session.

        Returns:
            Session summary.
        """
        session_id = self._current_session_id or str(uuid.uuid4())[:8]
        git_project, git_branch = self._get_git_info()

        # Try to get session data from Redis
        session_data: dict[str, str] = {}
        redis_client = await self._get_redis()
        if redis_client:
            try:
                session_data = await redis_client.hgetall(f"session:{session_id}") or {}
                await redis_client.delete(f"session:{session_id}")
            except Exception:
                pass

        project = session_data.get("project") or git_project
        branch = session_data.get("branch") or git_branch

        # Extract decisions from conversation
        decisions = await extract_decisions(conversation_excerpt) if conversation_excerpt else []

        # Create session capture
        capture = SessionCapture(
            session_id=session_id,
            project_path=project,
            git_branch=branch,
            files_modified=files_modified or [],
            conversation_excerpt=conversation_excerpt,
            key_decisions=decisions,
            errors_encountered=[],
            timestamp=datetime.now(UTC),
        )

        # Generate summary using LLM
        summary_text = await summarize_session(capture)

        # Save session to context store
        await context_store.save(
            content=summary_text,
            context_type=ContextType.SESSION,
            project=project,
            branch=branch,
            metadata={
                "session_id": session_id,
                "files_count": len(files_modified or []),
                "decisions_count": len(decisions),
            },
        )

        # Save any extracted decisions
        for decision in decisions:
            await context_store.save(
                content=decision,
                context_type=ContextType.DECISION,
                project=project,
                branch=branch,
                metadata={"session_id": session_id},
            )

        self._current_session_id = None

        return {
            "session_id": session_id,
            "summary": summary_text,
            "project": project,
            "branch": branch,
            "files_modified": len(files_modified or []),
            "decisions_extracted": len(decisions),
            "decisions": decisions,
        }

    async def capture_decision(
        self,
        decision: str,
        category: str | None = None,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        """Capture an architectural or technical decision.

        Args:
            decision: The decision that was made.
            category: Optional category (e.g., "architecture", "api", "database").
            rationale: Optional explanation of why this decision was made.

        Returns:
            Saved decision info.
        """
        git_project, git_branch = self._get_git_info()

        content = decision
        if rationale:
            content = f"{decision}\n\nRationale: {rationale}"

        metadata: dict[str, Any] = {}
        if category:
            metadata["category"] = category
        if self._current_session_id:
            metadata["session_id"] = self._current_session_id

        item = await context_store.save(
            content=content,
            context_type=ContextType.DECISION,
            project=git_project,
            branch=git_branch,
            metadata=metadata,
        )

        return {
            "id": item.id,
            "decision": decision,
            "category": category,
            "project": git_project,
            "branch": git_branch,
            "timestamp": item.timestamp.isoformat(),
        }

    async def capture_blocker(
        self,
        description: str,
        severity: str = "medium",
        context: str | None = None,
    ) -> dict[str, Any]:
        """Capture a blocker or issue encountered.

        Args:
            description: Description of the blocker.
            severity: Severity level (low, medium, high).
            context: Optional additional context.

        Returns:
            Saved blocker info.
        """
        git_project, git_branch = self._get_git_info()

        content = description
        if context:
            content = f"{description}\n\nContext: {context}"

        metadata: dict[str, Any] = {
            "severity": severity,
            "resolved": False,
        }
        if self._current_session_id:
            metadata["session_id"] = self._current_session_id

        item = await context_store.save(
            content=content,
            context_type=ContextType.BLOCKER,
            project=git_project,
            branch=git_branch,
            metadata=metadata,
        )

        return {
            "id": item.id,
            "description": description,
            "severity": severity,
            "project": git_project,
            "timestamp": item.timestamp.isoformat(),
        }

    async def get_blockers(
        self,
        project: str | None = None,
        include_resolved: bool = False,
    ) -> list[dict[str, Any]]:
        """Get active blockers.

        Args:
            project: Filter by project.
            include_resolved: Whether to include resolved blockers.

        Returns:
            List of blockers.
        """
        git_project, _ = self._get_git_info()
        project = project or git_project

        blockers = await context_store.get_recent(
            project=project,
            hours=168,  # 1 week
            context_type=ContextType.BLOCKER,
            limit=20,
        )

        result = []
        for b in blockers:
            resolved = b.metadata.get("resolved", False)
            if include_resolved or not resolved:
                result.append({
                    "id": b.id,
                    "description": b.content[:300],
                    "severity": b.metadata.get("severity", "medium"),
                    "resolved": resolved,
                    "project": b.project,
                    "timestamp": b.timestamp.isoformat(),
                })

        return result


# Default session manager instance
session_manager = SessionManager()

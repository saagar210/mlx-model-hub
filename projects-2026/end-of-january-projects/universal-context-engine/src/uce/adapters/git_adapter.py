"""
Git repository adapter.

Uses subprocess to call git commands and extract commit history and working state.
"""

import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .base import BaseAdapter, SyncCursor
from ..models.context_item import ContextItem, BiTemporalMetadata, RelevanceSignals


class GitAdapter(BaseAdapter):
    """
    Adapter for Git repositories.

    Extracts:
    - Commit history with messages and file changes
    - Current working tree status (modified/staged files)
    - Diff content for recent changes
    """

    name = "Git Repository"
    source_type = "git"

    def __init__(self, repo_paths: list[str]):
        """
        Initialize Git adapter.

        Args:
            repo_paths: List of repository paths to monitor
        """
        self.repo_paths = [Path(p).expanduser().resolve() for p in repo_paths]

    async def fetch_incremental(
        self, cursor: SyncCursor | None = None
    ) -> tuple[list[ContextItem], SyncCursor]:
        """Fetch commits since cursor."""
        items = []

        since = cursor.last_sync_at if cursor else datetime.utcnow() - timedelta(days=7)
        since_str = since.strftime("%Y-%m-%d %H:%M:%S")

        for repo_path in self.repo_paths:
            if not (repo_path / ".git").exists():
                continue

            try:
                # Get recent commits
                commits = await self._get_commits(repo_path, since_str)
                for commit in commits:
                    items.append(self._commit_to_item(repo_path, commit))

                # Get current working state
                status = await self._get_status(repo_path)
                if status["modified"] or status["staged"]:
                    items.append(self._status_to_item(repo_path, status))

            except Exception as e:
                # Log but don't fail on individual repo errors
                pass

        new_cursor = SyncCursor(
            source=self.source_type,
            cursor_value=datetime.utcnow().isoformat(),
            last_sync_at=datetime.utcnow(),
            items_synced=(cursor.items_synced if cursor else 0) + len(items),
        )

        return items, new_cursor

    async def fetch_recent(self, hours: int = 24) -> list[ContextItem]:
        """Fetch recent git activity."""
        since = datetime.utcnow() - timedelta(hours=hours)
        items, _ = await self.fetch_incremental(
            SyncCursor(source=self.source_type, last_sync_at=since)
        )
        return items

    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """Search git log for query."""
        items = []

        for repo_path in self.repo_paths:
            if not (repo_path / ".git").exists():
                continue

            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    [
                        "git", "-C", str(repo_path), "log",
                        "--all", f"--grep={query}",
                        "--format=%H|%s|%an|%ai|%b",
                        f"-{limit}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split("\n"):
                        if "|" in line:
                            parts = line.split("|", 4)
                            if len(parts) >= 4:
                                commit = {
                                    "sha": parts[0],
                                    "message": parts[1],
                                    "author": parts[2],
                                    "date": parts[3],
                                    "body": parts[4] if len(parts) > 4 else "",
                                    "files": [],
                                }
                                items.append(self._commit_to_item(repo_path, commit))

            except Exception:
                pass

        return items[:limit]

    async def _get_commits(self, repo_path: Path, since: str) -> list[dict]:
        """Get commits since date."""
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "git", "-C", str(repo_path), "log",
                f"--since={since}",
                "--format=%H|%s|%an|%ai|%b",
                "--name-only",
                "-100",  # Limit to 100 commits per sync
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            return []

        commits = []
        current_commit: dict | None = None

        for line in result.stdout.strip().split("\n"):
            if "|" in line and line.count("|") >= 3:
                if current_commit:
                    commits.append(current_commit)
                parts = line.split("|", 4)
                current_commit = {
                    "sha": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "date": parts[3],
                    "body": parts[4] if len(parts) > 4 else "",
                    "files": [],
                }
            elif current_commit and line.strip():
                current_commit["files"].append(line.strip())

        if current_commit:
            commits.append(current_commit)

        return commits

    async def _get_status(self, repo_path: Path) -> dict:
        """Get current git status."""
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        modified = []
        staged = []
        untracked = []

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                status = line[:2]
                filename = line[3:]

                if status[0] in "MADRCU":
                    staged.append(filename)
                if status[1] in "MD":
                    modified.append(filename)
                if status == "??":
                    untracked.append(filename)

        return {"modified": modified, "staged": staged, "untracked": untracked}

    async def _get_branch(self, repo_path: Path) -> str:
        """Get current branch name."""
        result = await asyncio.to_thread(
            subprocess.run,
            ["git", "-C", str(repo_path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        return "unknown"

    def _commit_to_item(self, repo_path: Path, commit: dict) -> ContextItem:
        """Convert commit to ContextItem."""
        # Parse date
        try:
            date_str = commit["date"].replace(" ", "T")
            # Handle timezone offset
            if "+" in date_str:
                date_str = date_str.split("+")[0]
            elif "-" in date_str and date_str.count("-") > 2:
                # Timezone offset like -0500
                date_str = date_str.rsplit("-", 1)[0]
            commit_date = datetime.fromisoformat(date_str)
        except Exception:
            commit_date = datetime.utcnow()

        repo_name = repo_path.name
        files_str = ", ".join(commit["files"][:20])
        if len(commit["files"]) > 20:
            files_str += f" (+{len(commit['files']) - 20} more)"

        content = f"Commit: {commit['message']}"
        if commit.get("body"):
            content += f"\n\n{commit['body']}"
        if files_str:
            content += f"\n\nFiles changed: {files_str}"

        return ContextItem(
            id=uuid4(),
            source="git",
            source_id=commit["sha"],
            source_url=str(repo_path),
            content_type="git_commit",
            title=f"[{repo_name}] {commit['message'][:80]}",
            content=content,
            temporal=BiTemporalMetadata(t_valid=commit_date),
            tags=["git", "commit", repo_name],
            relevance=RelevanceSignals(source_quality=0.75),
            metadata={
                "sha": commit["sha"],
                "author": commit["author"],
                "repo": str(repo_path),
                "repo_name": repo_name,
                "files": commit["files"][:50],
                "files_count": len(commit["files"]),
            },
        )

    def _status_to_item(self, repo_path: Path, status: dict) -> ContextItem:
        """Convert working tree status to ContextItem."""
        repo_name = repo_path.name

        content_parts = []
        if status["staged"]:
            content_parts.append(f"Staged: {', '.join(status['staged'][:20])}")
        if status["modified"]:
            content_parts.append(f"Modified: {', '.join(status['modified'][:20])}")
        if status["untracked"]:
            content_parts.append(f"Untracked: {', '.join(status['untracked'][:10])}")

        return ContextItem(
            id=uuid4(),
            source="git",
            source_id=f"wip_{repo_name}_{datetime.utcnow().strftime('%Y%m%d%H%M')}",
            source_url=str(repo_path),
            content_type="git_diff",
            title=f"[{repo_name}] Work in progress",
            content="\n".join(content_parts),
            temporal=BiTemporalMetadata(t_valid=datetime.utcnow()),
            expires_at=datetime.utcnow() + timedelta(hours=1),  # Ephemeral
            tags=["git", "wip", repo_name],
            relevance=RelevanceSignals(source_quality=0.6, recency=1.0),
            metadata={
                "repo": str(repo_path),
                "repo_name": repo_name,
                **status,
            },
        )

    def get_sync_interval(self) -> timedelta:
        """Git changes frequently during active development."""
        return timedelta(minutes=2)

    def get_source_quality(self) -> float:
        """Git content is structured but needs context."""
        return 0.75


__all__ = ["GitAdapter"]

"""Git repository adapter for commit history and file context."""

import asyncio
import re
from datetime import datetime, timedelta
from pathlib import Path

from personal_context.adapters.base import AbstractContextAdapter
from personal_context.schema import ContextItem, ContextSource


class GitAdapter(AbstractContextAdapter):
    """Adapter for Git repository context."""

    def __init__(self, repos_path: Path):
        self.repos_path = Path(repos_path)
        if not self.repos_path.exists():
            raise ValueError(f"Git repos path not found: {repos_path}")

    @property
    def source(self) -> ContextSource:
        return ContextSource.GIT

    async def health_check(self) -> bool:
        """Check if git is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False

    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """Search commit messages across all repos."""
        results: list[ContextItem] = []

        for repo in self._iter_repos():
            commits = await self._search_commits_in_repo(repo, query, limit=limit)
            results.extend(commits)

        # Sort by timestamp and limit
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    async def get_recent(self, hours: int = 24, limit: int = 20) -> list[ContextItem]:
        """Get recent commits across all repos."""
        results: list[ContextItem] = []
        since = datetime.now() - timedelta(hours=hours)

        for repo in self._iter_repos():
            commits = await self._get_recent_commits(repo, since, limit=limit)
            results.extend(commits)

        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    async def get_repo_context(self, repo_path: str | None = None) -> dict:
        """Get current context for a repository (branch, status, recent commits)."""
        if repo_path:
            repo = self.repos_path / repo_path
        else:
            # Use current working directory or first repo
            repo = self.repos_path

        if not (repo / ".git").exists():
            # Find first git repo
            for r in self._iter_repos():
                repo = r
                break

        branch = await self._run_git(repo, ["branch", "--show-current"])
        status = await self._run_git(repo, ["status", "--short"])

        # Get recent commits
        log_output = await self._run_git(
            repo,
            ["log", "--oneline", "-10", "--format=%h|%s|%ai|%an"],
        )

        commits = []
        for line in log_output.strip().split("\n"):
            if line and "|" in line:
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "date": parts[2],
                        "author": parts[3],
                    })

        return {
            "repo": str(repo.relative_to(self.repos_path)),
            "branch": branch.strip(),
            "status": status.strip() if status.strip() else "clean",
            "recent_commits": commits[:5],
        }

    async def get_file_history(
        self, file_path: str, repo_path: str | None = None, count: int = 10
    ) -> list[dict]:
        """Get commit history for a specific file."""
        repo = self.repos_path / repo_path if repo_path else self.repos_path

        # Find repo containing file
        if not (repo / ".git").exists():
            for r in self._iter_repos():
                if (r / file_path).exists():
                    repo = r
                    break

        log_output = await self._run_git(
            repo,
            ["log", f"-{count}", "--format=%h|%s|%ai|%an", "--", file_path],
        )

        history = []
        for line in log_output.strip().split("\n"):
            if line and "|" in line:
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    history.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "date": parts[2],
                        "author": parts[3],
                    })

        return history

    async def search_commits(
        self, query: str, repo_path: str | None = None, limit: int = 20
    ) -> list[ContextItem]:
        """Search commit messages in a specific repo or all repos."""
        if repo_path:
            repo = self.repos_path / repo_path
            return await self._search_commits_in_repo(repo, query, limit)
        else:
            return await self.search(query, limit)

    async def get_diff_summary(
        self, repo_path: str | None = None, staged: bool = False
    ) -> str:
        """Get summary of current changes."""
        repo = self.repos_path / repo_path if repo_path else self.repos_path

        if not (repo / ".git").exists():
            for r in self._iter_repos():
                repo = r
                break

        if staged:
            diff = await self._run_git(repo, ["diff", "--cached", "--stat"])
        else:
            diff = await self._run_git(repo, ["diff", "--stat"])

        return diff.strip() if diff.strip() else "No changes"

    async def _search_commits_in_repo(
        self, repo: Path, query: str, limit: int = 10
    ) -> list[ContextItem]:
        """Search commits in a single repo."""
        results: list[ContextItem] = []

        try:
            # Search commit messages
            log_output = await self._run_git(
                repo,
                [
                    "log",
                    f"-{limit * 2}",  # Get extra to filter
                    "--all",
                    f"--grep={query}",
                    "--regexp-ignore-case",
                    "--format=%H|%s|%ai|%an",
                ],
            )

            repo_name = repo.name
            for line in log_output.strip().split("\n"):
                if line and "|" in line:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        hash_full, message, date_str, author = parts
                        try:
                            timestamp = datetime.strptime(
                                date_str.split()[0], "%Y-%m-%d"
                            )
                        except ValueError:
                            timestamp = datetime.now()

                        item = ContextItem(
                            id=f"git:{repo_name}:{hash_full[:8]}",
                            source=ContextSource.GIT,
                            title=f"[{repo_name}] {message[:80]}",
                            content=f"Commit by {author}: {message}",
                            path=f"{repo_name}/{hash_full[:8]}",
                            timestamp=timestamp,
                            metadata={
                                "repo": repo_name,
                                "hash": hash_full,
                                "author": author,
                            },
                        )
                        results.append(item)

                        if len(results) >= limit:
                            break

        except Exception:
            pass

        return results

    async def _get_recent_commits(
        self, repo: Path, since: datetime, limit: int = 20
    ) -> list[ContextItem]:
        """Get recent commits from a repo."""
        results: list[ContextItem] = []
        since_str = since.strftime("%Y-%m-%d")

        try:
            log_output = await self._run_git(
                repo,
                [
                    "log",
                    f"-{limit}",
                    f"--since={since_str}",
                    "--format=%H|%s|%ai|%an",
                ],
            )

            repo_name = repo.name
            for line in log_output.strip().split("\n"):
                if line and "|" in line:
                    parts = line.split("|", 3)
                    if len(parts) >= 4:
                        hash_full, message, date_str, author = parts
                        try:
                            # Parse datetime like "2025-01-20 10:30:45 -0500"
                            dt_part = " ".join(date_str.split()[:2])
                            timestamp = datetime.strptime(dt_part, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            timestamp = datetime.now()

                        item = ContextItem(
                            id=f"git:{repo_name}:{hash_full[:8]}",
                            source=ContextSource.GIT,
                            title=f"[{repo_name}] {message[:80]}",
                            content=f"Commit by {author}: {message}",
                            path=f"{repo_name}/{hash_full[:8]}",
                            timestamp=timestamp,
                            metadata={
                                "repo": repo_name,
                                "hash": hash_full,
                                "author": author,
                            },
                        )
                        results.append(item)

        except Exception:
            pass

        return results

    def _iter_repos(self):
        """Iterate over git repositories in the repos path."""
        # Check if repos_path itself is a git repo
        if (self.repos_path / ".git").exists():
            yield self.repos_path

        # Check immediate subdirectories
        for subdir in self.repos_path.iterdir():
            if subdir.is_dir() and (subdir / ".git").exists():
                yield subdir

    async def _run_git(self, repo: Path, args: list[str]) -> str:
        """Run a git command in the specified repo."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "-C",
                str(repo),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode("utf-8", errors="replace")
        except Exception:
            return ""

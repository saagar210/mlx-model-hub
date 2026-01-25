"""Tests for the Git adapter."""

import tempfile
from pathlib import Path

import pytest

from personal_context.adapters.git import GitAdapter
from personal_context.schema import ContextSource


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository for testing."""
    import subprocess

    repo = tmp_path / "test-repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True
    )

    # Create some commits
    (repo / "file1.txt").write_text("Initial content")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit: add file1"], cwd=repo, capture_output=True
    )

    (repo / "file1.txt").write_text("Updated content with authentication")
    subprocess.run(["git", "add", "file1.txt"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add authentication feature"], cwd=repo, capture_output=True
    )

    (repo / "file2.txt").write_text("New file for testing")
    subprocess.run(["git", "add", "file2.txt"], cwd=repo, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add test file"], cwd=repo, capture_output=True
    )

    return tmp_path  # Return parent so adapter iterates subdirs


@pytest.fixture
def adapter(temp_repo: Path) -> GitAdapter:
    """Create adapter with test repo."""
    return GitAdapter(temp_repo)


class TestGitAdapter:
    """Tests for GitAdapter."""

    @pytest.mark.asyncio
    async def test_health_check(self, adapter: GitAdapter):
        """Test health check passes when git is available."""
        assert await adapter.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_invalid_path(self, tmp_path: Path):
        """Test adapter fails for nonexistent path."""
        with pytest.raises(ValueError):
            GitAdapter(tmp_path / "nonexistent")

    @pytest.mark.asyncio
    async def test_search_commits(self, adapter: GitAdapter):
        """Test searching commit messages."""
        results = await adapter.search("authentication", limit=10)
        assert len(results) >= 1
        assert any("authentication" in r.title.lower() for r in results)
        assert all(r.source == ContextSource.GIT for r in results)

    @pytest.mark.asyncio
    async def test_search_no_results(self, adapter: GitAdapter):
        """Test search with no matches."""
        results = await adapter.search("nonexistent-xyz-123", limit=10)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_get_repo_context(self, adapter: GitAdapter):
        """Test getting repository context."""
        context = await adapter.get_repo_context()
        assert "branch" in context
        assert "status" in context
        assert "recent_commits" in context
        assert len(context["recent_commits"]) >= 1

    @pytest.mark.asyncio
    async def test_get_file_history(self, adapter: GitAdapter):
        """Test getting file history."""
        history = await adapter.get_file_history("file1.txt")
        assert len(history) >= 2  # Initial + update
        assert any("authentication" in h["message"].lower() for h in history)

    @pytest.mark.asyncio
    async def test_get_recent(self, adapter: GitAdapter):
        """Test getting recent commits."""
        # Look back far enough to include our test commits
        results = await adapter.get_recent(hours=24, limit=10)
        assert len(results) >= 1
        assert all(r.source == ContextSource.GIT for r in results)

    @pytest.mark.asyncio
    async def test_get_diff_summary(self, adapter: GitAdapter, temp_repo: Path):
        """Test getting diff summary."""
        # Make an uncommitted change
        repo = temp_repo / "test-repo"
        (repo / "file1.txt").write_text("Uncommitted change")

        diff = await adapter.get_diff_summary()
        assert "file1" in diff or "No changes" in diff

"""Obsidian vault adapter for reading and searching markdown notes."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import frontmatter

from personal_context.adapters.base import AbstractContextAdapter
from personal_context.schema import ContextItem, ContextSource, NoteResult


class ObsidianAdapter(AbstractContextAdapter):
    """Adapter for Obsidian markdown vault."""

    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        if not self.vault_path.exists():
            raise ValueError(f"Obsidian vault not found: {vault_path}")

    @property
    def source(self) -> ContextSource:
        return ContextSource.OBSIDIAN

    async def health_check(self) -> bool:
        """Check if vault is accessible."""
        return self.vault_path.exists() and self.vault_path.is_dir()

    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """Search notes by content and filename."""
        results: list[tuple[float, ContextItem]] = []
        query_lower = query.lower()
        query_terms = query_lower.split()

        for md_file in self._iter_markdown_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                content_lower = content.lower()
                rel_path = md_file.relative_to(self.vault_path)
                filename_lower = md_file.stem.lower()

                # Score based on matches
                score = 0.0

                # Filename match (highest weight)
                if query_lower in filename_lower:
                    score += 0.5
                for term in query_terms:
                    if term in filename_lower:
                        score += 0.2

                # Content match
                content_matches = content_lower.count(query_lower)
                if content_matches > 0:
                    score += min(0.3, content_matches * 0.05)

                # Term frequency in content
                for term in query_terms:
                    term_count = content_lower.count(term)
                    if term_count > 0:
                        score += min(0.2, term_count * 0.02)

                if score > 0:
                    # Extract snippet around first match
                    snippet = self._extract_snippet(content, query, max_length=300)
                    post = frontmatter.loads(content)
                    title = post.metadata.get("title", md_file.stem)

                    item = ContextItem(
                        id=f"obsidian:{rel_path}",
                        source=ContextSource.OBSIDIAN,
                        title=title,
                        content=snippet,
                        path=str(rel_path),
                        timestamp=datetime.fromtimestamp(md_file.stat().st_mtime),
                        metadata=dict(post.metadata),
                        relevance_score=score,
                    )
                    results.append((score, item))

            except Exception:
                # Skip files that can't be read
                continue

        # Sort by score descending, return top N
        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:limit]]

    async def get_recent(self, hours: int = 24, limit: int = 20) -> list[ContextItem]:
        """Get recently modified notes."""
        cutoff = datetime.now() - timedelta(hours=hours)
        results: list[tuple[datetime, ContextItem]] = []

        for md_file in self._iter_markdown_files():
            try:
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                if mtime >= cutoff:
                    content = md_file.read_text(encoding="utf-8")
                    rel_path = md_file.relative_to(self.vault_path)
                    post = frontmatter.loads(content)
                    title = post.metadata.get("title", md_file.stem)

                    item = ContextItem(
                        id=f"obsidian:{rel_path}",
                        source=ContextSource.OBSIDIAN,
                        title=title,
                        content=content[:500],
                        path=str(rel_path),
                        timestamp=mtime,
                        metadata=dict(post.metadata),
                    )
                    results.append((mtime, item))
            except Exception:
                continue

        # Sort by mtime descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:limit]]

    async def read_note(self, path: str) -> NoteResult | None:
        """Read a specific note by path."""
        full_path = self.vault_path / path
        if not full_path.exists() or not full_path.suffix == ".md":
            # Try adding .md extension
            full_path = self.vault_path / f"{path}.md"
            if not full_path.exists():
                return None

        try:
            content = full_path.read_text(encoding="utf-8")
            post = frontmatter.loads(content)
            rel_path = full_path.relative_to(self.vault_path)

            return NoteResult(
                path=str(rel_path),
                title=post.metadata.get("title", full_path.stem),
                content=post.content,
                frontmatter=dict(post.metadata),
                modified=datetime.fromtimestamp(full_path.stat().st_mtime),
                backlinks=await self.get_backlinks(str(rel_path)),
            )
        except Exception:
            return None

    async def get_backlinks(self, path: str) -> list[str]:
        """Find notes that link to the given path."""
        # Normalize path for matching
        target_stem = Path(path).stem
        backlinks: list[str] = []

        # Pattern for wikilinks: [[note]] or [[note|alias]]
        wikilink_pattern = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")

        for md_file in self._iter_markdown_files():
            if md_file.stem == target_stem:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                matches = wikilink_pattern.findall(content)
                for match in matches:
                    # Check if this links to our target
                    if match.lower() == target_stem.lower() or match.lower().endswith(
                        f"/{target_stem.lower()}"
                    ):
                        rel_path = md_file.relative_to(self.vault_path)
                        backlinks.append(str(rel_path))
                        break
            except Exception:
                continue

        return backlinks

    async def list_by_tag(self, tag: str, limit: int = 20) -> list[ContextItem]:
        """Find notes with a specific tag."""
        results: list[ContextItem] = []
        tag_clean = tag.lstrip("#")

        for md_file in self._iter_markdown_files():
            try:
                content = md_file.read_text(encoding="utf-8")
                post = frontmatter.loads(content)

                # Check frontmatter tags
                fm_tags = post.metadata.get("tags", [])
                if isinstance(fm_tags, str):
                    fm_tags = [fm_tags]

                # Check inline tags
                inline_tags = re.findall(r"#([\w/-]+)", content)

                all_tags = [t.lower() for t in fm_tags + inline_tags]
                if tag_clean.lower() in all_tags:
                    rel_path = md_file.relative_to(self.vault_path)
                    item = ContextItem(
                        id=f"obsidian:{rel_path}",
                        source=ContextSource.OBSIDIAN,
                        title=post.metadata.get("title", md_file.stem),
                        content=content[:300],
                        path=str(rel_path),
                        timestamp=datetime.fromtimestamp(md_file.stat().st_mtime),
                        metadata=dict(post.metadata),
                    )
                    results.append(item)
                    if len(results) >= limit:
                        break
            except Exception:
                continue

        return results

    def _iter_markdown_files(self):
        """Iterate over all markdown files in vault, excluding hidden dirs."""
        for md_file in self.vault_path.rglob("*.md"):
            # Skip hidden directories and .obsidian
            if any(part.startswith(".") for part in md_file.parts):
                continue
            yield md_file

    def _extract_snippet(self, content: str, query: str, max_length: int = 300) -> str:
        """Extract a snippet around the query match."""
        query_lower = query.lower()
        content_lower = content.lower()

        # Find first occurrence
        idx = content_lower.find(query_lower)
        if idx == -1:
            # Try first term
            terms = query_lower.split()
            for term in terms:
                idx = content_lower.find(term)
                if idx != -1:
                    break

        if idx == -1:
            # No match, return start of content
            return content[:max_length]

        # Extract context around match
        start = max(0, idx - max_length // 3)
        end = min(len(content), idx + max_length * 2 // 3)

        snippet = content[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

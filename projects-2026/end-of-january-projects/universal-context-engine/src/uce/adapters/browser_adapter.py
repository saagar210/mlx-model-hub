"""
Browser context adapter.

Captures open tabs, page content, and navigation through Playwright MCP or direct integration.
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from .base import BaseAdapter, SyncCursor
from ..models.context_item import ContextItem, BiTemporalMetadata, RelevanceSignals


class BrowserContextAdapter(BaseAdapter):
    """
    Adapter for browser context via Playwright MCP.

    Captures:
    - Open browser tabs with titles and URLs
    - Page content snapshots (accessibility tree)
    - Navigation history
    """

    name = "Browser Context"
    source_type = "browser"

    def __init__(self, mcp_client: Any | None = None):
        """
        Initialize browser adapter.

        Args:
            mcp_client: Optional MCP client for Playwright integration
        """
        self.mcp_client = mcp_client
        self._cached_tabs: dict[str, dict] = {}

    async def fetch_incremental(
        self, cursor: SyncCursor | None = None
    ) -> tuple[list[ContextItem], SyncCursor]:
        """Fetch current browser state."""
        items = []

        if not self.mcp_client:
            # Return empty if no MCP client configured
            return items, SyncCursor(
                source=self.source_type,
                last_sync_at=datetime.utcnow(),
                items_synced=cursor.items_synced if cursor else 0,
            )

        try:
            # Get tabs context from Playwright MCP
            tabs_response = await self.mcp_client.call_tool(
                "mcp__playwright__browser_tabs",
                {"action": "list"},
            )

            for tab in tabs_response.get("tabs", []):
                tab_id = str(tab.get("index", tab.get("id")))

                # Check if tab content changed
                cached = self._cached_tabs.get(tab_id)
                if cached and cached.get("url") == tab.get("url"):
                    continue

                # Get page snapshot for content
                snapshot = None
                try:
                    snapshot = await self.mcp_client.call_tool(
                        "mcp__playwright__browser_snapshot",
                        {"tabId": tab.get("id")},
                    )
                except Exception:
                    pass

                item = self._tab_to_item(tab, snapshot)
                items.append(item)

                self._cached_tabs[tab_id] = {
                    "url": tab.get("url"),
                    "timestamp": datetime.utcnow(),
                }

        except Exception:
            # Browser automation errors are common, continue silently
            pass

        new_cursor = SyncCursor(
            source=self.source_type,
            cursor_value=datetime.utcnow().isoformat(),
            last_sync_at=datetime.utcnow(),
            items_synced=(cursor.items_synced if cursor else 0) + len(items),
        )

        return items, new_cursor

    async def fetch_recent(self, hours: int = 24) -> list[ContextItem]:
        """Fetch current browser state (browser context is always 'recent')."""
        items, _ = await self.fetch_incremental(None)
        return items

    async def search(self, query: str, limit: int = 10) -> list[ContextItem]:
        """Browser doesn't support historical search - return empty."""
        return []

    def add_tab_manually(
        self,
        url: str,
        title: str,
        content: str | None = None,
    ) -> ContextItem:
        """
        Manually add a browser tab context.

        Useful when MCP client is not available but tab info is known.
        """
        return ContextItem(
            id=uuid4(),
            source="browser",
            source_id=f"tab_{url[:50]}",
            source_url=url,
            content_type="page_content",
            title=title,
            content=content or f"URL: {url}\nTitle: {title}",
            temporal=BiTemporalMetadata(t_valid=datetime.utcnow()),
            expires_at=datetime.utcnow() + timedelta(hours=4),
            tags=["browser", "tab"],
            relevance=RelevanceSignals(source_quality=0.6, recency=1.0),
            metadata={"url": url, "title": title},
        )

    def _tab_to_item(self, tab: dict, snapshot: dict | str | None) -> ContextItem:
        """Convert tab info to ContextItem."""
        url = tab.get("url", "unknown")
        title = tab.get("title", "Untitled")

        content_parts = [
            f"URL: {url}",
            f"Title: {title}",
        ]

        if snapshot:
            text = self._extract_text_from_snapshot(snapshot)
            if text:
                # Limit content length
                content_parts.append(f"\n{text[:3000]}")

        return ContextItem(
            id=uuid4(),
            source="browser",
            source_id=f"tab_{tab.get('id', 'unknown')}",
            source_url=url,
            content_type="page_content",
            title=title,
            content="\n".join(content_parts),
            temporal=BiTemporalMetadata(t_valid=datetime.utcnow()),
            expires_at=datetime.utcnow() + timedelta(hours=4),  # Short-lived
            tags=["browser", "tab", self._domain_from_url(url)],
            relevance=RelevanceSignals(source_quality=0.6, recency=1.0),
            metadata={
                "tab_id": tab.get("id"),
                "url": url,
                "title": title,
                "domain": self._domain_from_url(url),
            },
        )

    def _extract_text_from_snapshot(self, snapshot: dict | str | None) -> str:
        """Extract readable text from accessibility snapshot."""
        if not snapshot:
            return ""

        if isinstance(snapshot, str):
            return snapshot[:3000]

        if isinstance(snapshot, dict):
            # Try common keys
            for key in ["content", "text", "markdown", "body"]:
                if key in snapshot:
                    return str(snapshot[key])[:3000]

            # Try nested structure
            if "result" in snapshot:
                return self._extract_text_from_snapshot(snapshot["result"])

        return ""

    def _domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc or "unknown"
        except Exception:
            return "unknown"

    def get_sync_interval(self) -> timedelta:
        """Browser state changes frequently."""
        return timedelta(minutes=1)

    def get_source_quality(self) -> float:
        """Browser content is ephemeral and unstructured."""
        return 0.6

    def clear_cache(self) -> None:
        """Clear the tab cache."""
        self._cached_tabs.clear()


__all__ = ["BrowserContextAdapter"]

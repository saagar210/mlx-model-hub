# Universal Context Engine
## Unified Context Aggregation Across All AI Systems

---

## Project Overview

### What This Is
A unified context aggregation layer that combines data from all your AI projects into a single, queryable context store. The Universal Context Engine acts as the "memory backbone" for your entire AI stack—pulling from Knowledge Engine, MCP servers, LocalCrew outputs, browsing context, and more to provide any AI system with rich, relevant context on demand.

### Current Status
**Phase**: Planning
**Priority**: High (amplifies all other projects)
**Estimated Effort**: 2-3 sessions, ongoing refinement

---

## Context & Motivation

### The Problem
Your AI systems each have their own context silos:
- **Knowledge Engine**: Documents and embeddings
- **MCP Servers**: Real-time data (git, calendar, clipboard)
- **LocalCrew**: Agent execution history
- **Dify Workflows**: Conversation state
- **GraphRAG**: Entity relationships
- **Browser Automation**: Page content and session state

When you ask Claude a question, it doesn't know:
- What you worked on in LocalCrew yesterday
- What's in your clipboard right now
- What browser tabs are open
- What git changes are pending
- How entities relate across documents

### The Solution
The Universal Context Engine:
1. **Aggregates**: Pulls from all context sources via adapters
2. **Normalizes**: Transforms into unified schema
3. **Indexes**: Makes searchable with hybrid retrieval
4. **Prioritizes**: Ranks by recency, relevance, and source quality
5. **Serves**: Exposes via MCP server for any AI to consume

### Why This Matters

1. **Cross-System Intelligence**: LocalCrew agents know what you searched in Knowledge Engine
2. **Temporal Awareness**: "What was I working on?" becomes answerable
3. **Entity Resolution**: Same concept across different sources gets connected
4. **Reduced Repetition**: Context follows you, no re-explaining
5. **Better Responses**: More context = more relevant AI outputs

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                        UNIVERSAL CONTEXT ENGINE                                │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                       CONTEXT SOURCES (Adapters)                         │  │
│  │                                                                          │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │  │
│  │  │  Knowledge  │ │    MCP      │ │  LocalCrew  │ │   Browser   │       │  │
│  │  │   Engine    │ │  Servers    │ │   History   │ │   Context   │       │  │
│  │  │             │ │             │ │             │ │             │       │  │
│  │  │ • Documents │ │ • Git       │ │ • Crew runs │ │ • Open tabs │       │  │
│  │  │ • Chunks    │ │ • Calendar  │ │ • Agent     │ │ • Page text │       │  │
│  │  │ • Embeddings│ │ • Clipboard │ │   outputs   │ │ • Forms     │       │  │
│  │  │             │ │ • System    │ │ • Tasks     │ │             │       │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘       │  │
│  │         │               │               │               │               │  │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │  │
│  │  │  GraphRAG   │ │  Langfuse   │ │    Dify     │ │  Obsidian   │       │  │
│  │  │  (Proj 5)   │ │  (Proj 8)   │ │  (Proj 4)   │ │             │       │  │
│  │  │             │ │             │ │             │ │             │       │  │
│  │  │ • Entities  │ │ • Traces    │ │ • Sessions  │ │ • Notes     │       │  │
│  │  │ • Relations │ │ • Scores    │ │ • Workflows │ │ • Links     │       │  │
│  │  │ • Summaries │ │ • Prompts   │ │             │ │ • Tags      │       │  │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘       │  │
│  │         │               │               │               │               │  │
│  └─────────┴───────────────┴───────────────┴───────────────┴───────────────┘  │
│                                       │                                        │
│                                       ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         INGESTION PIPELINE                               │  │
│  │                                                                          │  │
│  │  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐              │  │
│  │  │   Adapter     │   │   Schema      │   │   Dedup &     │              │  │
│  │  │   Layer       │──▶│   Normalizer  │──▶│   Merge       │              │  │
│  │  │               │   │               │   │               │              │  │
│  │  │ Source-       │   │ Common        │   │ Entity        │              │  │
│  │  │ specific      │   │ context       │   │ resolution    │              │  │
│  │  │ transformers  │   │ format        │   │ across        │              │  │
│  │  │               │   │               │   │ sources       │              │  │
│  │  └───────────────┘   └───────────────┘   └───────────────┘              │  │
│  │                                                                          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                        │
│                                       ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         UNIFIED CONTEXT STORE                            │  │
│  │                                                                          │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │                     CONTEXT ITEMS                                  │  │  │
│  │  │                                                                    │  │  │
│  │  │  {                                                                 │  │  │
│  │  │    "id": "ctx_123",                                                │  │  │
│  │  │    "source": "knowledge_engine",                                   │  │  │
│  │  │    "type": "document_chunk",                                       │  │  │
│  │  │    "content": "...",                                               │  │  │
│  │  │    "embedding": [...],                                             │  │  │
│  │  │    "timestamp": "2026-01-25T10:30:00Z",                            │  │  │
│  │  │    "metadata": {...},                                              │  │  │
│  │  │    "entities": ["OAuth", "Authentication"],                        │  │  │
│  │  │    "relevance_signals": {                                          │  │  │
│  │  │      "recency": 0.9,                                               │  │  │
│  │  │      "frequency": 0.7,                                             │  │  │
│  │  │      "source_quality": 0.95                                        │  │  │
│  │  │    }                                                               │  │  │
│  │  │  }                                                                 │  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                          │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                       │  │
│  │  │   Vector Index      │  │   Keyword Index     │                       │  │
│  │  │   (Qdrant)          │  │   (BM25)            │                       │  │
│  │  │                     │  │                     │                       │  │
│  │  │   Semantic search   │  │   Exact matching    │                       │  │
│  │  │   across all        │  │   Entity lookup     │                       │  │
│  │  │   context           │  │   Tag filtering     │                       │  │
│  │  └─────────────────────┘  └─────────────────────┘                       │  │
│  │                                                                          │  │
│  │  ┌─────────────────────┐  ┌─────────────────────┐                       │  │
│  │  │   Temporal Index    │  │   Entity Graph      │                       │  │
│  │  │                     │  │                     │                       │  │
│  │  │   Time-based        │  │   Cross-source      │                       │  │
│  │  │   retrieval         │  │   connections       │                       │  │
│  │  │   "Last 24 hours"   │  │                     │                       │  │
│  │  └─────────────────────┘  └─────────────────────┘                       │  │
│  │                                                                          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                       │                                        │
│                                       ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         CONTEXT API                                      │  │
│  │                                                                          │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │                       MCP SERVER                                   │  │  │
│  │  │                                                                    │  │  │
│  │  │   Tools:                                                           │  │  │
│  │  │   • search_context(query, filters) → relevant context items        │  │  │
│  │  │   • get_recent_context(hours, sources) → temporal slice            │  │  │
│  │  │   • get_entity_context(entity) → all mentions across sources       │  │  │
│  │  │   • get_session_context(session_id) → conversation continuity      │  │  │
│  │  │                                                                    │  │  │
│  │  │   Resources:                                                       │  │  │
│  │  │   • context://recent → last hour of activity                       │  │  │
│  │  │   • context://working → current work context                       │  │  │
│  │  │   • context://entity/{name} → entity-centric view                  │  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                          │  │
│  │  ┌───────────────────────────────────────────────────────────────────┐  │  │
│  │  │                       REST API                                     │  │  │
│  │  │                                                                    │  │  │
│  │  │   POST /context/search                                             │  │  │
│  │  │   POST /context/ingest                                             │  │  │
│  │  │   GET  /context/recent                                             │  │  │
│  │  │   GET  /context/entity/{name}                                      │  │  │
│  │  │   GET  /context/stats                                              │  │  │
│  │  └───────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Specification

### Unified Context Schema

```python
from pydantic import BaseModel
from typing import List, Dict, Optional, Literal
from datetime import datetime

class RelevanceSignals(BaseModel):
    """Signals used for context ranking"""
    recency: float = 0.5        # 0-1, how recent
    frequency: float = 0.5      # 0-1, how often accessed/referenced
    source_quality: float = 0.8 # 0-1, trustworthiness of source
    explicit_relevance: float = 0.0  # 0-1, user-marked importance

class ContextItem(BaseModel):
    """Universal context item schema"""
    id: str
    source: Literal[
        "knowledge_engine",
        "graphrag",
        "mcp_git",
        "mcp_calendar",
        "mcp_clipboard",
        "localcrew",
        "dify",
        "langfuse",
        "browser",
        "obsidian"
    ]
    type: Literal[
        "document_chunk",
        "entity",
        "relationship",
        "git_change",
        "calendar_event",
        "clipboard_content",
        "agent_output",
        "conversation",
        "trace",
        "page_content",
        "note"
    ]
    content: str
    embedding: Optional[List[float]] = None
    timestamp: datetime
    expires_at: Optional[datetime] = None  # For ephemeral context
    metadata: Dict = {}
    entities: List[str] = []  # Extracted/linked entities
    tags: List[str] = []
    relevance_signals: RelevanceSignals = RelevanceSignals()

    # Cross-references
    related_ids: List[str] = []  # Links to other context items
    source_id: Optional[str] = None  # Original ID in source system
```

### Source Adapters

```python
# universal-context-engine/adapters/base.py
from abc import ABC, abstractmethod
from typing import List, AsyncIterator
from ..schema import ContextItem

class ContextAdapter(ABC):
    """Base class for context source adapters"""

    source_name: str

    @abstractmethod
    async def fetch_recent(self, hours: int = 24) -> List[ContextItem]:
        """Fetch recent context from this source"""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> List[ContextItem]:
        """Search this source for relevant context"""
        pass

    @abstractmethod
    async def stream_updates(self) -> AsyncIterator[ContextItem]:
        """Stream real-time updates from this source"""
        pass

    def transform(self, raw_data: dict) -> ContextItem:
        """Transform source-specific data to unified schema"""
        raise NotImplementedError
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Session 1)

```python
# universal-context-engine/core/engine.py
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
import asyncio

from ..schema import ContextItem, RelevanceSignals
from ..adapters import get_adapter

class UniversalContextEngine:
    """Main context aggregation and retrieval engine"""

    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection_name: str = "universal_context"
    ):
        self.qdrant = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.adapters: Dict[str, ContextAdapter] = {}

        # Initialize collection if needed
        self._ensure_collection()

    def _ensure_collection(self):
        """Create Qdrant collection for context storage"""
        collections = self.qdrant.get_collections().collections
        if self.collection_name not in [c.name for c in collections]:
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=768,  # nomic-embed-text dimension
                    distance=Distance.COSINE
                )
            )

    def register_adapter(self, adapter: ContextAdapter):
        """Register a context source adapter"""
        self.adapters[adapter.source_name] = adapter

    async def ingest(self, item: ContextItem):
        """Ingest a single context item"""
        # Generate embedding if not present
        if not item.embedding:
            item.embedding = await self._embed(item.content)

        # Store in Qdrant
        self.qdrant.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=item.id,
                    vector=item.embedding,
                    payload=item.model_dump(exclude={"embedding"})
                )
            ]
        )

    async def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        types: Optional[List[str]] = None,
        hours: Optional[int] = None,
        limit: int = 20
    ) -> List[ContextItem]:
        """Search unified context store"""

        # Build filter
        filters = []
        if sources:
            filters.append({"source": {"$in": sources}})
        if types:
            filters.append({"type": {"$in": types}})
        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            filters.append({"timestamp": {"$gte": cutoff.isoformat()}})

        # Embed query
        query_embedding = await self._embed(query)

        # Search Qdrant
        results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter={"must": filters} if filters else None,
            limit=limit
        )

        # Convert to ContextItems and rank
        items = [
            ContextItem(**r.payload, embedding=None)
            for r in results
        ]

        return self._rank_by_relevance(items, query)

    async def get_recent(
        self,
        hours: int = 24,
        sources: Optional[List[str]] = None
    ) -> List[ContextItem]:
        """Get recent context across sources"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Query Qdrant with time filter
        results = self.qdrant.scroll(
            collection_name=self.collection_name,
            scroll_filter={
                "must": [
                    {"timestamp": {"$gte": cutoff.isoformat()}},
                    *([{"source": {"$in": sources}}] if sources else [])
                ]
            },
            limit=100
        )[0]

        items = [ContextItem(**r.payload) for r in results]
        return sorted(items, key=lambda x: x.timestamp, reverse=True)

    async def get_entity_context(self, entity: str) -> List[ContextItem]:
        """Get all context mentioning a specific entity"""
        results = self.qdrant.scroll(
            collection_name=self.collection_name,
            scroll_filter={
                "must": [
                    {"entities": {"$contains": entity}}
                ]
            },
            limit=50
        )[0]

        return [ContextItem(**r.payload) for r in results]

    async def sync_all_sources(self, hours: int = 24):
        """Sync recent data from all registered adapters"""
        tasks = []
        for name, adapter in self.adapters.items():
            tasks.append(self._sync_adapter(adapter, hours))

        await asyncio.gather(*tasks)

    async def _sync_adapter(self, adapter: ContextAdapter, hours: int):
        """Sync a single adapter"""
        items = await adapter.fetch_recent(hours)
        for item in items:
            await self.ingest(item)

    def _rank_by_relevance(
        self,
        items: List[ContextItem],
        query: str
    ) -> List[ContextItem]:
        """Rank items by combined relevance signals"""
        for item in items:
            # Calculate composite score
            signals = item.relevance_signals

            # Recency boost (exponential decay)
            age_hours = (datetime.utcnow() - item.timestamp).total_seconds() / 3600
            recency_score = max(0, 1 - (age_hours / 168))  # Decay over 1 week

            # Source quality varies by type
            source_weights = {
                "knowledge_engine": 0.9,
                "obsidian": 0.85,
                "graphrag": 0.85,
                "localcrew": 0.8,
                "mcp_git": 0.75,
                "browser": 0.6,
                "mcp_clipboard": 0.5
            }

            # Composite score
            item.relevance_signals.recency = recency_score
            item._score = (
                0.4 * recency_score +
                0.3 * source_weights.get(item.source, 0.5) +
                0.2 * signals.frequency +
                0.1 * signals.explicit_relevance
            )

        return sorted(items, key=lambda x: x._score, reverse=True)

    async def _embed(self, text: str) -> List[float]:
        """Generate embedding using nomic-embed-text"""
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:11434/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": text}
            )
            return response.json()["embedding"]
```

### Phase 2: Source Adapters (Session 1-2)

```python
# universal-context-engine/adapters/knowledge_engine.py
from typing import List, AsyncIterator
import httpx
from .base import ContextAdapter
from ..schema import ContextItem

class KnowledgeEngineAdapter(ContextAdapter):
    """Adapter for Knowledge Engine RAG system"""

    source_name = "knowledge_engine"

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def fetch_recent(self, hours: int = 24) -> List[ContextItem]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/documents/recent",
                params={"hours": hours}
            )

            items = []
            for doc in response.json():
                items.append(self.transform(doc))

            return items

    async def search(self, query: str, limit: int = 10) -> List[ContextItem]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/search/hybrid",
                json={"query": query, "limit": limit}
            )

            return [self.transform(r) for r in response.json()["results"]]

    async def stream_updates(self) -> AsyncIterator[ContextItem]:
        # Knowledge Engine would need to expose a webhook/SSE endpoint
        pass

    def transform(self, raw: dict) -> ContextItem:
        return ContextItem(
            id=f"ke_{raw['id']}",
            source="knowledge_engine",
            type="document_chunk",
            content=raw["content"],
            embedding=raw.get("embedding"),
            timestamp=raw.get("indexed_at", datetime.utcnow()),
            metadata={
                "source_file": raw.get("source"),
                "chunk_index": raw.get("chunk_index")
            },
            entities=raw.get("entities", []),
            tags=raw.get("tags", []),
            source_id=raw["id"]
        )


# universal-context-engine/adapters/git_mcp.py
class GitMCPAdapter(ContextAdapter):
    """Adapter for Git context via MCP"""

    source_name = "mcp_git"

    async def fetch_recent(self, hours: int = 24) -> List[ContextItem]:
        # Call MCP git server
        items = []

        # Recent commits
        commits = await self._mcp_call("git_log", {"limit": 50})
        for commit in commits:
            if self._within_hours(commit["date"], hours):
                items.append(ContextItem(
                    id=f"git_commit_{commit['sha'][:8]}",
                    source="mcp_git",
                    type="git_change",
                    content=f"Commit: {commit['message']}\n\nFiles: {', '.join(commit['files'])}",
                    timestamp=commit["date"],
                    metadata={
                        "sha": commit["sha"],
                        "author": commit["author"],
                        "files": commit["files"]
                    },
                    entities=self._extract_entities(commit),
                    tags=["git", "commit"]
                ))

        # Uncommitted changes
        status = await self._mcp_call("git_status", {})
        if status["modified"] or status["staged"]:
            items.append(ContextItem(
                id=f"git_wip_{datetime.utcnow().isoformat()}",
                source="mcp_git",
                type="git_change",
                content=f"Work in progress:\nModified: {status['modified']}\nStaged: {status['staged']}",
                timestamp=datetime.utcnow(),
                metadata=status,
                tags=["git", "wip"],
                expires_at=datetime.utcnow() + timedelta(hours=1)  # Ephemeral
            ))

        return items


# universal-context-engine/adapters/localcrew.py
class LocalCrewAdapter(ContextAdapter):
    """Adapter for LocalCrew agent execution history"""

    source_name = "localcrew"

    async def fetch_recent(self, hours: int = 24) -> List[ContextItem]:
        # Query Langfuse for LocalCrew traces (if integrated)
        # Or read from LocalCrew's own logs

        items = []
        traces = await self._get_crew_traces(hours)

        for trace in traces:
            items.append(ContextItem(
                id=f"crew_{trace['id']}",
                source="localcrew",
                type="agent_output",
                content=f"Crew: {trace['crew_name']}\nTask: {trace['task']}\nOutput: {trace['output'][:1000]}",
                timestamp=trace["completed_at"],
                metadata={
                    "crew_name": trace["crew_name"],
                    "agents": trace["agents"],
                    "task": trace["task"],
                    "success": trace["success"]
                },
                entities=trace.get("extracted_entities", []),
                tags=["crew", trace["crew_name"]]
            ))

        return items


# universal-context-engine/adapters/browser.py
class BrowserContextAdapter(ContextAdapter):
    """Adapter for browser automation context"""

    source_name = "browser"

    async def fetch_recent(self, hours: int = 24) -> List[ContextItem]:
        # Query Playwright MCP or browser session store
        items = []

        # Open tabs content
        tabs = await self._get_open_tabs()
        for tab in tabs:
            items.append(ContextItem(
                id=f"browser_tab_{tab['id']}",
                source="browser",
                type="page_content",
                content=f"Tab: {tab['title']}\nURL: {tab['url']}\n\n{tab['text'][:2000]}",
                timestamp=tab.get("last_accessed", datetime.utcnow()),
                metadata={
                    "url": tab["url"],
                    "title": tab["title"]
                },
                tags=["browser", "open_tab"],
                expires_at=datetime.utcnow() + timedelta(hours=4)  # Short-lived
            ))

        return items
```

### Phase 3: MCP Server (Session 2)

```python
# universal-context-engine/mcp_server.py
from mcp import Server, Resource, Tool
from mcp.types import TextContent
from .core.engine import UniversalContextEngine

app = Server("universal-context")
engine = UniversalContextEngine()

# Register all adapters
from .adapters import (
    KnowledgeEngineAdapter,
    GitMCPAdapter,
    LocalCrewAdapter,
    BrowserContextAdapter,
    ObsidianAdapter,
    GraphRAGAdapter
)

engine.register_adapter(KnowledgeEngineAdapter())
engine.register_adapter(GitMCPAdapter())
engine.register_adapter(LocalCrewAdapter())
engine.register_adapter(BrowserContextAdapter())
engine.register_adapter(ObsidianAdapter())
engine.register_adapter(GraphRAGAdapter())


@app.tool()
async def search_context(
    query: str,
    sources: list[str] | None = None,
    types: list[str] | None = None,
    hours: int | None = None,
    limit: int = 20
) -> str:
    """
    Search unified context across all sources.

    Args:
        query: Search query
        sources: Filter by sources (knowledge_engine, mcp_git, localcrew, etc.)
        types: Filter by types (document_chunk, git_change, agent_output, etc.)
        hours: Only include context from last N hours
        limit: Maximum results to return
    """
    results = await engine.search(
        query=query,
        sources=sources,
        types=types,
        hours=hours,
        limit=limit
    )

    formatted = []
    for item in results:
        formatted.append(
            f"[{item.source}:{item.type}] ({item.timestamp.strftime('%Y-%m-%d %H:%M')})\n"
            f"{item.content[:500]}...\n"
            f"Entities: {', '.join(item.entities)}\n"
            f"---"
        )

    return "\n\n".join(formatted)


@app.tool()
async def get_recent_context(
    hours: int = 24,
    sources: list[str] | None = None
) -> str:
    """
    Get recent context activity.

    Args:
        hours: How many hours back to look
        sources: Filter by specific sources
    """
    results = await engine.get_recent(hours=hours, sources=sources)

    formatted = []
    for item in results:
        formatted.append(
            f"[{item.timestamp.strftime('%H:%M')}] {item.source}: {item.content[:200]}..."
        )

    return "\n".join(formatted)


@app.tool()
async def get_entity_context(entity: str) -> str:
    """
    Get all context related to a specific entity.

    Args:
        entity: Entity name to look up (e.g., "OAuth", "Knowledge Engine")
    """
    results = await engine.get_entity_context(entity)

    formatted = [f"Context for entity: {entity}\n"]
    for item in results:
        formatted.append(
            f"[{item.source}] {item.content[:300]}...\n"
        )

    return "\n".join(formatted)


@app.tool()
async def get_working_context() -> str:
    """
    Get current working context: recent activity, open tabs, pending changes.
    Useful for understanding "what am I working on?"
    """
    # Combine multiple signals
    git_context = await engine.search(
        query="",
        sources=["mcp_git"],
        hours=4,
        limit=5
    )

    browser_context = await engine.search(
        query="",
        sources=["browser"],
        hours=1,
        limit=5
    )

    recent_crews = await engine.search(
        query="",
        sources=["localcrew"],
        hours=8,
        limit=3
    )

    output = ["## Current Working Context\n"]

    if git_context:
        output.append("### Recent Git Activity")
        for item in git_context:
            output.append(f"- {item.content[:100]}...")

    if browser_context:
        output.append("\n### Open Tabs")
        for item in browser_context:
            output.append(f"- {item.metadata.get('title', 'Unknown')}")

    if recent_crews:
        output.append("\n### Recent Agent Work")
        for item in recent_crews:
            output.append(f"- {item.content[:100]}...")

    return "\n".join(output)


@app.resource("context://recent")
async def recent_context_resource() -> Resource:
    """Recent context from the last hour"""
    results = await engine.get_recent(hours=1)
    content = "\n\n".join([
        f"[{r.source}] {r.content[:300]}"
        for r in results
    ])
    return Resource(
        uri="context://recent",
        name="Recent Context",
        description="Activity from the last hour",
        content=TextContent(text=content)
    )


@app.resource("context://working")
async def working_context_resource() -> Resource:
    """Current working context"""
    content = await get_working_context()
    return Resource(
        uri="context://working",
        name="Working Context",
        description="Current work context including git, browser, recent agents",
        content=TextContent(text=content)
    )


if __name__ == "__main__":
    import asyncio

    # Background sync task
    async def periodic_sync():
        while True:
            await engine.sync_all_sources(hours=24)
            await asyncio.sleep(300)  # Every 5 minutes

    asyncio.create_task(periodic_sync())
    app.run()
```

### Phase 4: Entity Resolution (Session 2)

```python
# universal-context-engine/core/entity_resolver.py
from typing import List, Dict, Set
from collections import defaultdict
import re

class EntityResolver:
    """Resolve and link entities across context sources"""

    def __init__(self):
        # Alias mappings
        self.aliases: Dict[str, str] = {
            "ke": "Knowledge Engine",
            "knowledge-engine": "Knowledge Engine",
            "oauth2": "OAuth",
            "oauth 2.0": "OAuth",
            "jwt": "JWT",
            "json web token": "JWT",
            "cc": "Claude Code",
            "claude-code": "Claude Code",
        }

        # Entity type mappings
        self.entity_types: Dict[str, str] = {
            "Knowledge Engine": "system",
            "OAuth": "technology",
            "JWT": "technology",
            "Claude Code": "tool",
            "Qdrant": "system",
            "LocalCrew": "system",
        }

    def normalize(self, entity: str) -> str:
        """Normalize entity to canonical form"""
        lower = entity.lower().strip()
        return self.aliases.get(lower, entity.title())

    def extract_entities(self, text: str) -> List[str]:
        """Extract entities from text"""
        entities = set()

        # Known entity patterns
        known_patterns = [
            r'\b(Knowledge Engine|OAuth|JWT|GraphRAG|Qdrant|Claude Code|LocalCrew|Dify|Langfuse)\b',
            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b',  # Title Case phrases
        ]

        for pattern in known_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                entities.add(self.normalize(match))

        return list(entities)

    def find_related(self, entity: str, context_items: List) -> List:
        """Find context items related to an entity"""
        normalized = self.normalize(entity)

        related = []
        for item in context_items:
            if normalized in item.entities:
                related.append(item)
            elif normalized.lower() in item.content.lower():
                related.append(item)

        return related

    def build_entity_graph(self, context_items: List) -> Dict:
        """Build graph of entity co-occurrences"""
        co_occurrences = defaultdict(lambda: defaultdict(int))

        for item in context_items:
            entities = item.entities
            for i, e1 in enumerate(entities):
                for e2 in entities[i+1:]:
                    co_occurrences[e1][e2] += 1
                    co_occurrences[e2][e1] += 1

        return dict(co_occurrences)
```

---

## Integration with Other Projects

| Project | Integration |
|---------|-------------|
| **AI Command Center** (Project 1) | Routes context-enriched prompts |
| **Personal Context Layer** (Project 2) | Individual MCP servers feed into UCE |
| **Autonomous Automation** (Project 3) | n8n workflows can query UCE |
| **Visual Knowledge Platform** (Project 4) | Dify uses UCE for enhanced retrieval |
| **Knowledge Graph Layer** (Project 5) | GraphRAG entities merged into UCE |
| **Self-Improving Agents** (Project 6) | Training data enriched with context |
| **AI Operations Dashboard** (Project 8) | Langfuse traces indexed in UCE |
| **AI-Native Dev** (Project 10) | Development context always available |

---

## Configuration

### MCP Configuration

```json
// ~/.claude.json addition
{
  "mcpServers": {
    "universal-context": {
      "command": "python",
      "args": ["-m", "universal_context_engine.mcp_server"],
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "KNOWLEDGE_ENGINE_URL": "http://localhost:8000",
        "LANGFUSE_URL": "http://localhost:3001"
      }
    }
  }
}
```

### Sync Schedule

```yaml
# universal-context-engine/config.yaml
sync:
  default_interval_minutes: 5

  sources:
    knowledge_engine:
      interval_minutes: 30
      full_sync_hours: 168  # Weekly

    mcp_git:
      interval_minutes: 2
      on_change: true

    localcrew:
      interval_minutes: 5

    browser:
      interval_minutes: 1
      expires_hours: 4

    obsidian:
      interval_minutes: 15

    graphrag:
      interval_minutes: 60
```

---

## Builds On Existing

| Component | Location | Status |
|-----------|----------|--------|
| Knowledge Engine | ~/claude-code/personal/knowledge-engine | In progress |
| Qdrant | Via Knowledge Engine | Running |
| nomic-embed-text | Ollama model | Loaded |
| LocalCrew | ~/claude-code/personal/crewai-automation-platform | Working |
| MCP Servers | ~/.claude.json | Configured |

---

## Success Criteria

1. **Core Engine Running**: Can ingest and search context items
2. **Adapters Connected**: At least 4 sources feeding data
3. **MCP Server Active**: Claude Code can query unified context
4. **Entity Resolution**: Same concept linked across sources
5. **Temporal Queries**: "What was I working on?" returns relevant results
6. **Cross-Source Search**: Single query searches all sources

# Knowledge Seeder CLI - Implementation Plan

## Executive Summary

The Knowledge Seeder is a command-line tool that systematically ingests curated knowledge sources into the Knowledge Engine. It transforms scattered documentation, blogs, videos, and repositories into a queryable knowledge base that powers downstream AI applications.

**Critical Design Principle**: This tool must be idempotent, resumable, and auditable. A 30-year veteran knows that data pipelines fail, networks drop, and APIs rate-limit. Design for failure from day one.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Knowledge Seeder CLI                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │   Source    │───▶│   Content   │───▶│  Ingestion  │                │
│  │   Manager   │    │  Extractor  │    │   Client    │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│         │                 │                   │                        │
│         │                 │                   │                        │
│  ┌──────▼─────────────────▼───────────────────▼──────┐                │
│  │                    State Manager                   │                │
│  │  (SQLite: tracks ingested, failed, pending)       │                │
│  └────────────────────────────────────────────────────┘                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ HTTP POST /v1/ingest/source
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Knowledge Engine API                             │
│                   (http://localhost:8000)                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Design Decisions (Senior Engineer Perspective)

### Why SQLite for State?

**Decision**: Use SQLite for ingestion state tracking, not a YAML/JSON file.

**Rationale**:
1. **Atomic writes** - No corruption on crash mid-write
2. **Query capability** - "Show me all failed URLs from yesterday"
3. **Concurrent access** - Multiple seeder processes won't corrupt state
4. **Resume capability** - Know exactly where you stopped

**Anti-pattern avoided**: Storing state in flat files that grow unbounded and require full reads.

### Why Namespace-per-Domain?

**Decision**: Each knowledge domain gets its own namespace in Knowledge Engine.

**Rationale**:
1. **Isolation** - RAG queries can target specific domains
2. **Garbage collection** - Delete entire domain without touching others
3. **Multi-project support** - Voice AI project queries `voice-ai` namespace only
4. **Access patterns** - Common case is "search within domain X"

**Namespaces planned**:
- `frameworks` - LangGraph, LlamaIndex, Pipecat, etc.
- `ai-research` - arXiv papers, research blogs
- `tools` - Qdrant, Ollama, MLX documentation
- `tutorials` - YouTube transcripts, how-to guides
- `best-practices` - Prompt engineering, RAG patterns

### Why Batch with Throttling?

**Decision**: Process sources in controlled batches with configurable rate limiting.

**Rationale**:
1. **Rate limits** - YouTube transcript API has limits
2. **Memory** - Don't OOM on 1000 sources
3. **Observability** - Progress is visible per batch
4. **Resumability** - Commit state after each batch

---

## Project Structure

```
knowledge-seeder/
├── src/
│   └── knowledge_seeder/
│       ├── __init__.py
│       ├── cli.py                 # Click CLI entry point
│       ├── config.py              # Configuration management
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── loader.py          # Load sources from YAML
│       │   ├── validator.py       # Validate URLs/sources
│       │   └── discovery.py       # Discover new sources (RSS, sitemap)
│       ├── ingest/
│       │   ├── __init__.py
│       │   ├── client.py          # Knowledge Engine API client
│       │   ├── batch.py           # Batch processing logic
│       │   └── retry.py           # Retry with exponential backoff
│       ├── state/
│       │   ├── __init__.py
│       │   ├── database.py        # SQLite state management
│       │   └── models.py          # State data models
│       └── reports/
│           ├── __init__.py
│           └── summary.py         # Ingestion summary reports
├── sources/                       # Curated source definitions
│   ├── frameworks.yaml
│   ├── ai-research.yaml
│   ├── tools.yaml
│   ├── tutorials.yaml
│   └── best-practices.yaml
├── tests/
│   ├── test_sources.py
│   ├── test_ingest.py
│   └── test_state.py
├── pyproject.toml
└── README.md
```

---

## Implementation Phases

### Phase 1: Core Infrastructure (Days 1-2)

#### 1.1 State Database Schema

```python
# src/knowledge_seeder/state/database.py
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from contextlib import contextmanager

class SourceStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class SourceRecord:
    id: int
    source_url: str
    source_type: str  # url, youtube, github
    namespace: str
    category: str
    status: SourceStatus
    document_id: Optional[str]  # UUID from Knowledge Engine
    chunk_count: Optional[int]
    error_message: Optional[str]
    attempt_count: int
    created_at: datetime
    updated_at: datetime
    last_ingested_at: Optional[datetime]

class StateDatabase:
    """
    SQLite-backed state management for ingestion tracking.

    Design principles:
    - Idempotent operations (safe to re-run)
    - Atomic state transitions
    - Full audit trail
    """

    def __init__(self, db_path: Path = Path("~/.knowledge-seeder/state.db").expanduser()):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT UNIQUE NOT NULL,
                    source_type TEXT NOT NULL,
                    namespace TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    document_id TEXT,
                    chunk_count INTEGER,
                    error_message TEXT,
                    attempt_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_ingested_at DATETIME
                );

                CREATE TABLE IF NOT EXISTS ingestion_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    sources_attempted INTEGER DEFAULT 0,
                    sources_succeeded INTEGER DEFAULT 0,
                    sources_failed INTEGER DEFAULT 0,
                    namespace_filter TEXT,
                    category_filter TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
                CREATE INDEX IF NOT EXISTS idx_sources_namespace ON sources(namespace);
                CREATE INDEX IF NOT EXISTS idx_sources_category ON sources(category);
            ''')

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add_source(
        self,
        source_url: str,
        source_type: str,
        namespace: str,
        category: str
    ) -> bool:
        """
        Add a source to track. Idempotent - safe to call multiple times.

        Returns True if new, False if already exists.
        """
        with self._get_connection() as conn:
            try:
                conn.execute(
                    '''INSERT INTO sources (source_url, source_type, namespace, category)
                       VALUES (?, ?, ?, ?)''',
                    (source_url, source_type, namespace, category)
                )
                return True
            except sqlite3.IntegrityError:
                # Already exists
                return False

    def get_pending_sources(
        self,
        namespace: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100
    ) -> list[SourceRecord]:
        """Get sources that need ingestion."""
        with self._get_connection() as conn:
            query = "SELECT * FROM sources WHERE status IN ('pending', 'failed')"
            params = []

            if namespace:
                query += " AND namespace = ?"
                params.append(namespace)
            if category:
                query += " AND category = ?"
                params.append(category)

            # Prioritize pending over failed, then by least attempts
            query += " ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, attempt_count ASC"
            query += f" LIMIT {limit}"

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_record(row) for row in rows]

    def mark_in_progress(self, source_url: str):
        """Mark source as being processed."""
        with self._get_connection() as conn:
            conn.execute(
                '''UPDATE sources
                   SET status = 'in_progress',
                       updated_at = CURRENT_TIMESTAMP,
                       attempt_count = attempt_count + 1
                   WHERE source_url = ?''',
                (source_url,)
            )

    def mark_completed(
        self,
        source_url: str,
        document_id: str,
        chunk_count: int
    ):
        """Mark source as successfully ingested."""
        with self._get_connection() as conn:
            conn.execute(
                '''UPDATE sources
                   SET status = 'completed',
                       document_id = ?,
                       chunk_count = ?,
                       error_message = NULL,
                       updated_at = CURRENT_TIMESTAMP,
                       last_ingested_at = CURRENT_TIMESTAMP
                   WHERE source_url = ?''',
                (document_id, chunk_count, source_url)
            )

    def mark_failed(self, source_url: str, error: str):
        """Mark source as failed with error message."""
        with self._get_connection() as conn:
            conn.execute(
                '''UPDATE sources
                   SET status = 'failed',
                       error_message = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE source_url = ?''',
                (error, source_url)
            )

    def get_statistics(self, namespace: Optional[str] = None) -> dict:
        """Get ingestion statistics."""
        with self._get_connection() as conn:
            base_query = "SELECT status, COUNT(*) as count FROM sources"
            params = []

            if namespace:
                base_query += " WHERE namespace = ?"
                params.append(namespace)

            base_query += " GROUP BY status"

            rows = conn.execute(base_query, params).fetchall()
            return {row["status"]: row["count"] for row in rows}

    def _row_to_record(self, row) -> SourceRecord:
        return SourceRecord(
            id=row["id"],
            source_url=row["source_url"],
            source_type=row["source_type"],
            namespace=row["namespace"],
            category=row["category"],
            status=SourceStatus(row["status"]),
            document_id=row["document_id"],
            chunk_count=row["chunk_count"],
            error_message=row["error_message"],
            attempt_count=row["attempt_count"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_ingested_at=datetime.fromisoformat(row["last_ingested_at"]) if row["last_ingested_at"] else None
        )
```

#### 1.2 Configuration Management

```python
# src/knowledge_seeder/config.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml

@dataclass
class SeederConfig:
    """Configuration for the Knowledge Seeder."""

    # Knowledge Engine connection
    knowledge_engine_url: str = "http://localhost:8000"
    api_timeout: int = 120  # seconds

    # Rate limiting
    requests_per_minute: int = 30  # Be nice to APIs
    batch_size: int = 10  # Process in batches

    # Retry settings
    max_retries: int = 3
    retry_backoff_factor: float = 2.0  # Exponential backoff

    # Storage
    state_db_path: Path = field(default_factory=lambda: Path("~/.knowledge-seeder/state.db").expanduser())
    sources_dir: Path = field(default_factory=lambda: Path("sources"))

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None

    @classmethod
    def from_file(cls, path: Path) -> "SeederConfig":
        """Load config from YAML file."""
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            return cls(**data)
        return cls()

    def to_file(self, path: Path):
        """Save config to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.dump(self.__dict__, f, default_flow_style=False)
```

### Phase 2: Source Management (Day 2-3)

#### 2.1 Source Definition Schema

```yaml
# sources/frameworks.yaml
---
namespace: frameworks
description: AI/ML framework documentation and guides
categories:
  langgraph:
    description: LangGraph agent orchestration framework
    sources:
      - url: https://langchain-ai.github.io/langgraph/
        type: url
        title: LangGraph Documentation
        priority: high
      - url: https://langchain-ai.github.io/langgraph/concepts/
        type: url
        title: LangGraph Concepts
        priority: high
      - url: https://langchain-ai.github.io/langgraph/tutorials/
        type: url
        title: LangGraph Tutorials
        priority: high
      - url: https://www.youtube.com/watch?v=9BPCV5TYWmg
        type: youtube
        title: "LangGraph Tutorial: Building Agents"
        priority: medium

  llamaindex:
    description: LlamaIndex RAG framework
    sources:
      - url: https://docs.llamaindex.ai/en/stable/
        type: url
        title: LlamaIndex Documentation
        priority: high
      - url: https://docs.llamaindex.ai/en/stable/getting_started/concepts/
        type: url
        title: LlamaIndex Concepts
        priority: high

  pipecat:
    description: Pipecat voice AI framework
    sources:
      - url: https://docs.pipecat.ai/getting-started/introduction
        type: url
        title: Pipecat Introduction
        priority: high
      - url: https://docs.pipecat.ai/getting-started/quickstart
        type: url
        title: Pipecat Quickstart
        priority: high
```

#### 2.2 Source Loader

```python
# src/knowledge_seeder/sources/loader.py
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator
import yaml
import re

@dataclass
class Source:
    url: str
    source_type: str  # url, youtube, github, file
    namespace: str
    category: str
    title: str
    priority: str  # high, medium, low
    tags: list[str]

class SourceLoader:
    """
    Load and validate source definitions from YAML files.

    Design: Sources are defined declaratively in YAML, not code.
    This allows non-developers to curate sources.
    """

    def __init__(self, sources_dir: Path):
        self.sources_dir = sources_dir

    def load_all(self) -> Iterator[Source]:
        """Load all sources from all YAML files."""
        for yaml_file in self.sources_dir.glob("*.yaml"):
            yield from self.load_file(yaml_file)

    def load_file(self, path: Path) -> Iterator[Source]:
        """Load sources from a single YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        namespace = data.get("namespace", path.stem)

        for category_name, category_data in data.get("categories", {}).items():
            for source_def in category_data.get("sources", []):
                yield self._parse_source(
                    source_def,
                    namespace=namespace,
                    category=category_name
                )

    def load_namespace(self, namespace: str) -> Iterator[Source]:
        """Load sources for a specific namespace."""
        yaml_file = self.sources_dir / f"{namespace}.yaml"
        if yaml_file.exists():
            yield from self.load_file(yaml_file)

    def _parse_source(
        self,
        source_def: dict,
        namespace: str,
        category: str
    ) -> Source:
        """Parse a source definition into a Source object."""
        url = source_def["url"]
        source_type = source_def.get("type", self._detect_type(url))

        return Source(
            url=url,
            source_type=source_type,
            namespace=namespace,
            category=category,
            title=source_def.get("title", ""),
            priority=source_def.get("priority", "medium"),
            tags=source_def.get("tags", [])
        )

    def _detect_type(self, url: str) -> str:
        """Auto-detect source type from URL."""
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        if "github.com" in url:
            return "github"
        if url.startswith("http"):
            return "url"
        return "file"
```

### Phase 3: Ingestion Client (Day 3-4)

#### 3.1 Knowledge Engine Client

```python
# src/knowledge_seeder/ingest/client.py
import httpx
import asyncio
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class IngestResult:
    success: bool
    document_id: Optional[str] = None
    chunk_count: Optional[int] = None
    error: Optional[str] = None

class KnowledgeEngineClient:
    """
    Async client for Knowledge Engine ingestion API.

    Design principles:
    - Async for concurrent ingestion
    - Proper connection pooling
    - Graceful error handling
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 120
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_connections=10)
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> bool:
        """Check if Knowledge Engine is available."""
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def ingest_source(
        self,
        source: str,
        namespace: str,
        tags: Optional[list[str]] = None
    ) -> IngestResult:
        """
        Ingest a source into the Knowledge Engine.

        Maps directly to: POST /v1/ingest/source
        """
        try:
            response = await self._client.post(
                "/v1/ingest/source",
                json={
                    "source": source,
                    "namespace": namespace,
                    "tags": tags or []
                }
            )

            if response.status_code == 200:
                data = response.json()
                return IngestResult(
                    success=True,
                    document_id=data.get("document_id"),
                    chunk_count=data.get("chunk_count")
                )
            else:
                error_detail = response.json().get("detail", response.text)
                return IngestResult(success=False, error=error_detail)

        except httpx.TimeoutException:
            return IngestResult(success=False, error="Request timed out")
        except Exception as e:
            return IngestResult(success=False, error=str(e))

    async def detect_source_type(self, source: str) -> Optional[str]:
        """Detect source type without ingesting."""
        try:
            response = await self._client.get(
                "/v1/ingest/detect",
                params={"source": source}
            )
            if response.status_code == 200:
                return response.json().get("type")
        except Exception:
            pass
        return None
```

#### 3.2 Batch Processing with Rate Limiting

```python
# src/knowledge_seeder/ingest/batch.py
import asyncio
from dataclasses import dataclass
from typing import Callable, Optional
import logging
import time

from knowledge_seeder.sources.loader import Source
from knowledge_seeder.ingest.client import KnowledgeEngineClient, IngestResult
from knowledge_seeder.state.database import StateDatabase

logger = logging.getLogger(__name__)

@dataclass
class BatchResult:
    total: int
    succeeded: int
    failed: int
    skipped: int
    duration_seconds: float

class BatchIngester:
    """
    Process sources in controlled batches with rate limiting.

    Design:
    - Process in batches for memory efficiency
    - Rate limit to respect API limits
    - Commit state after each batch for resumability
    """

    def __init__(
        self,
        client: KnowledgeEngineClient,
        state_db: StateDatabase,
        requests_per_minute: int = 30,
        batch_size: int = 10,
        on_progress: Optional[Callable[[int, int], None]] = None
    ):
        self.client = client
        self.state_db = state_db
        self.requests_per_minute = requests_per_minute
        self.batch_size = batch_size
        self.on_progress = on_progress
        self._delay = 60.0 / requests_per_minute  # Seconds between requests

    async def ingest_pending(
        self,
        namespace: Optional[str] = None,
        category: Optional[str] = None,
        max_sources: Optional[int] = None
    ) -> BatchResult:
        """
        Ingest all pending sources matching filters.

        Returns aggregate results.
        """
        start_time = time.time()
        total = 0
        succeeded = 0
        failed = 0
        skipped = 0

        while True:
            # Get next batch of pending sources
            sources = self.state_db.get_pending_sources(
                namespace=namespace,
                category=category,
                limit=self.batch_size
            )

            if not sources:
                break

            if max_sources and total >= max_sources:
                break

            # Process batch
            for source in sources:
                if max_sources and total >= max_sources:
                    break

                total += 1

                # Mark in progress
                self.state_db.mark_in_progress(source.source_url)

                # Ingest
                result = await self.client.ingest_source(
                    source=source.source_url,
                    namespace=source.namespace,
                    tags=[source.category]
                )

                if result.success:
                    self.state_db.mark_completed(
                        source.source_url,
                        result.document_id,
                        result.chunk_count
                    )
                    succeeded += 1
                    logger.info(f"✓ Ingested: {source.source_url} ({result.chunk_count} chunks)")
                else:
                    self.state_db.mark_failed(source.source_url, result.error)
                    failed += 1
                    logger.warning(f"✗ Failed: {source.source_url} - {result.error}")

                # Progress callback
                if self.on_progress:
                    self.on_progress(total, succeeded + failed + skipped)

                # Rate limiting
                await asyncio.sleep(self._delay)

        duration = time.time() - start_time

        return BatchResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration
        )
```

### Phase 4: CLI Interface (Day 4-5)

#### 4.1 Main CLI

```python
# src/knowledge_seeder/cli.py
import asyncio
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from knowledge_seeder.config import SeederConfig
from knowledge_seeder.sources.loader import SourceLoader
from knowledge_seeder.state.database import StateDatabase
from knowledge_seeder.ingest.client import KnowledgeEngineClient
from knowledge_seeder.ingest.batch import BatchIngester

console = Console()

@click.group()
@click.option("--config", "-c", type=Path, default=Path("~/.knowledge-seeder/config.yaml").expanduser())
@click.pass_context
def cli(ctx, config):
    """Knowledge Seeder - Populate your Knowledge Engine with curated sources."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = SeederConfig.from_file(config)

@cli.command()
@click.option("--namespace", "-n", help="Filter by namespace")
@click.option("--category", "-c", help="Filter by category")
@click.pass_context
def sync(ctx, namespace, category):
    """Sync source definitions to state database."""
    config = ctx.obj["config"]

    loader = SourceLoader(config.sources_dir)
    state_db = StateDatabase(config.state_db_path)

    added = 0
    existing = 0

    for source in loader.load_all():
        if namespace and source.namespace != namespace:
            continue
        if category and source.category != category:
            continue

        is_new = state_db.add_source(
            source_url=source.url,
            source_type=source.source_type,
            namespace=source.namespace,
            category=source.category
        )

        if is_new:
            added += 1
        else:
            existing += 1

    console.print(f"[green]✓[/green] Added {added} new sources, {existing} already tracked")

@cli.command()
@click.option("--namespace", "-n", help="Filter by namespace")
@click.option("--category", "-c", help="Filter by category")
@click.option("--limit", "-l", type=int, help="Max sources to ingest")
@click.option("--dry-run", is_flag=True, help="Show what would be ingested")
@click.pass_context
def ingest(ctx, namespace, category, limit, dry_run):
    """Ingest pending sources into Knowledge Engine."""
    config = ctx.obj["config"]
    state_db = StateDatabase(config.state_db_path)

    if dry_run:
        sources = state_db.get_pending_sources(namespace=namespace, category=category, limit=limit or 100)
        console.print(f"\n[bold]Would ingest {len(sources)} sources:[/bold]\n")
        for s in sources[:20]:
            console.print(f"  • {s.source_url}")
        if len(sources) > 20:
            console.print(f"  ... and {len(sources) - 20} more")
        return

    async def run_ingestion():
        async with KnowledgeEngineClient(
            base_url=config.knowledge_engine_url,
            timeout=config.api_timeout
        ) as client:
            # Health check
            if not await client.health_check():
                console.print("[red]✗[/red] Knowledge Engine not available")
                return

            console.print("[green]✓[/green] Knowledge Engine connected")

            ingester = BatchIngester(
                client=client,
                state_db=state_db,
                requests_per_minute=config.requests_per_minute,
                batch_size=config.batch_size
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Ingesting...", total=None)

                result = await ingester.ingest_pending(
                    namespace=namespace,
                    category=category,
                    max_sources=limit
                )

                progress.update(task, completed=True)

            # Summary
            console.print(f"\n[bold]Ingestion Complete[/bold]")
            console.print(f"  Total: {result.total}")
            console.print(f"  [green]Succeeded: {result.succeeded}[/green]")
            console.print(f"  [red]Failed: {result.failed}[/red]")
            console.print(f"  Duration: {result.duration_seconds:.1f}s")

    asyncio.run(run_ingestion())

@cli.command()
@click.option("--namespace", "-n", help="Filter by namespace")
@click.pass_context
def status(ctx, namespace):
    """Show ingestion statistics."""
    config = ctx.obj["config"]
    state_db = StateDatabase(config.state_db_path)

    stats = state_db.get_statistics(namespace=namespace)

    table = Table(title="Ingestion Status")
    table.add_column("Status", style="cyan")
    table.add_column("Count", justify="right")

    total = 0
    for status, count in sorted(stats.items()):
        style = {
            "completed": "green",
            "pending": "yellow",
            "failed": "red",
            "in_progress": "blue"
        }.get(status, "white")
        table.add_row(status, f"[{style}]{count}[/{style}]")
        total += count

    table.add_row("─" * 10, "─" * 5)
    table.add_row("[bold]Total[/bold]", f"[bold]{total}[/bold]")

    console.print(table)

@cli.command()
@click.option("--namespace", "-n", help="Filter by namespace")
@click.option("--limit", "-l", type=int, default=10, help="Max sources to show")
@click.pass_context
def failed(ctx, namespace, limit):
    """Show failed sources with error messages."""
    config = ctx.obj["config"]
    state_db = StateDatabase(config.state_db_path)

    # Get failed sources
    with state_db._get_connection() as conn:
        query = "SELECT * FROM sources WHERE status = 'failed'"
        params = []
        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)
        query += f" ORDER BY updated_at DESC LIMIT {limit}"

        rows = conn.execute(query, params).fetchall()

    if not rows:
        console.print("[green]No failed sources![/green]")
        return

    console.print(f"\n[bold red]Failed Sources ({len(rows)}):[/bold red]\n")
    for row in rows:
        console.print(f"  [cyan]{row['source_url']}[/cyan]")
        console.print(f"    Error: {row['error_message']}")
        console.print(f"    Attempts: {row['attempt_count']}")
        console.print()

@cli.command()
@click.argument("url")
@click.option("--namespace", "-n", default="default", help="Target namespace")
@click.pass_context
def add(ctx, url, namespace):
    """Manually add a single source and ingest it."""
    config = ctx.obj["config"]
    state_db = StateDatabase(config.state_db_path)

    # Add to state
    state_db.add_source(
        source_url=url,
        source_type="auto",
        namespace=namespace,
        category="manual"
    )

    console.print(f"[green]✓[/green] Added: {url}")
    console.print(f"  Run 'knowledge-seeder ingest' to ingest it")

if __name__ == "__main__":
    cli()
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_state.py
import pytest
from pathlib import Path
import tempfile

from knowledge_seeder.state.database import StateDatabase, SourceStatus

@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield StateDatabase(db_path)

def test_add_source_idempotent(temp_db):
    """Adding same source twice should not raise."""
    result1 = temp_db.add_source("https://example.com", "url", "test", "cat")
    result2 = temp_db.add_source("https://example.com", "url", "test", "cat")

    assert result1 == True  # First add
    assert result2 == False  # Already exists

def test_state_transitions(temp_db):
    """Test source status transitions."""
    temp_db.add_source("https://example.com", "url", "test", "cat")

    # Initial state
    sources = temp_db.get_pending_sources()
    assert len(sources) == 1
    assert sources[0].status == SourceStatus.PENDING

    # Mark in progress
    temp_db.mark_in_progress("https://example.com")

    # Mark completed
    temp_db.mark_completed("https://example.com", "doc-123", 10)

    # Should no longer be pending
    sources = temp_db.get_pending_sources()
    assert len(sources) == 0
```

### Integration Tests

```python
# tests/test_ingest.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from knowledge_seeder.ingest.client import KnowledgeEngineClient, IngestResult

@pytest.mark.asyncio
async def test_client_handles_timeout():
    """Client should gracefully handle timeouts."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post.side_effect = asyncio.TimeoutError()

        async with KnowledgeEngineClient() as client:
            client._client = mock_client.return_value.__aenter__.return_value
            result = await client.ingest_source("https://example.com", "test")

            assert result.success == False
            assert "timeout" in result.error.lower()
```

---

## Deployment

### pyproject.toml

```toml
[project]
name = "knowledge-seeder"
version = "0.1.0"
description = "CLI tool to seed the Knowledge Engine with curated sources"
requires-python = ">=3.10"
dependencies = [
    "click>=8.0",
    "httpx>=0.25",
    "pyyaml>=6.0",
    "rich>=13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
]

[project.scripts]
knowledge-seeder = "knowledge_seeder.cli:cli"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Timeline

| Day | Task |
|-----|------|
| Day 1 | State database + configuration |
| Day 2 | Source loader + YAML schema |
| Day 3 | Knowledge Engine client |
| Day 4 | Batch processing + rate limiting |
| Day 5 | CLI interface + testing |

**Total: 5 days**

---

## Senior Engineer Retrospective

### What This Design Gets Right

1. **Idempotency** - Every operation is safe to retry
2. **Observability** - Full audit trail in SQLite
3. **Resumability** - Crash anywhere, pick up where you left off
4. **Rate limiting** - Won't hammer the Knowledge Engine or external APIs
5. **Separation of concerns** - YAML for sources, code for logic

### What To Watch For

1. **Source YAML sprawl** - Keep categories focused, don't dump everything
2. **Stale content** - Plan for periodic re-ingestion of fast-changing sources
3. **Error accumulation** - Monitor failed sources, investigate patterns
4. **Knowledge Engine changes** - API may evolve, keep client loosely coupled

### Future Enhancements (Defer for Now)

1. **RSS/Atom feed support** - Auto-discover new blog posts
2. **GitHub release tracking** - Ingest new documentation versions
3. **Scheduled runs** - Cron-based refresh of sources
4. **Web UI** - Dashboard for managing sources

"""SQLite state manager for tracking source ingestion status."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from knowledge_seeder.config import get_settings
from knowledge_seeder.models import SourceState, SourceStatus, SourceType


def utcnow() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class StateManager:
    """Manages source state in SQLite database."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize state manager."""
        self.db_path = db_path or get_settings().state_db_path
        self._db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to the database and ensure schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._create_schema()

    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> "StateManager":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def _create_schema(self) -> None:
        """Create database schema if it doesn't exist."""
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sources (
                source_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                namespace TEXT NOT NULL,
                source_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',

                -- Extraction state
                content_hash TEXT,
                content_length INTEGER,
                extracted_at TEXT,

                -- Ingestion state
                document_id TEXT,
                chunk_count INTEGER,
                ingested_at TEXT,

                -- Error tracking
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                last_attempt TEXT,

                -- Timestamps
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sources_namespace ON sources(namespace);
            CREATE INDEX IF NOT EXISTS idx_sources_status ON sources(status);
            CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);

            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                namespace TEXT NOT NULL,
                sources_total INTEGER NOT NULL,
                sources_new INTEGER NOT NULL,
                sources_updated INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL DEFAULT 'running'
            );
        """)
        await self._db.commit()

    # --- Source CRUD Operations ---

    async def get_source(self, source_id: str) -> SourceState | None:
        """Get a source by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM sources WHERE source_id = ?",
            (source_id,)
        )
        row = await cursor.fetchone()
        if row:
            return self._row_to_state(row)
        return None

    async def get_source_by_url(self, url: str) -> SourceState | None:
        """Get a source by URL."""
        cursor = await self._db.execute(
            "SELECT * FROM sources WHERE url = ?",
            (url,)
        )
        row = await cursor.fetchone()
        if row:
            return self._row_to_state(row)
        return None

    async def upsert_source(self, state: SourceState) -> None:
        """Insert or update a source."""
        state.updated_at = utcnow()
        await self._db.execute("""
            INSERT INTO sources (
                source_id, name, url, namespace, source_type, status,
                content_hash, content_length, extracted_at,
                document_id, chunk_count, ingested_at,
                error_message, retry_count, last_attempt,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                name = excluded.name,
                url = excluded.url,
                namespace = excluded.namespace,
                source_type = excluded.source_type,
                status = excluded.status,
                content_hash = excluded.content_hash,
                content_length = excluded.content_length,
                extracted_at = excluded.extracted_at,
                document_id = excluded.document_id,
                chunk_count = excluded.chunk_count,
                ingested_at = excluded.ingested_at,
                error_message = excluded.error_message,
                retry_count = excluded.retry_count,
                last_attempt = excluded.last_attempt,
                updated_at = excluded.updated_at
        """, (
            state.source_id,
            state.name,
            state.url,
            state.namespace,
            state.source_type.value,
            state.status.value,
            state.content_hash,
            state.content_length,
            state.extracted_at.isoformat() if state.extracted_at else None,
            state.document_id,
            state.chunk_count,
            state.ingested_at.isoformat() if state.ingested_at else None,
            state.error_message,
            state.retry_count,
            state.last_attempt.isoformat() if state.last_attempt else None,
            state.created_at.isoformat(),
            state.updated_at.isoformat(),
        ))
        await self._db.commit()

    async def update_status(
        self,
        source_id: str,
        status: SourceStatus,
        error_message: str | None = None,
    ) -> None:
        """Update source status."""
        now = utcnow().isoformat()
        await self._db.execute("""
            UPDATE sources
            SET status = ?, error_message = ?, last_attempt = ?, updated_at = ?
            WHERE source_id = ?
        """, (status.value, error_message, now, now, source_id))
        await self._db.commit()

    async def mark_extracted(
        self,
        source_id: str,
        content_hash: str,
        content_length: int,
    ) -> None:
        """Mark source as extracted."""
        now = utcnow().isoformat()
        await self._db.execute("""
            UPDATE sources
            SET status = ?, content_hash = ?, content_length = ?,
                extracted_at = ?, updated_at = ?
            WHERE source_id = ?
        """, (
            SourceStatus.EXTRACTED.value,
            content_hash,
            content_length,
            now,
            now,
            source_id,
        ))
        await self._db.commit()

    async def mark_completed(
        self,
        source_id: str,
        document_id: str,
        chunk_count: int,
    ) -> None:
        """Mark source as completed (ingested)."""
        now = utcnow().isoformat()
        await self._db.execute("""
            UPDATE sources
            SET status = ?, document_id = ?, chunk_count = ?,
                ingested_at = ?, updated_at = ?
            WHERE source_id = ?
        """, (
            SourceStatus.COMPLETED.value,
            document_id,
            chunk_count,
            now,
            now,
            source_id,
        ))
        await self._db.commit()

    async def mark_failed(self, source_id: str, error: str) -> None:
        """Mark source as failed and increment retry count."""
        now = utcnow().isoformat()
        await self._db.execute("""
            UPDATE sources
            SET status = ?, error_message = ?, retry_count = retry_count + 1,
                last_attempt = ?, updated_at = ?
            WHERE source_id = ?
        """, (SourceStatus.FAILED.value, error, now, now, source_id))
        await self._db.commit()

    # --- Query Operations ---

    async def list_sources(
        self,
        namespace: str | None = None,
        status: SourceStatus | None = None,
        limit: int | None = None,
    ) -> list[SourceState]:
        """List sources with optional filters."""
        query = "SELECT * FROM sources WHERE 1=1"
        params = []

        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_state(row) for row in rows]

    async def iter_sources(
        self,
        namespace: str | None = None,
        status: SourceStatus | None = None,
    ) -> AsyncIterator[SourceState]:
        """Iterate over sources with optional filters."""
        query = "SELECT * FROM sources WHERE 1=1"
        params = []

        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at"

        cursor = await self._db.execute(query, params)
        async for row in cursor:
            yield self._row_to_state(row)

    async def get_pending_sources(
        self,
        namespace: str | None = None,
        limit: int | None = None,
    ) -> list[SourceState]:
        """Get sources pending extraction or ingestion."""
        return await self.list_sources(
            namespace=namespace,
            status=SourceStatus.PENDING,
            limit=limit,
        )

    async def get_failed_sources(
        self,
        namespace: str | None = None,
        max_retries: int = 3,
    ) -> list[SourceState]:
        """Get failed sources that haven't exceeded retry limit."""
        query = """
            SELECT * FROM sources
            WHERE status = ? AND retry_count < ?
        """
        params = [SourceStatus.FAILED.value, max_retries]

        if namespace:
            query += " AND namespace = ?"
            params.append(namespace)

        query += " ORDER BY retry_count ASC, last_attempt ASC"

        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_state(row) for row in rows]

    async def get_extracted_sources(
        self,
        namespace: str | None = None,
    ) -> list[SourceState]:
        """Get sources that have been extracted but not ingested."""
        return await self.list_sources(
            namespace=namespace,
            status=SourceStatus.EXTRACTED,
        )

    # --- Statistics ---

    async def get_stats(self, namespace: str | None = None) -> dict:
        """Get statistics about sources."""
        query = "SELECT status, COUNT(*) as count FROM sources"
        params = []

        if namespace:
            query += " WHERE namespace = ?"
            params.append(namespace)

        query += " GROUP BY status"

        cursor = await self._db.execute(query, params)
        rows = await cursor.fetchall()

        stats = {status.value: 0 for status in SourceStatus}
        for row in rows:
            stats[row["status"]] = row["count"]

        stats["total"] = sum(stats.values())
        return stats

    async def get_namespaces(self) -> list[str]:
        """Get list of all namespaces."""
        cursor = await self._db.execute(
            "SELECT DISTINCT namespace FROM sources ORDER BY namespace"
        )
        rows = await cursor.fetchall()
        return [row["namespace"] for row in rows]

    # --- Utilities ---

    def _row_to_state(self, row: aiosqlite.Row) -> SourceState:
        """Convert database row to SourceState."""
        return SourceState(
            source_id=row["source_id"],
            name=row["name"],
            url=row["url"],
            namespace=row["namespace"],
            source_type=SourceType(row["source_type"]),
            status=SourceStatus(row["status"]),
            content_hash=row["content_hash"],
            content_length=row["content_length"],
            extracted_at=datetime.fromisoformat(row["extracted_at"]) if row["extracted_at"] else None,
            document_id=row["document_id"],
            chunk_count=row["chunk_count"],
            ingested_at=datetime.fromisoformat(row["ingested_at"]) if row["ingested_at"] else None,
            error_message=row["error_message"],
            retry_count=row["retry_count"],
            last_attempt=datetime.fromisoformat(row["last_attempt"]) if row["last_attempt"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

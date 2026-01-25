"""
Sync cursor management for incremental synchronization.
"""

from datetime import datetime

import asyncpg

from ..adapters.base import SyncCursor


class CursorManager:
    """
    Manages sync cursors for incremental synchronization.

    Stores and retrieves cursor state from the database.
    """

    def __init__(self, pg_pool: asyncpg.Pool) -> None:
        """
        Initialize cursor manager.

        Args:
            pg_pool: PostgreSQL connection pool
        """
        self.pg = pg_pool

    async def get_cursor(self, source: str) -> SyncCursor | None:
        """
        Get cursor for a source.

        Args:
            source: Source identifier

        Returns:
            SyncCursor or None if not found
        """
        async with self.pg.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT source, last_sync_cursor, last_sync_at, items_synced
                FROM sync_state
                WHERE source = $1
                """,
                source,
            )

            if row:
                return SyncCursor(
                    source=row["source"],
                    cursor_value=row["last_sync_cursor"],
                    last_sync_at=row["last_sync_at"],
                    items_synced=row["items_synced"] or 0,
                )
        return None

    async def save_cursor(self, cursor: SyncCursor) -> None:
        """
        Save cursor state.

        Args:
            cursor: Cursor to save
        """
        async with self.pg.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sync_state (source, last_sync_cursor, last_sync_at, items_synced, sync_status)
                VALUES ($1, $2, $3, $4, 'idle')
                ON CONFLICT (source)
                DO UPDATE SET
                    last_sync_cursor = $2,
                    last_sync_at = $3,
                    items_synced = $4,
                    sync_status = 'idle',
                    updated_at = NOW()
                """,
                cursor.source,
                cursor.cursor_value,
                cursor.last_sync_at,
                cursor.items_synced,
            )

    async def set_status(
        self,
        source: str,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """
        Update sync status.

        Args:
            source: Source identifier
            status: New status (idle, running, error)
            error_message: Optional error message
        """
        async with self.pg.acquire() as conn:
            if error_message:
                await conn.execute(
                    """
                    UPDATE sync_state
                    SET sync_status = $2, error_message = $3, last_error_at = NOW()
                    WHERE source = $1
                    """,
                    source,
                    status,
                    error_message,
                )
            else:
                await conn.execute(
                    """
                    UPDATE sync_state
                    SET sync_status = $2, error_message = NULL
                    WHERE source = $1
                    """,
                    source,
                    status,
                )

    async def get_all_cursors(self) -> list[SyncCursor]:
        """Get all cursors."""
        async with self.pg.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT source, last_sync_cursor, last_sync_at, items_synced
                FROM sync_state
                WHERE enabled = true
                """
            )

        return [
            SyncCursor(
                source=row["source"],
                cursor_value=row["last_sync_cursor"],
                last_sync_at=row["last_sync_at"],
                items_synced=row["items_synced"] or 0,
            )
            for row in rows
        ]

    async def record_sync_history(
        self,
        source: str,
        started_at: datetime,
        completed_at: datetime | None,
        status: str,
        items_processed: int = 0,
        items_created: int = 0,
        items_updated: int = 0,
        items_skipped: int = 0,
        error_message: str | None = None,
    ) -> None:
        """Record sync run in history."""
        async with self.pg.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO sync_history (
                    source, started_at, completed_at, status,
                    items_processed, items_created, items_updated, items_skipped,
                    error_message
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                source,
                started_at,
                completed_at,
                status,
                items_processed,
                items_created,
                items_updated,
                items_skipped,
                error_message,
            )


__all__ = ["CursorManager"]

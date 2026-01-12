"""Response caching for repeated queries."""

import hashlib
import logging
import sqlite3
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ResponseCache:
    """SQLite-based cache for LLM responses."""

    def __init__(self, cache_dir: str | Path | None = None, ttl_seconds: int = 3600):
        if cache_dir is None:
            cache_dir = Path.home() / ".unified-mlx" / "cache"

        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "response_cache.db"
        self.ttl = ttl_seconds
        self._init_db()
        logger.info(f"Response cache initialized at {self.db_path}")

    def _init_db(self):
        """Initialize the cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache(expires_at)
            """)
            conn.commit()

    def _make_key(self, prompt: str, model: str, **params) -> str:
        """Generate cache key from prompt and parameters."""
        # Include relevant params in key
        key_parts = [prompt, model]
        for k, v in sorted(params.items()):
            if k in ("temperature", "max_tokens", "top_p"):
                key_parts.append(f"{k}:{v}")

        key_str = "|".join(str(p) for p in key_parts)
        return hashlib.sha256(key_str.encode()).hexdigest()[:32]

    def get(self, prompt: str, model: str, **params) -> Optional[str]:
        """Get cached response if available and not expired."""
        key = self._make_key(prompt, model, **params)
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT response FROM cache WHERE key=? AND expires_at > ?",
                (key, now)
            ).fetchone()

            if row is not None:
                logger.debug(f"Cache hit for key {key[:8]}...")
                return row[0]

        return None

    def set(self, prompt: str, model: str, response: str, **params) -> None:
        """Cache a response."""
        key = self._make_key(prompt, model, **params)
        now = time.time()
        expires_at = now + self.ttl

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cache
                   (key, response, model, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, response, model, now, expires_at)
            )
            conn.commit()

        logger.debug(f"Cached response for key {key[:8]}...")

    def clear(self) -> int:
        """Clear all cached responses. Returns count of items cleared."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM cache")
            count = cursor.fetchone()[0]
            conn.execute("DELETE FROM cache")
            conn.commit()

        logger.info(f"Cleared {count} cached responses")
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count of items removed."""
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE expires_at < ?", (now,)
            )
            conn.commit()
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Cleaned up {count} expired cache entries")
        return count

    def stats(self) -> dict:
        """Get cache statistics."""
        now = time.time()

        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            valid = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]

        return {
            "total_entries": total,
            "valid_entries": valid,
            "expired_entries": total - valid,
        }


# Global singleton
response_cache = ResponseCache()

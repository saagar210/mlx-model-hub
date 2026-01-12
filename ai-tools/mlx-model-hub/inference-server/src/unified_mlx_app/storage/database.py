"""SQLite database for conversation persistence."""

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Message:
    """A single message in a conversation."""

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Conversation:
    """A conversation with messages."""

    id: Optional[int] = None
    title: str = "New Conversation"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    model_type: str = "chat"  # chat, vision


class ConversationDB:
    """SQLite database for storing conversations."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            # Default to ~/.unified-mlx/conversations.db
            db_dir = Path.home() / ".unified-mlx"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "conversations.db"

        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    model_type TEXT DEFAULT 'chat',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    messages TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_updated_at
                ON conversations(updated_at DESC)
            """)
            conn.commit()

    def save_conversation(self, conv: Conversation) -> int:
        """Save or update a conversation. Returns the conversation ID."""
        messages_json = json.dumps([
            {"role": m.role, "content": m.content, "timestamp": m.timestamp}
            for m in conv.messages
        ])

        with sqlite3.connect(self.db_path) as conn:
            if conv.id is None:
                cursor = conn.execute(
                    """INSERT INTO conversations
                       (title, model_type, created_at, updated_at, messages)
                       VALUES (?, ?, ?, ?, ?)""",
                    (conv.title, conv.model_type, conv.created_at, time.time(), messages_json)
                )
                conv.id = cursor.lastrowid
            else:
                conn.execute(
                    """UPDATE conversations
                       SET title=?, messages=?, updated_at=?
                       WHERE id=?""",
                    (conv.title, messages_json, time.time(), conv.id)
                )
            conn.commit()

        return conv.id

    def get_conversation(self, conv_id: int) -> Optional[Conversation]:
        """Load a conversation by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM conversations WHERE id=?", (conv_id,)
            ).fetchone()

            if row is None:
                return None

            messages_data = json.loads(row["messages"])
            messages = [
                Message(
                    role=m["role"],
                    content=m["content"],
                    timestamp=m.get("timestamp", 0)
                )
                for m in messages_data
            ]

            return Conversation(
                id=row["id"],
                title=row["title"],
                model_type=row["model_type"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                messages=messages,
            )

    def list_conversations(
        self, limit: int = 50, model_type: str | None = None
    ) -> list[dict]:
        """List recent conversations (metadata only)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if model_type:
                rows = conn.execute(
                    """SELECT id, title, model_type, created_at, updated_at
                       FROM conversations
                       WHERE model_type=?
                       ORDER BY updated_at DESC LIMIT ?""",
                    (model_type, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, title, model_type, created_at, updated_at
                       FROM conversations
                       ORDER BY updated_at DESC LIMIT ?""",
                    (limit,)
                ).fetchall()

            return [dict(row) for row in rows]

    def delete_conversation(self, conv_id: int) -> bool:
        """Delete a conversation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM conversations WHERE id=?", (conv_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def generate_title(self, messages: list[Message]) -> str:
        """Generate a title from the first user message."""
        for msg in messages:
            if msg.role == "user":
                # Take first 50 chars of first user message
                title = msg.content[:50]
                if len(msg.content) > 50:
                    title += "..."
                return title
        return "New Conversation"


# Global singleton
conversation_db = ConversationDB()

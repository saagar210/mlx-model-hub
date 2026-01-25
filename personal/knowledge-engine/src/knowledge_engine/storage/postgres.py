"""PostgreSQL metadata store adapter."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from tenacity import retry, stop_after_attempt, wait_exponential

from knowledge_engine.config import Settings, get_settings

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class DocumentRecord(Base):
    """Document metadata table."""

    __tablename__ = "documents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    namespace = Column(String(255), nullable=False, index=True)
    title = Column(String(1024))
    document_type = Column(String(50), nullable=False, index=True)
    source = Column(Text)
    chunk_count = Column(Integer, default=0)
    embedding_model = Column(String(255))
    extra_metadata = Column(JSONB, default={})

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    is_deleted = Column(Boolean, default=False, index=True)


class ChunkRecord(Base):
    """Document chunk table for BM25 search."""

    __tablename__ = "chunks"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    document_id = Column(PG_UUID(as_uuid=True), nullable=False, index=True)
    namespace = Column(String(255), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    title = Column(String(1024))
    # PostgreSQL full-text search vector - will be populated by trigger
    search_vector = Column(Text)  # tsvector stored as text for simplicity

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)


class MemoryRecord(Base):
    """Memory storage table."""

    __tablename__ = "memories"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    namespace = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    memory_type = Column(String(50), nullable=False, index=True)
    context = Column(Text)
    source = Column(Text)
    importance = Column(Integer, default=50)  # Stored as 0-100
    tags = Column(JSONB, default=[])
    extra_metadata = Column(JSONB, default={})

    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    accessed_at = Column(DateTime(timezone=True))
    access_count = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), index=True)
    is_deleted = Column(Boolean, default=False, index=True)


class AuditLogRecord(Base):
    """Audit log table for compliance."""

    __tablename__ = "audit_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True)
    namespace = Column(String(255), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False)
    resource_id = Column(PG_UUID(as_uuid=True))
    actor = Column(String(255))
    details = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)


class PostgresStore:
    """PostgreSQL metadata store with async support."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize PostgreSQL connection."""
        self._settings = settings or get_settings()
        self._engine = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Establish connection to PostgreSQL."""
        if self._engine is not None:
            return

        self._engine = create_async_engine(
            self._settings.database_url.get_secret_value(),
            pool_size=self._settings.db_pool_size,
            max_overflow=self._settings.db_max_overflow,
            pool_pre_ping=True,
            echo=self._settings.debug,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Create tables if needed
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Connected to PostgreSQL")

    async def close(self) -> None:
        """Close PostgreSQL connection."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Disconnected from PostgreSQL")

    async def _get_session(self) -> AsyncSession:
        """Get a database session."""
        if self._session_factory is None:
            await self.connect()
        assert self._session_factory is not None
        return self._session_factory()

    # Document operations
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def save_document(
        self,
        id: UUID,
        namespace: str,
        title: str | None,
        document_type: str,
        source: str | None = None,
        chunk_count: int = 0,
        embedding_model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Save or update document metadata."""
        async with await self._get_session() as session:
            async with session.begin():
                record = DocumentRecord(
                    id=id,
                    namespace=namespace,
                    title=title,
                    document_type=document_type,
                    source=source,
                    chunk_count=chunk_count,
                    embedding_model=embedding_model,
                    extra_metadata=metadata or {},
                )
                await session.merge(record)

    async def get_document(
        self,
        id: UUID,
        namespace: str = "default",
    ) -> dict[str, Any] | None:
        """Get document metadata by ID."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(DocumentRecord).where(
                    DocumentRecord.id == id,
                    DocumentRecord.namespace == namespace,
                    DocumentRecord.is_deleted == False,  # noqa: E712
                )
            )
            record = result.scalar_one_or_none()
            if record:
                return {
                    "id": record.id,
                    "namespace": record.namespace,
                    "title": record.title,
                    "document_type": record.document_type,
                    "source": record.source,
                    "chunk_count": record.chunk_count,
                    "embedding_model": record.embedding_model,
                    "metadata": record.extra_metadata,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            return None

    async def list_documents(
        self,
        namespace: str = "default",
        document_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List documents with optional filtering."""
        async with await self._get_session() as session:
            query = select(DocumentRecord).where(
                DocumentRecord.namespace == namespace,
                DocumentRecord.is_deleted == False,  # noqa: E712
            )
            if document_type:
                query = query.where(DocumentRecord.document_type == document_type)
            query = query.order_by(DocumentRecord.created_at.desc()).limit(limit).offset(offset)

            result = await session.execute(query)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "namespace": r.namespace,
                    "title": r.title,
                    "document_type": r.document_type,
                    "source": r.source,
                    "chunk_count": r.chunk_count,
                    "created_at": r.created_at,
                }
                for r in records
            ]

    async def delete_document(self, id: UUID, namespace: str = "default") -> bool:
        """Soft delete a document."""
        async with await self._get_session() as session:
            async with session.begin():
                result = await session.execute(
                    update(DocumentRecord)
                    .where(
                        DocumentRecord.id == id,
                        DocumentRecord.namespace == namespace,
                    )
                    .values(is_deleted=True, updated_at=utc_now())
                )
                return result.rowcount > 0

    # Chunk operations for BM25 search
    async def save_chunks(
        self,
        document_id: UUID,
        namespace: str,
        chunks: list[dict[str, Any]],
    ) -> int:
        """Save document chunks for BM25 search."""
        async with await self._get_session() as session:
            async with session.begin():
                for chunk in chunks:
                    record = ChunkRecord(
                        id=chunk["id"],
                        document_id=document_id,
                        namespace=namespace,
                        chunk_index=chunk["chunk_index"],
                        content=chunk["content"],
                        title=chunk.get("title"),
                    )
                    await session.merge(record)
                return len(chunks)

    async def bm25_search(
        self,
        query: str,
        namespace: str = "default",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Perform BM25 full-text search using PostgreSQL.

        Uses plainto_tsquery for simple query parsing.
        """
        async with await self._get_session() as session:
            # Use raw SQL for full-text search with ranking
            from sqlalchemy import text

            sql = text("""
                SELECT
                    id,
                    document_id,
                    chunk_index,
                    content,
                    title,
                    ts_rank(to_tsvector('english', content), plainto_tsquery('english', :query)) as score
                FROM chunks
                WHERE namespace = :namespace
                    AND to_tsvector('english', content) @@ plainto_tsquery('english', :query)
                ORDER BY score DESC
                LIMIT :limit
            """)

            result = await session.execute(
                sql,
                {"query": query, "namespace": namespace, "limit": limit}
            )
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "document_id": str(row.document_id),
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "title": row.title,
                    "score": float(row.score),
                }
                for row in rows
            ]

    # Memory operations
    async def save_memory(
        self,
        id: UUID,
        namespace: str,
        content: str,
        memory_type: str,
        context: str | None = None,
        source: str | None = None,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        """Save a memory."""
        async with await self._get_session() as session:
            async with session.begin():
                record = MemoryRecord(
                    id=id,
                    namespace=namespace,
                    content=content,
                    memory_type=memory_type,
                    context=context,
                    source=source,
                    importance=int(importance * 100),
                    tags=tags or [],
                    extra_metadata=metadata or {},
                    expires_at=expires_at,
                )
                await session.merge(record)

    async def get_memory(self, id: UUID, namespace: str = "default") -> dict[str, Any] | None:
        """Get memory by ID and update access stats."""
        async with await self._get_session() as session:
            async with session.begin():
                result = await session.execute(
                    select(MemoryRecord).where(
                        MemoryRecord.id == id,
                        MemoryRecord.namespace == namespace,
                        MemoryRecord.is_deleted == False,  # noqa: E712
                    )
                )
                record = result.scalar_one_or_none()
                if record:
                    # Update access stats
                    record.accessed_at = utc_now()
                    record.access_count += 1

                    return {
                        "id": record.id,
                        "namespace": record.namespace,
                        "content": record.content,
                        "memory_type": record.memory_type,
                        "context": record.context,
                        "source": record.source,
                        "importance": record.importance / 100.0,
                        "tags": record.tags,
                        "metadata": record.extra_metadata,
                        "created_at": record.created_at,
                        "updated_at": record.updated_at,
                        "accessed_at": record.accessed_at,
                        "access_count": record.access_count,
                    }
                return None

    # Audit operations
    async def log_audit(
        self,
        id: UUID,
        namespace: str,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        actor: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit event."""
        async with await self._get_session() as session:
            async with session.begin():
                record = AuditLogRecord(
                    id=id,
                    namespace=namespace,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    actor=actor,
                    details=details or {},
                )
                session.add(record)

    async def get_audit_logs(
        self,
        namespace: str = "default",
        action: str | None = None,
        resource_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get audit logs with filtering."""
        async with await self._get_session() as session:
            query = select(AuditLogRecord).where(AuditLogRecord.namespace == namespace)
            if action:
                query = query.where(AuditLogRecord.action == action)
            if resource_type:
                query = query.where(AuditLogRecord.resource_type == resource_type)
            query = query.order_by(AuditLogRecord.created_at.desc()).limit(limit)

            result = await session.execute(query)
            records = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "action": r.action,
                    "resource_type": r.resource_type,
                    "resource_id": r.resource_id,
                    "actor": r.actor,
                    "details": r.details,
                    "created_at": r.created_at,
                }
                for r in records
            ]

    async def health_check(self) -> bool:
        """Check PostgreSQL connection health."""
        try:
            async with await self._get_session() as session:
                await session.execute(select(1))
            return True
        except Exception as e:
            logger.error("PostgreSQL health check failed: %s", e)
            return False

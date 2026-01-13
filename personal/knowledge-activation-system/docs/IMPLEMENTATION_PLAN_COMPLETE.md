# KAS Production Readiness - Complete Implementation Plan

**Created:** 2026-01-13
**Scope:** P12-P38 (27 priorities)
**Estimated Total:** ~150-200 implementation tasks

---

## Table of Contents

1. [Execution Strategy](#execution-strategy)
2. [Dependency Graph](#dependency-graph)
3. [Phase 1: Foundation Hardening (P12-P16)](#phase-1-foundation-hardening)
4. [Phase 2: API Maturity (P17-P22)](#phase-2-api-maturity)
5. [Phase 3: Reliability & Observability (P23-P27)](#phase-3-reliability--observability)
6. [Phase 4: Testing & Quality (P28-P32)](#phase-4-testing--quality)
7. [Phase 5: Developer Experience (P33-P36)](#phase-5-developer-experience)
8. [Phase 6: Production Operations (P37-P38)](#phase-6-production-operations)

---

## Execution Strategy

### Recommended Execution Batches

**Batch 1 - Critical Foundation (P12-P15):** ~2-3 sessions
- P12: Connection Pool Management
- P14: Error Handling Standardization
- P15: Logging Infrastructure
- P13: Configuration Externalization

**Batch 2 - Security & Validation (P16-P18):** ~2 sessions
- P16: Input Validation Enhancement
- P17: Authentication System
- P18: Rate Limiting

**Batch 3 - API Features (P19-P22):** ~2 sessions
- P19: API Versioning
- P20: Batch Operations
- P21: Export/Import System
- P22: OpenAPI Documentation

**Batch 4 - Reliability (P23-P27):** ~2-3 sessions
- P23: Health Check Enhancement
- P24: Metrics Collection
- P25: Distributed Tracing
- P26: Circuit Breaker Pattern
- P27: Graceful Degradation

**Batch 5 - Testing (P28-P32):** ~2-3 sessions
- P28: Integration Test Suite
- P29: Load Testing
- P30: Evaluation Framework Enhancement
- P31: Mutation Testing
- P32: Security Testing

**Batch 6 - Developer Experience (P33-P36):** ~2 sessions
- P33: CLI Completeness
- P34: MCP Server Enhancement
- P35: Local Development Setup
- P36: SDK/Client Library

**Batch 7 - Production (P37-P38):** ~1-2 sessions
- P37: Backup & Recovery
- P38: Deployment Automation

### Per-Priority Workflow

For each priority:
1. **Implement** - Write code following the detailed steps
2. **Test** - Run unit tests, add new tests as specified
3. **Review** - Complete the review checklist
4. **Verify** - Run full test suite (`pytest`)
5. **Document** - Update relevant docs if needed
6. **Commit** - Single commit per priority with clear message

---

## Dependency Graph

```
P11 (Done) ─┬─> P12 (Connection Pool)
            │
            └─> P13 (Configuration) ─┬─> P14 (Error Handling)
                                     │
                                     └─> P15 (Logging) ─┬─> P23 (Health Checks)
                                                        │
                                                        └─> P24 (Metrics)
                                                        │
                                                        └─> P25 (Tracing)

P14 (Error Handling) ─┬─> P26 (Circuit Breaker)
                      │
                      └─> P27 (Graceful Degradation)

P16 (Input Validation) ─> P17 (Authentication) ─> P18 (Rate Limiting)

P17 (Authentication) ─> P22 (OpenAPI Docs)

P19 (API Versioning) ─> P20 (Batch Operations)
                    │
                    └─> P21 (Export/Import)

P14 + P15 ─> P28 (Integration Tests) ─> P29 (Load Testing)
                                     │
                                     └─> P30 (Evaluation Framework)

P28 ─> P31 (Mutation Testing)
   │
   └─> P32 (Security Testing)

P20 + P21 ─> P33 (CLI Completeness)
          │
          └─> P34 (MCP Server Enhancement)

P35 (Dev Setup) - Independent
P36 (SDK) - Depends on P17, P22

P37 (Backup) - Independent but after P12
P38 (Deployment) - After P28, P32
```

---

## Phase 1: Foundation Hardening

### P12: Connection Pool Management

**Gap:** No connection pool configuration, potential exhaustion

**Files to Modify:**
- `src/knowledge/db.py`
- `src/knowledge/config.py`

**Implementation Steps:**

1. **Update config.py with pool settings**
   ```python
   # Add to Settings class
   db_pool_min: int = 2
   db_pool_max: int = 10
   db_pool_max_inactive_time: float = 300.0  # 5 minutes
   db_pool_timeout: float = 30.0  # Connection acquire timeout
   db_command_timeout: float = 60.0
   db_retry_attempts: int = 3
   db_retry_delay: float = 1.0
   ```

2. **Enhance Database class in db.py**
   ```python
   # Add connection health check method
   async def _check_connection_health(self, conn: asyncpg.Connection) -> bool:
       try:
           await conn.fetchval("SELECT 1")
           return True
       except Exception:
           return False

   # Add retry logic wrapper
   async def _execute_with_retry(self, operation: Callable, *args, **kwargs):
       for attempt in range(self.settings.db_retry_attempts):
           try:
               return await operation(*args, **kwargs)
           except asyncpg.PostgresConnectionError:
               if attempt < self.settings.db_retry_attempts - 1:
                   await asyncio.sleep(self.settings.db_retry_delay * (attempt + 1))
               else:
                   raise

   # Add pool metrics
   def get_pool_stats(self) -> dict:
       if self._pool is None:
           return {"status": "disconnected"}
       return {
           "size": self._pool.get_size(),
           "free_size": self._pool.get_idle_size(),
           "min_size": self._pool.get_min_size(),
           "max_size": self._pool.get_max_size(),
       }
   ```

3. **Update connect() method**
   ```python
   async def connect(self) -> None:
       if self._pool is not None:
           return
       self._pool = await asyncpg.create_pool(
           self.settings.database_url,
           min_size=self.settings.db_pool_min,
           max_size=self.settings.db_pool_max,
           max_inactive_connection_lifetime=self.settings.db_pool_max_inactive_time,
           command_timeout=self.settings.db_command_timeout,
           init=self._init_connection,
       )
   ```

4. **Add pool stats to health endpoint**
   - Modify `check_health()` to include pool statistics

**Testing Strategy:**

1. **Unit Tests** (`tests/test_db.py`):
   ```python
   class TestConnectionPool:
       async def test_pool_creation_with_settings(self):
           """Test pool respects min/max settings"""

       async def test_pool_stats_when_connected(self):
           """Test get_pool_stats returns correct info"""

       async def test_pool_stats_when_disconnected(self):
           """Test get_pool_stats handles disconnected state"""

       async def test_connection_retry_on_failure(self):
           """Test retry logic with mock failures"""

       async def test_connection_health_check(self):
           """Test health check returns correct status"""
   ```

2. **Integration Tests** (if database available):
   ```python
   async def test_pool_under_concurrent_load(self):
       """Test pool handles concurrent requests"""

   async def test_pool_recovery_after_connection_loss(self):
       """Test pool recovers from transient failures"""
   ```

**Review Checklist:**
- [ ] Pool min/max settings configurable via environment
- [ ] Pool stats exposed in health endpoint
- [ ] Retry logic handles PostgresConnectionError
- [ ] Connection timeout is configurable
- [ ] Idle connections are cleaned up
- [ ] All existing tests pass
- [ ] No hardcoded connection values remain

---

### P13: Configuration Externalization

**Gap:** 10+ hardcoded values (batch sizes, timeouts, limits)

**Files to Create/Modify:**
- `src/knowledge/config.py` (modify)

**Implementation Steps:**

1. **Audit codebase for magic numbers**
   - Search for hardcoded integers, floats, timeouts
   - Document each with file:line reference

2. **Group settings by domain**
   ```python
   class Settings(BaseSettings):
       # Database (existing)
       database_url: str = "..."
       db_pool_min: int = 2
       db_pool_max: int = 10

       # Embedding
       embedding_batch_size: int = 10
       embedding_timeout: float = 30.0
       embedding_max_retries: int = 3

       # Search
       search_default_limit: int = 10
       search_max_limit: int = 100
       bm25_candidates: int = 50
       vector_candidates: int = 50
       rrf_k: int = 60

       # Chunking
       chunk_size_default: int = 512
       chunk_overlap_default: int = 50
       chunk_size_youtube: int = 1000
       chunk_size_bookmark: int = 500

       # Ingestion
       ingest_batch_size: int = 50
       ingest_timeout: float = 120.0
       url_fetch_timeout: float = 30.0

       # Review/FSRS
       review_cards_per_session: int = 20
       review_minimum_interval_hours: int = 4

       # API
       api_request_timeout: float = 30.0
       api_max_request_size: int = 10 * 1024 * 1024  # 10MB
   ```

3. **Add validation**
   ```python
   @model_validator(mode='after')
   def validate_settings(self) -> 'Settings':
       if self.db_pool_min > self.db_pool_max:
           raise ValueError("db_pool_min cannot exceed db_pool_max")
       if self.search_default_limit > self.search_max_limit:
           raise ValueError("search_default_limit cannot exceed search_max_limit")
       return self
   ```

4. **Update all modules to use Settings**
   - Replace hardcoded values with `settings.{name}`
   - Inject settings via dependency injection where possible

**Testing Strategy:**

1. **Unit Tests** (`tests/test_config.py`):
   ```python
   class TestSettings:
       def test_default_values(self):
           """Test all defaults are set correctly"""

       def test_env_override(self, monkeypatch):
           """Test environment variables override defaults"""

       def test_validation_pool_min_max(self):
           """Test pool min > max raises error"""

       def test_validation_search_limits(self):
           """Test search limit validation"""

       def test_settings_cached(self):
           """Test get_settings() returns cached instance"""
   ```

**Review Checklist:**
- [ ] All magic numbers identified and moved to Settings
- [ ] Environment variable names follow KNOWLEDGE_ prefix
- [ ] Validation prevents invalid combinations
- [ ] Default values are sensible for local development
- [ ] Settings are documented with comments
- [ ] All modules use injected settings, not hardcoded values

---

### P14: Error Handling Standardization

**Gap:** Inconsistent error handling across modules

**Files to Create:**
- `src/knowledge/exceptions.py` (new)

**Files to Modify:**
- `src/knowledge/api/main.py`
- `src/knowledge/api/routes/*.py` (all route files)
- `src/knowledge/db.py`
- `src/knowledge/search.py`
- `src/knowledge/embeddings.py`

**Implementation Steps:**

1. **Create exception hierarchy**
   ```python
   # src/knowledge/exceptions.py
   from typing import Any

   class KASError(Exception):
       """Base exception for all KAS errors."""
       error_code: str = "KAS_ERROR"
       status_code: int = 500

       def __init__(self, message: str, details: dict[str, Any] | None = None):
           self.message = message
           self.details = details or {}
           super().__init__(message)

       def to_dict(self) -> dict[str, Any]:
           return {
               "error": self.error_code,
               "message": self.message,
               "details": self.details,
           }

   # Database errors
   class DatabaseError(KASError):
       error_code = "DATABASE_ERROR"
       status_code = 503

   class ConnectionError(DatabaseError):
       error_code = "CONNECTION_ERROR"

   class QueryError(DatabaseError):
       error_code = "QUERY_ERROR"

   # Search errors
   class SearchError(KASError):
       error_code = "SEARCH_ERROR"
       status_code = 500

   class EmbeddingError(SearchError):
       error_code = "EMBEDDING_ERROR"

   class RerankerError(SearchError):
       error_code = "RERANKER_ERROR"

   # Ingestion errors
   class IngestError(KASError):
       error_code = "INGEST_ERROR"
       status_code = 400

   class ContentFetchError(IngestError):
       error_code = "CONTENT_FETCH_ERROR"

   class ChunkingError(IngestError):
       error_code = "CHUNKING_ERROR"

   class DuplicateContentError(IngestError):
       error_code = "DUPLICATE_CONTENT"
       status_code = 409

   # Validation errors
   class ValidationError(KASError):
       error_code = "VALIDATION_ERROR"
       status_code = 400

   # Not found
   class NotFoundError(KASError):
       error_code = "NOT_FOUND"
       status_code = 404

   # Auth errors (for P17)
   class AuthError(KASError):
       error_code = "AUTH_ERROR"
       status_code = 401

   class RateLimitError(KASError):
       error_code = "RATE_LIMIT_EXCEEDED"
       status_code = 429
   ```

2. **Create error response schema**
   ```python
   # src/knowledge/api/schemas.py
   class ErrorResponse(BaseModel):
       error: str
       message: str
       details: dict[str, Any] = {}
       request_id: str | None = None
   ```

3. **Add global exception handler in main.py**
   ```python
   from knowledge.exceptions import KASError

   @app.exception_handler(KASError)
   async def kas_error_handler(request: Request, exc: KASError):
       return JSONResponse(
           status_code=exc.status_code,
           content=exc.to_dict(),
       )

   @app.exception_handler(Exception)
   async def generic_error_handler(request: Request, exc: Exception):
       logger.exception("Unhandled exception", exc_info=exc)
       return JSONResponse(
           status_code=500,
           content={
               "error": "INTERNAL_ERROR",
               "message": "An unexpected error occurred",
               "details": {},
           },
       )
   ```

4. **Update all modules to raise custom exceptions**
   - Replace generic `Exception` with specific `KASError` subclasses
   - Add context to exception details

**Testing Strategy:**

1. **Unit Tests** (`tests/test_exceptions.py`):
   ```python
   class TestExceptions:
       def test_kas_error_to_dict(self):
           """Test error serialization"""

       def test_error_inheritance(self):
           """Test exception hierarchy"""

       def test_error_with_details(self):
           """Test details are preserved"""

       @pytest.mark.parametrize("exc_class,expected_code", [
           (DatabaseError, 503),
           (ValidationError, 400),
           (NotFoundError, 404),
       ])
       def test_status_codes(self, exc_class, expected_code):
           """Test each exception has correct status code"""
   ```

2. **API Tests** (`tests/test_api_errors.py`):
   ```python
   async def test_error_response_format(client):
       """Test error responses follow schema"""

   async def test_not_found_error(client):
       """Test 404 returns proper error format"""

   async def test_validation_error(client):
       """Test validation errors include details"""
   ```

**Review Checklist:**
- [ ] All custom exceptions inherit from KASError
- [ ] Each exception has unique error_code
- [ ] Status codes are appropriate (4xx vs 5xx)
- [ ] Global exception handler catches all KASError
- [ ] Unhandled exceptions return generic 500
- [ ] Error details don't leak sensitive information
- [ ] All routes use custom exceptions

---

### P15: Logging Infrastructure

**Gap:** Minimal logging, no structured format

**Files to Create:**
- `src/knowledge/logging.py` (new, rename existing logging_config.py)

**Files to Modify:**
- `src/knowledge/api/main.py`
- `src/knowledge/api/middleware.py`
- All modules with logging

**Implementation Steps:**

1. **Install structlog**
   ```bash
   # Add to pyproject.toml dependencies
   "structlog>=24.0.0",
   ```

2. **Create logging configuration**
   ```python
   # src/knowledge/logging.py
   import logging
   import sys
   from typing import Any

   import structlog
   from structlog.types import Processor

   def configure_logging(
       level: str = "INFO",
       json_format: bool = True,
       include_request_id: bool = True,
   ) -> None:
       """Configure structured logging for the application."""

       # Shared processors
       shared_processors: list[Processor] = [
           structlog.contextvars.merge_contextvars,
           structlog.processors.add_log_level,
           structlog.processors.TimeStamper(fmt="iso"),
           structlog.processors.StackInfoRenderer(),
       ]

       if json_format:
           # JSON output for production
           renderer = structlog.processors.JSONRenderer()
       else:
           # Pretty output for development
           renderer = structlog.dev.ConsoleRenderer(colors=True)

       structlog.configure(
           processors=[
               *shared_processors,
               structlog.processors.format_exc_info,
               renderer,
           ],
           wrapper_class=structlog.make_filtering_bound_logger(
               getattr(logging, level.upper())
           ),
           context_class=dict,
           logger_factory=structlog.PrintLoggerFactory(),
           cache_logger_on_first_use=True,
       )

       # Configure standard library logging to use structlog
       logging.basicConfig(
           format="%(message)s",
           stream=sys.stdout,
           level=getattr(logging, level.upper()),
       )

   def get_logger(name: str | None = None) -> structlog.BoundLogger:
       """Get a structured logger instance."""
       return structlog.get_logger(name)

   # Context management for request IDs
   from contextvars import ContextVar

   request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

   def bind_request_id(request_id: str) -> None:
       """Bind request ID to logging context."""
       request_id_var.set(request_id)
       structlog.contextvars.bind_contextvars(request_id=request_id)

   def get_request_id() -> str | None:
       """Get current request ID."""
       return request_id_var.get()
   ```

3. **Add request ID middleware**
   ```python
   # src/knowledge/api/middleware.py
   import uuid
   from starlette.middleware.base import BaseHTTPMiddleware
   from knowledge.logging import bind_request_id, get_logger

   logger = get_logger(__name__)

   class RequestIDMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request, call_next):
           request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
           bind_request_id(request_id)

           logger.info(
               "request_started",
               method=request.method,
               path=request.url.path,
           )

           response = await call_next(request)
           response.headers["X-Request-ID"] = request_id

           logger.info(
               "request_completed",
               status_code=response.status_code,
           )

           return response
   ```

4. **Update config for log settings**
   ```python
   # Add to Settings
   log_level: str = "INFO"
   log_format: str = "json"  # or "console"
   log_include_request_id: bool = True
   ```

5. **Replace all logging.getLogger with structured logger**
   ```python
   # Before
   import logging
   logger = logging.getLogger(__name__)
   logger.info("Processing content")

   # After
   from knowledge.logging import get_logger
   logger = get_logger(__name__)
   logger.info("processing_content", content_id=content_id, type=content_type)
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_logging.py`):
   ```python
   class TestLogging:
       def test_configure_json_format(self):
           """Test JSON log format configuration"""

       def test_configure_console_format(self):
           """Test console log format configuration"""

       def test_request_id_binding(self):
           """Test request ID is bound to context"""

       def test_logger_includes_context(self, capsys):
           """Test logs include bound context"""
   ```

2. **Integration Tests**:
   ```python
   async def test_request_id_in_response(client):
       """Test X-Request-ID header in response"""

   async def test_custom_request_id_preserved(client):
       """Test custom X-Request-ID is preserved"""
   ```

**Review Checklist:**
- [ ] structlog configured with JSON format for production
- [ ] Console format available for development
- [ ] Request ID middleware added
- [ ] All modules use structured logger
- [ ] Log level configurable via environment
- [ ] Sensitive data not logged (passwords, tokens)
- [ ] Exception stack traces included

---

### P16: Input Validation Enhancement

**Gap:** Basic validation only, no sanitization

**Files to Modify:**
- `src/knowledge/api/schemas.py`
- `src/knowledge/validation.py`

**Implementation Steps:**

1. **Add Pydantic validators to schemas**
   ```python
   # src/knowledge/api/schemas.py
   from pydantic import BaseModel, Field, field_validator, model_validator
   import re
   from pathlib import Path

   class SearchRequest(BaseModel):
       query: str = Field(..., min_length=1, max_length=1000)
       limit: int = Field(default=10, ge=1, le=100)
       namespace: str | None = Field(default=None, max_length=100)
       rerank: bool = False

       @field_validator("query")
       @classmethod
       def sanitize_query(cls, v: str) -> str:
           # Remove potential SQL injection patterns
           v = re.sub(r"[;'\"]", "", v)
           # Normalize whitespace
           v = " ".join(v.split())
           return v.strip()

       @field_validator("namespace")
       @classmethod
       def validate_namespace(cls, v: str | None) -> str | None:
           if v is None:
               return v
           # Only allow alphanumeric, dash, underscore, asterisk
           if not re.match(r"^[\w\-*]+$", v):
               raise ValueError("Invalid namespace format")
           return v

   class ContentCreate(BaseModel):
       title: str = Field(..., min_length=1, max_length=500)
       content_type: str = Field(..., pattern=r"^(youtube|bookmark|file|note|capture)$")
       url: str | None = Field(default=None, max_length=2000)
       filepath: str = Field(..., max_length=1000)
       tags: list[str] = Field(default_factory=list, max_length=50)

       @field_validator("url")
       @classmethod
       def validate_url(cls, v: str | None) -> str | None:
           if v is None:
               return v
           # Basic URL validation
           if not v.startswith(("http://", "https://")):
               raise ValueError("URL must start with http:// or https://")
           # Block local/private URLs
           blocked_patterns = ["localhost", "127.0.0.1", "0.0.0.0", "192.168.", "10.", "172."]
           if any(p in v.lower() for p in blocked_patterns):
               raise ValueError("Local/private URLs not allowed")
           return v

       @field_validator("filepath")
       @classmethod
       def validate_filepath(cls, v: str) -> str:
           # Prevent path traversal
           if ".." in v or v.startswith("/"):
               raise ValueError("Invalid filepath")
           # Normalize path
           return str(Path(v))

       @field_validator("tags")
       @classmethod
       def validate_tags(cls, v: list[str]) -> list[str]:
           # Sanitize each tag
           return [re.sub(r"[^\w\-]", "", tag)[:50] for tag in v if tag.strip()]
   ```

2. **Add content size limits**
   ```python
   # Add to Settings
   max_content_size: int = 10 * 1024 * 1024  # 10MB
   max_chunk_text_size: int = 10000  # characters
   max_tags_count: int = 50
   max_query_length: int = 1000
   ```

3. **Create validation utilities**
   ```python
   # src/knowledge/validation.py
   import re
   from urllib.parse import urlparse

   def sanitize_sql_string(value: str) -> str:
       """Remove potential SQL injection patterns."""
       # Remove dangerous characters
       return re.sub(r"[;'\"\-\-/*]", "", value)

   def validate_url_safe(url: str) -> bool:
       """Check if URL is safe to fetch."""
       try:
           parsed = urlparse(url)
           # Must have scheme and netloc
           if not parsed.scheme or not parsed.netloc:
               return False
           # Only allow http/https
           if parsed.scheme not in ("http", "https"):
               return False
           # Block private IPs
           # ... (implementation)
           return True
       except Exception:
           return False

   def sanitize_filename(filename: str) -> str:
       """Sanitize filename for safe storage."""
       # Remove path separators
       filename = filename.replace("/", "_").replace("\\", "_")
       # Remove null bytes
       filename = filename.replace("\x00", "")
       # Limit length
       return filename[:255]
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_validation.py`):
   ```python
   class TestInputValidation:
       @pytest.mark.parametrize("query,expected", [
           ("normal query", "normal query"),
           ("query; DROP TABLE", "query DROP TABLE"),
           ("  extra   spaces  ", "extra spaces"),
       ])
       def test_query_sanitization(self, query, expected):
           """Test query sanitization"""

       def test_url_blocks_localhost(self):
           """Test localhost URLs are blocked"""

       def test_filepath_blocks_traversal(self):
           """Test path traversal is blocked"""

       def test_namespace_valid_patterns(self):
           """Test valid namespace patterns"""

       def test_tags_sanitized(self):
           """Test tags are sanitized"""
   ```

2. **API Tests**:
   ```python
   async def test_invalid_query_rejected(client):
       """Test validation errors return 400"""

   async def test_oversized_content_rejected(client):
       """Test content size limits enforced"""
   ```

**Review Checklist:**
- [ ] All string inputs have max_length
- [ ] Numeric inputs have ge/le constraints
- [ ] URLs are validated and sanitized
- [ ] File paths prevent traversal attacks
- [ ] SQL injection patterns removed
- [ ] Content size limits enforced
- [ ] Validation errors return helpful messages

---

## Phase 2: API Maturity

### P17: Authentication System

**Gap:** No authentication, API is open

**Files to Create:**
- `src/knowledge/api/auth.py`
- `src/knowledge/api/routes/auth.py`
- `docker/postgres/migrations/007_api_keys.sql`

**Implementation Steps:**

1. **Create API keys table**
   ```sql
   -- migrations/007_api_keys.sql
   CREATE TABLE api_keys (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       key_hash TEXT NOT NULL UNIQUE,
       name TEXT NOT NULL,
       scopes TEXT[] DEFAULT '{read}',
       rate_limit INTEGER DEFAULT 100,  -- requests per minute
       created_at TIMESTAMPTZ DEFAULT NOW(),
       last_used_at TIMESTAMPTZ,
       expires_at TIMESTAMPTZ,
       revoked_at TIMESTAMPTZ
   );

   CREATE INDEX idx_api_keys_hash ON api_keys(key_hash) WHERE revoked_at IS NULL;
   ```

2. **Create auth module**
   ```python
   # src/knowledge/api/auth.py
   import hashlib
   import secrets
   from datetime import datetime
   from typing import Annotated
   from uuid import UUID

   from fastapi import Depends, Header, HTTPException
   from pydantic import BaseModel

   from knowledge.db import get_db
   from knowledge.exceptions import AuthError

   class APIKey(BaseModel):
       id: UUID
       name: str
       scopes: list[str]
       rate_limit: int

   def generate_api_key() -> tuple[str, str]:
       """Generate new API key and its hash."""
       key = f"kas_{secrets.token_urlsafe(32)}"
       key_hash = hashlib.sha256(key.encode()).hexdigest()
       return key, key_hash

   async def get_api_key(
       x_api_key: Annotated[str | None, Header()] = None,
   ) -> APIKey | None:
       """Validate API key from header."""
       settings = get_settings()

       # If auth not required and no key provided, allow
       if not settings.require_api_key and not x_api_key:
           return None

       # If auth required but no key, reject
       if settings.require_api_key and not x_api_key:
           raise AuthError("API key required")

       if not x_api_key:
           return None

       # Validate key format
       if not x_api_key.startswith("kas_"):
           raise AuthError("Invalid API key format")

       # Hash and lookup
       key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
       db = await get_db()
       async with db.acquire() as conn:
           row = await conn.fetchrow(
               """
               SELECT id, name, scopes, rate_limit
               FROM api_keys
               WHERE key_hash = $1
                 AND revoked_at IS NULL
                 AND (expires_at IS NULL OR expires_at > NOW())
               """,
               key_hash,
           )

           if not row:
               raise AuthError("Invalid or expired API key")

           # Update last used
           await conn.execute(
               "UPDATE api_keys SET last_used_at = NOW() WHERE id = $1",
               row["id"],
           )

           return APIKey(**dict(row))

   def require_scope(scope: str):
       """Dependency to require specific scope."""
       async def check_scope(api_key: APIKey | None = Depends(get_api_key)):
           if api_key is None:
               return  # No auth required
           if scope not in api_key.scopes and "admin" not in api_key.scopes:
               raise AuthError(f"Scope '{scope}' required", details={"required_scope": scope})
           return api_key
       return check_scope
   ```

3. **Create auth routes**
   ```python
   # src/knowledge/api/routes/auth.py
   from fastapi import APIRouter, Depends
   from knowledge.api.auth import generate_api_key, require_scope, APIKey

   router = APIRouter(prefix="/auth", tags=["auth"])

   @router.post("/keys", dependencies=[Depends(require_scope("admin"))])
   async def create_api_key(request: CreateKeyRequest) -> CreateKeyResponse:
       """Create a new API key (admin only)."""
       key, key_hash = generate_api_key()
       # Store in database
       # Return key (only time it's visible)
       return {"key": key, "id": key_id, "name": request.name}

   @router.get("/keys", dependencies=[Depends(require_scope("admin"))])
   async def list_api_keys() -> list[APIKeyInfo]:
       """List all API keys (admin only)."""

   @router.delete("/keys/{key_id}", dependencies=[Depends(require_scope("admin"))])
   async def revoke_api_key(key_id: UUID):
       """Revoke an API key (admin only)."""
   ```

4. **Add auth to routes**
   ```python
   # Example usage in routes
   @router.get("/content/{id}")
   async def get_content(
       id: UUID,
       api_key: APIKey | None = Depends(get_api_key),
   ):
       # api_key is validated if provided

   @router.post("/content")
   async def create_content(
       request: ContentCreate,
       _: None = Depends(require_scope("write")),
   ):
       # Requires write scope
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_auth.py`):
   ```python
   class TestAuth:
       def test_generate_api_key_format(self):
           """Test key format is kas_..."""

       def test_key_hash_consistent(self):
           """Test same key produces same hash"""

       async def test_valid_key_returns_api_key(self):
           """Test valid key is accepted"""

       async def test_invalid_key_raises(self):
           """Test invalid key raises AuthError"""

       async def test_expired_key_rejected(self):
           """Test expired keys are rejected"""

       async def test_revoked_key_rejected(self):
           """Test revoked keys are rejected"""

       async def test_scope_check(self):
           """Test scope validation"""
   ```

2. **API Tests**:
   ```python
   async def test_protected_endpoint_without_key(client):
       """Test 401 when key required but missing"""

   async def test_protected_endpoint_with_valid_key(client):
       """Test access granted with valid key"""
   ```

**Review Checklist:**
- [ ] API keys use secure random generation
- [ ] Keys are stored as hashes only
- [ ] Key format is identifiable (kas_ prefix)
- [ ] Scopes limit access appropriately
- [ ] Expired/revoked keys are rejected
- [ ] Last used timestamp updated
- [ ] Admin-only key management
- [ ] Auth optional for local development

---

### P18: Rate Limiting

**Gap:** No rate limiting, vulnerable to abuse

**Files to Modify:**
- `src/knowledge/api/middleware.py`

**Implementation Steps:**

1. **Implement token bucket algorithm**
   ```python
   # src/knowledge/api/middleware.py
   import asyncio
   from collections import defaultdict
   from dataclasses import dataclass
   from time import time
   from typing import Callable

   from fastapi import Request, Response
   from starlette.middleware.base import BaseHTTPMiddleware

   from knowledge.config import get_settings
   from knowledge.exceptions import RateLimitError

   @dataclass
   class TokenBucket:
       tokens: float
       last_refill: float

   class RateLimiter:
       def __init__(
           self,
           requests_per_minute: int = 100,
           burst_size: int | None = None,
       ):
           self.rate = requests_per_minute / 60.0  # tokens per second
           self.burst_size = burst_size or requests_per_minute
           self.buckets: dict[str, TokenBucket] = defaultdict(
               lambda: TokenBucket(tokens=self.burst_size, last_refill=time())
           )
           self._lock = asyncio.Lock()

       async def acquire(self, key: str) -> tuple[bool, dict]:
           async with self._lock:
               bucket = self.buckets[key]
               now = time()

               # Refill tokens based on elapsed time
               elapsed = now - bucket.last_refill
               bucket.tokens = min(
                   self.burst_size,
                   bucket.tokens + elapsed * self.rate
               )
               bucket.last_refill = now

               # Try to consume a token
               if bucket.tokens >= 1:
                   bucket.tokens -= 1
                   return True, {
                       "remaining": int(bucket.tokens),
                       "limit": self.burst_size,
                       "reset": int(now + (self.burst_size - bucket.tokens) / self.rate),
                   }
               else:
                   return False, {
                       "remaining": 0,
                       "limit": self.burst_size,
                       "reset": int(now + (1 - bucket.tokens) / self.rate),
                   }

   class RateLimitMiddleware(BaseHTTPMiddleware):
       def __init__(self, app, default_limiter: RateLimiter):
           super().__init__(app)
           self.default_limiter = default_limiter
           self.limiters: dict[str, RateLimiter] = {}  # Per-key limiters

       async def dispatch(self, request: Request, call_next: Callable):
           # Skip rate limiting for health checks
           if request.url.path in ("/health", "/ready"):
               return await call_next(request)

           # Get rate limit key (API key or IP)
           api_key = request.headers.get("X-API-Key")
           rate_key = api_key or request.client.host if request.client else "unknown"

           # Get appropriate limiter
           limiter = self.default_limiter
           # Could look up per-key limits from API key

           allowed, info = await limiter.acquire(rate_key)

           if not allowed:
               raise RateLimitError(
                   "Rate limit exceeded",
                   details={"retry_after": info["reset"] - int(time())}
               )

           response = await call_next(request)

           # Add rate limit headers
           response.headers["X-RateLimit-Limit"] = str(info["limit"])
           response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
           response.headers["X-RateLimit-Reset"] = str(info["reset"])

           return response
   ```

2. **Register middleware in main.py**
   ```python
   from knowledge.api.middleware import RateLimitMiddleware, RateLimiter

   settings = get_settings()
   app.add_middleware(
       RateLimitMiddleware,
       default_limiter=RateLimiter(
           requests_per_minute=settings.rate_limit_requests,
           burst_size=settings.rate_limit_requests * 2,
       )
   )
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_rate_limit.py`):
   ```python
   class TestRateLimiter:
       async def test_allows_within_limit(self):
           """Test requests within limit are allowed"""

       async def test_blocks_over_limit(self):
           """Test requests over limit are blocked"""

       async def test_tokens_refill(self):
           """Test tokens refill over time"""

       async def test_burst_handling(self):
           """Test burst requests up to burst_size"""

       async def test_per_key_isolation(self):
           """Test different keys have separate buckets"""
   ```

2. **API Tests**:
   ```python
   async def test_rate_limit_headers_present(client):
       """Test rate limit headers in response"""

   async def test_rate_limit_exceeded_returns_429(client):
       """Test 429 when rate limited"""
   ```

**Review Checklist:**
- [ ] Token bucket algorithm correctly implemented
- [ ] Rate limit headers in all responses
- [ ] 429 returned when limit exceeded
- [ ] Per-API-key rate limits supported
- [ ] Health/ready endpoints exempt
- [ ] Burst handling works correctly
- [ ] Retry-After header included

---

### P19: API Versioning

**Gap:** No versioning strategy

**Files to Modify:**
- `src/knowledge/api/main.py`
- Create `src/knowledge/api/v1/__init__.py`

**Implementation Steps:**

1. **Restructure API routes**
   ```
   src/knowledge/api/
   ├── main.py
   ├── v1/
   │   ├── __init__.py
   │   └── router.py  # Groups all v1 routes
   └── routes/
       ├── search.py
       ├── content.py
       └── ...
   ```

2. **Create version router**
   ```python
   # src/knowledge/api/v1/router.py
   from fastapi import APIRouter

   from knowledge.api.routes import search, content, integration, review, health, auth

   router = APIRouter(prefix="/api/v1")

   router.include_router(search.router)
   router.include_router(content.router)
   router.include_router(integration.router)
   router.include_router(review.router)
   router.include_router(health.router)
   router.include_router(auth.router)
   ```

3. **Update main.py**
   ```python
   from knowledge.api.v1.router import router as v1_router

   app = FastAPI(
       title="Knowledge Activation System",
       version="1.0.0",
   )

   app.include_router(v1_router)

   # Add deprecation middleware for future versions
   @app.middleware("http")
   async def add_api_version_headers(request: Request, call_next):
       response = await call_next(request)
       response.headers["X-API-Version"] = "v1"
       # Future: add deprecation warnings
       return response
   ```

**Testing Strategy:**

1. **Unit Tests**:
   ```python
   async def test_v1_routes_accessible(client):
       """Test /api/v1/* routes work"""

   async def test_version_header_present(client):
       """Test X-API-Version header"""
   ```

**Review Checklist:**
- [ ] All routes under /api/v1/
- [ ] Version header in responses
- [ ] Easy to add v2 later
- [ ] Documentation reflects versioning

---

### P20: Batch Operations

**Gap:** No batch endpoints for bulk operations

**Files to Create:**
- `src/knowledge/api/routes/batch.py`

**Implementation Steps:**

1. **Create batch schemas**
   ```python
   # Add to schemas.py
   class BatchContentCreate(BaseModel):
       items: list[ContentCreate] = Field(..., max_length=100)

   class BatchSearchRequest(BaseModel):
       queries: list[SearchRequest] = Field(..., max_length=10)

   class BatchDeleteRequest(BaseModel):
       ids: list[UUID] = Field(..., max_length=100)

   class BatchResult(BaseModel):
       total: int
       succeeded: int
       failed: int
       results: list[dict]
       errors: list[dict]
   ```

2. **Create batch routes**
   ```python
   # src/knowledge/api/routes/batch.py
   from fastapi import APIRouter, BackgroundTasks, Depends
   from knowledge.api.auth import require_scope

   router = APIRouter(prefix="/batch", tags=["batch"])

   @router.post("/content", dependencies=[Depends(require_scope("write"))])
   async def batch_create_content(
       request: BatchContentCreate,
       background_tasks: BackgroundTasks,
   ) -> BatchResult:
       """Create multiple content items."""
       results = []
       errors = []

       for i, item in enumerate(request.items):
           try:
               content_id = await create_single_content(item)
               results.append({"index": i, "id": str(content_id)})
           except Exception as e:
               errors.append({"index": i, "error": str(e)})

       return BatchResult(
           total=len(request.items),
           succeeded=len(results),
           failed=len(errors),
           results=results,
           errors=errors,
       )

   @router.post("/search")
   async def batch_search(request: BatchSearchRequest) -> list[SearchResponse]:
       """Execute multiple search queries."""
       return [await search_single(q) for q in request.queries]

   @router.delete("/content", dependencies=[Depends(require_scope("write"))])
   async def batch_delete_content(request: BatchDeleteRequest) -> BatchResult:
       """Delete multiple content items."""
       # Implementation
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_batch.py`):
   ```python
   class TestBatchOperations:
       async def test_batch_create_success(self):
           """Test batch create with valid items"""

       async def test_batch_create_partial_failure(self):
           """Test batch with some failures"""

       async def test_batch_search_multiple_queries(self):
           """Test multiple search queries"""

       async def test_batch_delete(self):
           """Test batch delete"""

       async def test_batch_limit_enforced(self):
           """Test max items limit"""
   ```

**Review Checklist:**
- [ ] Batch size limits enforced
- [ ] Partial failures handled gracefully
- [ ] Results include success/failure counts
- [ ] Error details returned per item
- [ ] Write operations require auth

---

### P21: Export/Import System

**Gap:** No data portability

**Files to Create:**
- `src/knowledge/api/routes/export.py`

**Implementation Steps:**

1. **Create export/import schemas**
   ```python
   class ExportRequest(BaseModel):
       format: str = Field(default="json", pattern="^(json|obsidian)$")
       include_embeddings: bool = False
       namespace: str | None = None
       since: datetime | None = None  # For incremental export

   class ImportRequest(BaseModel):
       format: str = Field(default="json", pattern="^(json|obsidian)$")
       overwrite: bool = False
   ```

2. **Create export/import routes**
   ```python
   # src/knowledge/api/routes/export.py
   from fastapi import APIRouter, Depends
   from fastapi.responses import StreamingResponse
   import json

   router = APIRouter(prefix="/export", tags=["export"])

   @router.get("")
   async def export_data(
       format: str = "json",
       include_embeddings: bool = False,
       namespace: str | None = None,
       _: None = Depends(require_scope("read")),
   ) -> StreamingResponse:
       """Export all content as JSON or Obsidian format."""

       async def generate():
           db = await get_db()
           async with db.acquire() as conn:
               # Stream content in batches
               offset = 0
               batch_size = 100

               yield '{"content": ['
               first = True

               while True:
                   rows = await conn.fetch(
                       """
                       SELECT * FROM content
                       WHERE deleted_at IS NULL
                       ORDER BY created_at
                       LIMIT $1 OFFSET $2
                       """,
                       batch_size, offset
                   )

                   if not rows:
                       break

                   for row in rows:
                       if not first:
                           yield ','
                       first = False
                       yield json.dumps(dict(row), default=str)

                   offset += batch_size

               yield ']}'

       return StreamingResponse(
           generate(),
           media_type="application/json",
           headers={"Content-Disposition": "attachment; filename=kas_export.json"}
       )

   @router.post("/import")
   async def import_data(
       file: UploadFile,
       overwrite: bool = False,
       _: None = Depends(require_scope("write")),
   ) -> ImportResult:
       """Import content from JSON file."""
       # Parse and import
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_export.py`):
   ```python
   class TestExport:
       async def test_export_json_format(self):
           """Test JSON export is valid"""

       async def test_export_filters_by_namespace(self):
           """Test namespace filtering"""

       async def test_export_incremental(self):
           """Test since parameter"""

       async def test_import_creates_content(self):
           """Test import creates records"""

       async def test_import_overwrite(self):
           """Test overwrite mode"""
   ```

**Review Checklist:**
- [ ] Export streams large datasets
- [ ] JSON format is valid and complete
- [ ] Incremental export supported
- [ ] Import handles duplicates
- [ ] Embeddings optional in export
- [ ] Proper auth required

---

### P22: OpenAPI Documentation

**Gap:** Basic auto-generated docs only

**Files to Modify:**
- All route files
- `src/knowledge/api/main.py`

**Implementation Steps:**

1. **Add detailed docstrings to all endpoints**
   ```python
   @router.post(
       "/search",
       summary="Search knowledge base",
       description="""
       Perform hybrid search across all content using BM25 (keyword)
       and vector (semantic) search with RRF fusion.

       ## Search Modes
       - **Default**: Hybrid search combining BM25 and vector
       - **Reranked**: Add `rerank=true` for cross-encoder reranking

       ## Namespace Filtering
       Use `namespace` to filter results:
       - Exact match: `namespace=projects`
       - Prefix match: `namespace=projects/*`
       """,
       response_description="Search results with scores and content details",
       responses={
           200: {
               "description": "Successful search",
               "content": {
                   "application/json": {
                       "example": {
                           "results": [
                               {
                                   "id": "550e8400-e29b-41d4-a716-446655440000",
                                   "title": "Example Content",
                                   "score": 0.85,
                                   "chunk_text": "Relevant excerpt..."
                               }
                           ],
                           "total": 1,
                           "query": "example query"
                       }
                   }
               }
           },
           400: {"description": "Invalid search parameters"},
           429: {"description": "Rate limit exceeded"},
       }
   )
   async def search(...):
   ```

2. **Add response models**
   ```python
   class SearchResultItem(BaseModel):
       """Individual search result."""
       id: UUID = Field(..., description="Content UUID")
       title: str = Field(..., description="Content title")
       type: str = Field(..., description="Content type (youtube, bookmark, etc.)")
       score: float = Field(..., description="Relevance score (0-1)")
       chunk_text: str | None = Field(None, description="Matching chunk text")
       namespace: str | None = Field(None, description="Content namespace")

       model_config = ConfigDict(
           json_schema_extra={
               "example": {
                   "id": "550e8400-e29b-41d4-a716-446655440000",
                   "title": "Machine Learning Basics",
                   "type": "youtube",
                   "score": 0.85,
                   "chunk_text": "Neural networks are...",
                   "namespace": "learning"
               }
           }
       )
   ```

3. **Update FastAPI config**
   ```python
   app = FastAPI(
       title="Knowledge Activation System API",
       description="""
       ## Overview
       KAS is a personal knowledge management system with AI-powered search.

       ## Authentication
       Most endpoints require an API key passed via `X-API-Key` header.

       ## Rate Limiting
       Default: 100 requests/minute. Check `X-RateLimit-*` headers.

       ## Versioning
       Current version: v1. All endpoints prefixed with `/api/v1/`.
       """,
       version="1.0.0",
       docs_url="/docs",
       redoc_url="/redoc",
       openapi_tags=[
           {"name": "search", "description": "Search operations"},
           {"name": "content", "description": "Content CRUD operations"},
           {"name": "review", "description": "Spaced repetition review"},
           {"name": "batch", "description": "Bulk operations"},
           {"name": "export", "description": "Data export/import"},
           {"name": "auth", "description": "Authentication management"},
           {"name": "health", "description": "Health and status"},
       ]
   )
   ```

**Testing Strategy:**

1. **Validation Tests**:
   ```python
   def test_openapi_schema_valid():
       """Test OpenAPI schema is valid"""
       response = client.get("/openapi.json")
       assert response.status_code == 200
       schema = response.json()
       assert "paths" in schema
       assert "/api/v1/search" in schema["paths"]

   def test_all_endpoints_documented():
       """Test all endpoints have descriptions"""
       schema = client.get("/openapi.json").json()
       for path, methods in schema["paths"].items():
           for method, details in methods.items():
               assert "summary" in details, f"{method} {path} missing summary"
   ```

**Review Checklist:**
- [ ] All endpoints have summary and description
- [ ] Request/response examples provided
- [ ] Error responses documented
- [ ] Authentication documented
- [ ] Tags organize endpoints logically
- [ ] OpenAPI schema validates

---

## Phase 3: Reliability & Observability

### P23: Health Check Enhancement

**Gap:** Basic health check, no deep checks

**Files to Modify:**
- `src/knowledge/api/routes/health.py`

**Implementation Steps:**

1. **Enhance health endpoint**
   ```python
   # src/knowledge/api/routes/health.py
   from enum import Enum
   from pydantic import BaseModel
   import psutil
   import httpx

   class HealthStatus(str, Enum):
       HEALTHY = "healthy"
       DEGRADED = "degraded"
       UNHEALTHY = "unhealthy"

   class ComponentHealth(BaseModel):
       name: str
       status: HealthStatus
       latency_ms: float | None = None
       details: dict = {}

   class HealthResponse(BaseModel):
       status: HealthStatus
       version: str
       components: list[ComponentHealth]
       system: dict

   async def check_database_health() -> ComponentHealth:
       """Check database connectivity and pool status."""
       start = time.time()
       try:
           db = await get_db()
           health = await db.check_health()
           latency = (time.time() - start) * 1000

           return ComponentHealth(
               name="database",
               status=HealthStatus.HEALTHY if health["status"] == "healthy" else HealthStatus.UNHEALTHY,
               latency_ms=latency,
               details={
                   "pool": db.get_pool_stats(),
                   "content_count": health.get("content_count"),
               }
           )
       except Exception as e:
           return ComponentHealth(
               name="database",
               status=HealthStatus.UNHEALTHY,
               details={"error": str(e)}
           )

   async def check_ollama_health() -> ComponentHealth:
       """Check Ollama connectivity."""
       settings = get_settings()
       start = time.time()
       try:
           async with httpx.AsyncClient() as client:
               response = await client.get(
                   f"{settings.ollama_url}/api/tags",
                   timeout=5.0
               )
               latency = (time.time() - start) * 1000

               if response.status_code == 200:
                   models = response.json().get("models", [])
                   return ComponentHealth(
                       name="ollama",
                       status=HealthStatus.HEALTHY,
                       latency_ms=latency,
                       details={"models_available": len(models)}
                   )
               else:
                   return ComponentHealth(
                       name="ollama",
                       status=HealthStatus.DEGRADED,
                       latency_ms=latency,
                       details={"status_code": response.status_code}
                   )
       except Exception as e:
           return ComponentHealth(
               name="ollama",
               status=HealthStatus.UNHEALTHY,
               details={"error": str(e)}
           )

   def check_system_health() -> dict:
       """Check system resources."""
       return {
           "cpu_percent": psutil.cpu_percent(),
           "memory_percent": psutil.virtual_memory().percent,
           "disk_percent": psutil.disk_usage("/").percent,
       }

   @router.get("/health", response_model=HealthResponse)
   async def health_check() -> HealthResponse:
       """Deep health check of all components."""
       components = await asyncio.gather(
           check_database_health(),
           check_ollama_health(),
       )

       system = check_system_health()

       # Determine overall status
       statuses = [c.status for c in components]
       if all(s == HealthStatus.HEALTHY for s in statuses):
           overall = HealthStatus.HEALTHY
       elif any(s == HealthStatus.UNHEALTHY for s in statuses):
           overall = HealthStatus.UNHEALTHY
       else:
           overall = HealthStatus.DEGRADED

       return HealthResponse(
           status=overall,
           version="1.0.0",
           components=list(components),
           system=system,
       )

   @router.get("/ready")
   async def readiness_check():
       """Quick readiness check for load balancers."""
       db = await get_db()
       if db._pool is None:
           raise HTTPException(503, "Not ready")
       return {"ready": True}

   @router.get("/live")
   async def liveness_check():
       """Quick liveness check."""
       return {"alive": True}
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_health.py`):
   ```python
   class TestHealthChecks:
       async def test_health_returns_all_components(self):
           """Test health includes all component checks"""

       async def test_degraded_when_ollama_down(self, mock_ollama_down):
           """Test degraded status when Ollama unavailable"""

       async def test_unhealthy_when_db_down(self, mock_db_down):
           """Test unhealthy when database unavailable"""

       async def test_ready_endpoint(self):
           """Test readiness endpoint"""

       async def test_live_endpoint(self):
           """Test liveness endpoint"""

       async def test_system_metrics_included(self):
           """Test system CPU/memory/disk in response"""
   ```

**Review Checklist:**
- [ ] Database health includes pool stats
- [ ] Ollama health includes model availability
- [ ] System metrics (CPU, memory, disk) included
- [ ] Overall status logic correct (healthy/degraded/unhealthy)
- [ ] /ready and /live endpoints for k8s probes
- [ ] Component latencies measured

---

### P24: Metrics Collection

**Gap:** No application metrics

**Files to Create:**
- `src/knowledge/metrics.py`

**Implementation Steps:**

1. **Install prometheus-client**
   ```bash
   # Already in pyproject.toml observability extra
   ```

2. **Create metrics module**
   ```python
   # src/knowledge/metrics.py
   from prometheus_client import Counter, Histogram, Gauge, Info

   # Application info
   app_info = Info("kas", "Knowledge Activation System info")
   app_info.info({"version": "1.0.0"})

   # Request metrics
   http_requests_total = Counter(
       "kas_http_requests_total",
       "Total HTTP requests",
       ["method", "endpoint", "status"]
   )

   http_request_duration = Histogram(
       "kas_http_request_duration_seconds",
       "HTTP request duration",
       ["method", "endpoint"],
       buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
   )

   # Search metrics
   search_requests = Counter(
       "kas_search_requests_total",
       "Total search requests",
       ["namespace", "reranked"]
   )

   search_duration = Histogram(
       "kas_search_duration_seconds",
       "Search duration",
       ["search_type"],  # bm25, vector, hybrid, rerank
       buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
   )

   search_results = Histogram(
       "kas_search_results_count",
       "Number of search results",
       buckets=[0, 1, 5, 10, 20, 50, 100]
   )

   # Embedding metrics
   embedding_requests = Counter(
       "kas_embedding_requests_total",
       "Total embedding requests"
   )

   embedding_duration = Histogram(
       "kas_embedding_duration_seconds",
       "Embedding generation duration",
       buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
   )

   # Content metrics
   content_total = Gauge(
       "kas_content_total",
       "Total content items",
       ["type"]
   )

   chunks_total = Gauge(
       "kas_chunks_total",
       "Total chunks"
   )

   # Database metrics
   db_pool_size = Gauge(
       "kas_db_pool_size",
       "Database pool size"
   )

   db_pool_available = Gauge(
       "kas_db_pool_available",
       "Available database connections"
   )

   # Background task metrics
   ingest_queue_size = Gauge(
       "kas_ingest_queue_size",
       "Items in ingest queue"
   )
   ```

3. **Add metrics endpoint**
   ```python
   # src/knowledge/api/routes/metrics.py
   from fastapi import APIRouter
   from fastapi.responses import Response
   from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

   router = APIRouter(tags=["metrics"])

   @router.get("/metrics")
   async def metrics():
       """Prometheus metrics endpoint."""
       return Response(
           content=generate_latest(),
           media_type=CONTENT_TYPE_LATEST
       )
   ```

4. **Add metrics middleware**
   ```python
   # In middleware.py
   from knowledge.metrics import http_requests_total, http_request_duration

   class MetricsMiddleware(BaseHTTPMiddleware):
       async def dispatch(self, request, call_next):
           start = time.time()
           response = await call_next(request)
           duration = time.time() - start

           http_requests_total.labels(
               method=request.method,
               endpoint=request.url.path,
               status=response.status_code
           ).inc()

           http_request_duration.labels(
               method=request.method,
               endpoint=request.url.path
           ).observe(duration)

           return response
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_metrics.py`):
   ```python
   class TestMetrics:
       def test_metrics_endpoint_returns_prometheus_format(self):
           """Test /metrics returns valid Prometheus format"""

       def test_http_request_metrics_recorded(self):
           """Test HTTP metrics are recorded"""

       def test_search_metrics_recorded(self):
           """Test search metrics are recorded"""
   ```

**Review Checklist:**
- [ ] All key operations have metrics
- [ ] Histogram buckets appropriate for expected latencies
- [ ] Labels are low cardinality
- [ ] /metrics endpoint exposed
- [ ] Middleware records request metrics
- [ ] Content gauges updated periodically

---

### P25: Distributed Tracing

**Gap:** No request tracing

**Files to Create:**
- `src/knowledge/tracing.py`

**Implementation Steps:**

1. **Create tracing configuration**
   ```python
   # src/knowledge/tracing.py
   from opentelemetry import trace
   from opentelemetry.sdk.trace import TracerProvider
   from opentelemetry.sdk.trace.export import BatchSpanProcessor
   from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
   from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
   from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
   from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

   def configure_tracing(
       service_name: str = "kas",
       otlp_endpoint: str | None = None,
       sample_rate: float = 1.0,
   ) -> None:
       """Configure OpenTelemetry tracing."""
       provider = TracerProvider()

       if otlp_endpoint:
           exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
           provider.add_span_processor(BatchSpanProcessor(exporter))

       trace.set_tracer_provider(provider)

       # Auto-instrument libraries
       FastAPIInstrumentor.instrument()
       AsyncPGInstrumentor().instrument()
       HTTPXClientInstrumentor().instrument()

   def get_tracer(name: str) -> trace.Tracer:
       """Get a tracer instance."""
       return trace.get_tracer(name)

   # Usage in code
   tracer = get_tracer(__name__)

   async def search(...):
       with tracer.start_as_current_span("hybrid_search") as span:
           span.set_attribute("query", query)
           span.set_attribute("limit", limit)

           with tracer.start_as_current_span("bm25_search"):
               bm25_results = await db.bm25_search(query)

           with tracer.start_as_current_span("vector_search"):
               vector_results = await db.vector_search(embedding)

           # ... rest of search
   ```

2. **Add to config**
   ```python
   # Settings
   tracing_enabled: bool = False
   tracing_otlp_endpoint: str | None = None
   tracing_sample_rate: float = 1.0
   ```

**Testing Strategy:**

1. **Unit Tests**:
   ```python
   class TestTracing:
       def test_tracer_configuration(self):
           """Test tracer is configured correctly"""

       def test_spans_created(self, mock_tracer):
           """Test spans are created for operations"""

       def test_span_attributes_set(self, mock_tracer):
           """Test span attributes are recorded"""
   ```

**Review Checklist:**
- [ ] OpenTelemetry configured
- [ ] FastAPI auto-instrumented
- [ ] asyncpg auto-instrumented
- [ ] httpx auto-instrumented
- [ ] Custom spans for key operations
- [ ] Trace ID propagation works
- [ ] Sample rate configurable

---

### P26: Circuit Breaker Pattern

**Gap:** No failure isolation

**Files to Create:**
- `src/knowledge/circuit_breaker.py`

**Implementation Steps:**

1. **Implement circuit breaker**
   ```python
   # src/knowledge/circuit_breaker.py
   import asyncio
   from dataclasses import dataclass
   from enum import Enum
   from time import time
   from typing import Callable, TypeVar, Generic

   from knowledge.logging import get_logger
   from knowledge.metrics import Gauge, Counter

   logger = get_logger(__name__)

   T = TypeVar("T")

   class CircuitState(str, Enum):
       CLOSED = "closed"
       OPEN = "open"
       HALF_OPEN = "half_open"

   # Metrics
   circuit_state = Gauge(
       "kas_circuit_state",
       "Circuit breaker state (0=closed, 1=open, 2=half_open)",
       ["name"]
   )

   circuit_failures = Counter(
       "kas_circuit_failures_total",
       "Circuit breaker failures",
       ["name"]
   )

   @dataclass
   class CircuitBreakerConfig:
       failure_threshold: int = 5
       recovery_timeout: float = 30.0
       half_open_max_calls: int = 3

   class CircuitBreaker(Generic[T]):
       def __init__(
           self,
           name: str,
           config: CircuitBreakerConfig | None = None,
           fallback: Callable[..., T] | None = None,
       ):
           self.name = name
           self.config = config or CircuitBreakerConfig()
           self.fallback = fallback

           self._state = CircuitState.CLOSED
           self._failure_count = 0
           self._last_failure_time = 0.0
           self._half_open_calls = 0
           self._lock = asyncio.Lock()

       @property
       def state(self) -> CircuitState:
           return self._state

       async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
           """Execute function with circuit breaker protection."""
           async with self._lock:
               if self._state == CircuitState.OPEN:
                   if time() - self._last_failure_time > self.config.recovery_timeout:
                       self._state = CircuitState.HALF_OPEN
                       self._half_open_calls = 0
                       logger.info("circuit_half_open", name=self.name)
                   else:
                       logger.warning("circuit_open_rejected", name=self.name)
                       if self.fallback:
                           return await self.fallback(*args, **kwargs)
                       raise CircuitOpenError(self.name)

           try:
               result = await func(*args, **kwargs)
               await self._on_success()
               return result
           except Exception as e:
               await self._on_failure(e)
               raise

       async def _on_success(self):
           async with self._lock:
               if self._state == CircuitState.HALF_OPEN:
                   self._half_open_calls += 1
                   if self._half_open_calls >= self.config.half_open_max_calls:
                       self._state = CircuitState.CLOSED
                       self._failure_count = 0
                       logger.info("circuit_closed", name=self.name)
               else:
                   self._failure_count = 0

               circuit_state.labels(name=self.name).set(
                   0 if self._state == CircuitState.CLOSED else
                   1 if self._state == CircuitState.OPEN else 2
               )

       async def _on_failure(self, error: Exception):
           async with self._lock:
               self._failure_count += 1
               self._last_failure_time = time()
               circuit_failures.labels(name=self.name).inc()

               if self._state == CircuitState.HALF_OPEN:
                   self._state = CircuitState.OPEN
                   logger.warning("circuit_opened_from_half_open", name=self.name, error=str(error))
               elif self._failure_count >= self.config.failure_threshold:
                   self._state = CircuitState.OPEN
                   logger.warning("circuit_opened", name=self.name, failures=self._failure_count)

               circuit_state.labels(name=self.name).set(
                   0 if self._state == CircuitState.CLOSED else
                   1 if self._state == CircuitState.OPEN else 2
               )

   class CircuitOpenError(Exception):
       def __init__(self, circuit_name: str):
           self.circuit_name = circuit_name
           super().__init__(f"Circuit '{circuit_name}' is open")
   ```

2. **Create circuit breakers for external services**
   ```python
   # src/knowledge/embeddings.py
   from knowledge.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

   ollama_circuit = CircuitBreaker(
       name="ollama",
       config=CircuitBreakerConfig(
           failure_threshold=3,
           recovery_timeout=60.0,
       ),
       fallback=None,  # Or return cached/default embedding
   )

   async def get_embedding(text: str) -> list[float]:
       return await ollama_circuit.call(_get_embedding_impl, text)
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_circuit_breaker.py`):
   ```python
   class TestCircuitBreaker:
       async def test_closed_allows_calls(self):
           """Test closed circuit allows all calls"""

       async def test_opens_after_threshold(self):
           """Test circuit opens after failure threshold"""

       async def test_open_rejects_calls(self):
           """Test open circuit rejects calls"""

       async def test_half_open_after_timeout(self):
           """Test circuit goes half-open after timeout"""

       async def test_closes_after_successful_half_open(self):
           """Test circuit closes after successful half-open calls"""

       async def test_fallback_called_when_open(self):
           """Test fallback is called when circuit open"""
   ```

**Review Checklist:**
- [ ] Circuit states: closed, open, half-open
- [ ] Configurable thresholds
- [ ] Automatic recovery attempt
- [ ] Fallback function support
- [ ] Metrics for circuit state
- [ ] Thread-safe implementation

---

### P27: Graceful Degradation

**Gap:** Hard failures when dependencies unavailable

**Files to Modify:**
- `src/knowledge/search.py`
- `src/knowledge/embeddings.py`

**Implementation Steps:**

1. **Add fallback search modes**
   ```python
   # src/knowledge/search.py
   from knowledge.circuit_breaker import CircuitOpenError

   class SearchService:
       async def hybrid_search(
           self,
           query: str,
           limit: int = 10,
           namespace: str | None = None,
       ) -> SearchResult:
           """
           Hybrid search with graceful degradation.

           Falls back to BM25-only if embeddings unavailable.
           """
           bm25_results = []
           vector_results = []
           degraded = False

           # BM25 search (always attempt)
           try:
               bm25_results = await self.db.bm25_search(query, limit * 2, namespace)
           except Exception as e:
               logger.error("bm25_search_failed", error=str(e))

           # Vector search (may fail if Ollama down)
           try:
               embedding = await get_embedding(query)
               vector_results = await self.db.vector_search(embedding, limit * 2, namespace)
           except CircuitOpenError:
               logger.warning("vector_search_skipped", reason="circuit_open")
               degraded = True
           except Exception as e:
               logger.error("vector_search_failed", error=str(e))
               degraded = True

           # Combine results
           if vector_results:
               results = rrf_fusion(bm25_results, vector_results, k=self.settings.rrf_k)
           else:
               # Fallback to BM25 only
               results = [(r[0], r[1], r[2], r[3], None, r[4]) for r in bm25_results]

           return SearchResult(
               results=results[:limit],
               degraded=degraded,
               search_mode="hybrid" if not degraded else "bm25_only",
           )
   ```

2. **Add degraded mode indicators**
   ```python
   # In SearchResponse schema
   class SearchResponse(BaseModel):
       results: list[SearchResultItem]
       total: int
       query: str
       degraded: bool = False
       search_mode: str = "hybrid"
       warnings: list[str] = []
   ```

3. **Add retry queue for failed ingestions**
   ```python
   # src/knowledge/ingest/retry_queue.py
   from collections import deque
   from dataclasses import dataclass
   from datetime import datetime

   @dataclass
   class FailedIngest:
       content_type: str
       source: str
       error: str
       attempts: int
       last_attempt: datetime

   class IngestRetryQueue:
       def __init__(self, max_size: int = 1000):
           self._queue: deque[FailedIngest] = deque(maxlen=max_size)

       def add(self, item: FailedIngest):
           self._queue.append(item)

       async def process_retries(self, max_retries: int = 3):
           """Process failed ingestions."""
           items_to_retry = list(self._queue)
           self._queue.clear()

           for item in items_to_retry:
               if item.attempts >= max_retries:
                   logger.warning("ingest_max_retries", source=item.source)
                   continue

               try:
                   await ingest(item.content_type, item.source)
               except Exception as e:
                   item.attempts += 1
                   item.last_attempt = datetime.now()
                   item.error = str(e)
                   self._queue.append(item)
   ```

**Testing Strategy:**

1. **Unit Tests** (`tests/test_degradation.py`):
   ```python
   class TestGracefulDegradation:
       async def test_search_falls_back_to_bm25(self, mock_ollama_down):
           """Test search works with BM25 only"""

       async def test_degraded_flag_set(self, mock_ollama_down):
           """Test degraded flag in response"""

       async def test_search_mode_indicates_fallback(self):
           """Test search_mode shows bm25_only"""

       async def test_retry_queue_stores_failures(self):
           """Test failed ingests are queued"""

       async def test_retry_queue_processes(self):
           """Test retry queue processes items"""
   ```

**Review Checklist:**
- [ ] Search continues with BM25 when embeddings fail
- [ ] Response indicates degraded mode
- [ ] Warnings included in response
- [ ] Failed ingestions queued for retry
- [ ] Retry attempts limited
- [ ] Metrics track degraded operations

---

## Phase 4: Testing & Quality

### P28: Integration Test Suite

**Gap:** Only unit tests, no integration tests

**Files to Create:**
- `tests/integration/__init__.py`
- `tests/integration/conftest.py`
- `tests/integration/test_db_integration.py`
- `tests/integration/test_api_integration.py`
- `tests/integration/test_search_integration.py`

**Implementation Steps:**

1. **Create integration test fixtures**
   ```python
   # tests/integration/conftest.py
   import pytest
   import asyncio
   from httpx import AsyncClient

   from knowledge.db import Database
   from knowledge.config import Settings
   from knowledge.api.main import app

   @pytest.fixture(scope="session")
   def event_loop():
       loop = asyncio.get_event_loop_policy().new_event_loop()
       yield loop
       loop.close()

   @pytest.fixture(scope="session")
   async def integration_db():
       """Real database connection for integration tests."""
       settings = Settings(
           database_url="postgresql://knowledge:localdev@localhost:5432/knowledge_test"
       )
       db = Database(settings)
       await db.connect()
       yield db
       await db.disconnect()

   @pytest.fixture(scope="function")
   async def clean_db(integration_db):
       """Clean database before each test."""
       async with integration_db.acquire() as conn:
           await conn.execute("TRUNCATE content, chunks, review_queue CASCADE")
       yield integration_db

   @pytest.fixture
   async def api_client():
       """HTTP client for API tests."""
       async with AsyncClient(app=app, base_url="http://test") as client:
           yield client
   ```

2. **Create database integration tests**
   ```python
   # tests/integration/test_db_integration.py
   import pytest
   from uuid import uuid4

   @pytest.mark.integration
   class TestDatabaseIntegration:
       async def test_insert_and_retrieve_content(self, clean_db):
           """Test full content lifecycle with real database."""
           content_id = await clean_db.insert_content(
               filepath="test/integration.md",
               content_type="note",
               title="Integration Test",
               content_for_hash="test content",
           )

           content = await clean_db.get_content_by_id(content_id)
           assert content is not None
           assert content.title == "Integration Test"

       async def test_hybrid_search_returns_results(self, clean_db):
           """Test search returns real results."""
           # Insert test content
           # Generate real embeddings
           # Search and verify

       async def test_pool_handles_concurrent_requests(self, clean_db):
           """Test pool under concurrent load."""
           import asyncio

           async def query():
               await clean_db.get_stats()

           # Run 50 concurrent queries
           await asyncio.gather(*[query() for _ in range(50)])
   ```

3. **Create API integration tests**
   ```python
   # tests/integration/test_api_integration.py
   @pytest.mark.integration
   class TestAPIIntegration:
       async def test_search_endpoint_e2e(self, api_client, seeded_db):
           """Test search endpoint end-to-end."""
           response = await api_client.post(
               "/api/v1/search",
               json={"query": "test query", "limit": 5}
           )
           assert response.status_code == 200
           data = response.json()
           assert "results" in data

       async def test_content_create_and_search(self, api_client):
           """Test content creation flows to searchable."""
           # Create content
           create_response = await api_client.post(
               "/api/v1/content",
               json={...}
           )
           assert create_response.status_code == 201

           # Wait for indexing
           await asyncio.sleep(1)

           # Search for it
           search_response = await api_client.post(
               "/api/v1/search",
               json={"query": "created content"}
           )
           # Verify found
   ```

4. **Add pytest marker**
   ```python
   # pyproject.toml
   [tool.pytest.ini_options]
   markers = [
       "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
   ]
   ```

**Testing Strategy:**

Run integration tests separately:
```bash
# Run only integration tests
pytest tests/integration/ -v

# Run all except integration
pytest -m "not integration"
```

**Review Checklist:**
- [ ] Real database used (not mocked)
- [ ] Tests isolated with truncate
- [ ] Concurrent access tested
- [ ] Full request lifecycle tested
- [ ] Marker allows selective running
- [ ] CI can run with test database

---

### P29: Load Testing

**Gap:** No performance baselines

**Files to Create:**
- `tests/load/locustfile.py`
- `tests/load/k6_search.js`
- `tests/load/README.md`

**Implementation Steps:**

1. **Create Locust load test**
   ```python
   # tests/load/locustfile.py
   from locust import HttpUser, task, between
   import random

   SAMPLE_QUERIES = [
       "machine learning basics",
       "python programming",
       "database optimization",
       "API design patterns",
       "kubernetes deployment",
   ]

   class KASUser(HttpUser):
       wait_time = between(1, 3)

       @task(10)
       def search(self):
           query = random.choice(SAMPLE_QUERIES)
           self.client.post(
               "/api/v1/search",
               json={"query": query, "limit": 10}
           )

       @task(5)
       def search_with_rerank(self):
           query = random.choice(SAMPLE_QUERIES)
           self.client.post(
               "/api/v1/search",
               json={"query": query, "limit": 10, "rerank": True}
           )

       @task(2)
       def get_stats(self):
           self.client.get("/api/v1/stats")

       @task(1)
       def health_check(self):
           self.client.get("/health")
   ```

2. **Create k6 script**
   ```javascript
   // tests/load/k6_search.js
   import http from 'k6/http';
   import { check, sleep } from 'k6';
   import { Rate, Trend } from 'k6/metrics';

   const searchDuration = new Trend('search_duration');
   const searchErrors = new Rate('search_errors');

   export const options = {
     stages: [
       { duration: '1m', target: 10 },  // Ramp up
       { duration: '3m', target: 10 },  // Steady
       { duration: '1m', target: 50 },  // Spike
       { duration: '2m', target: 50 },  // Sustain spike
       { duration: '1m', target: 0 },   // Ramp down
     ],
     thresholds: {
       http_req_duration: ['p(95)<500', 'p(99)<1000'],
       search_errors: ['rate<0.01'],
     },
   };

   const queries = [
     'machine learning',
     'python programming',
     'api design',
   ];

   export default function () {
     const query = queries[Math.floor(Math.random() * queries.length)];

     const start = Date.now();
     const res = http.post(
       'http://localhost:8000/api/v1/search',
       JSON.stringify({ query, limit: 10 }),
       { headers: { 'Content-Type': 'application/json' } }
     );
     searchDuration.add(Date.now() - start);

     const success = check(res, {
       'status is 200': (r) => r.status === 200,
       'has results': (r) => JSON.parse(r.body).results !== undefined,
     });

     searchErrors.add(!success);

     sleep(1);
   }
   ```

3. **Document baselines**
   ```markdown
   # tests/load/README.md

   ## Performance Baselines

   | Metric | Target | Current |
   |--------|--------|---------|
   | Search p50 | <100ms | TBD |
   | Search p95 | <500ms | TBD |
   | Search p99 | <1s | TBD |
   | Rerank p95 | <2s | TBD |
   | Concurrent users | 50 | TBD |
   | Requests/sec | 100 | TBD |

   ## Running Tests

   ```bash
   # Locust (web UI)
   locust -f tests/load/locustfile.py --host=http://localhost:8000

   # k6 (CLI)
   k6 run tests/load/k6_search.js
   ```
   ```

**Testing Strategy:**

1. Run load tests against local instance
2. Capture baseline metrics
3. Add to CI as performance regression check

**Review Checklist:**
- [ ] Locust script covers main endpoints
- [ ] k6 script has realistic scenarios
- [ ] Thresholds defined for p95/p99
- [ ] Baseline documented
- [ ] Can run in CI

---

### P30: Evaluation Framework Enhancement

**Gap:** Basic eval only, no comprehensive metrics

**Files to Modify:**
- `evaluation/` directory

**Implementation Steps:**

1. **Add RAGAS metrics**
   ```python
   # evaluation/metrics.py
   from dataclasses import dataclass
   import numpy as np

   @dataclass
   class RetrievalMetrics:
       mrr: float  # Mean Reciprocal Rank
       ndcg: float  # Normalized Discounted Cumulative Gain
       precision_at_k: dict[int, float]  # P@1, P@5, P@10
       recall_at_k: dict[int, float]

   def calculate_mrr(results: list[list[str]], ground_truth: list[str]) -> float:
       """Calculate Mean Reciprocal Rank."""
       reciprocal_ranks = []
       for result_list, truth in zip(results, ground_truth):
           try:
               rank = result_list.index(truth) + 1
               reciprocal_ranks.append(1.0 / rank)
           except ValueError:
               reciprocal_ranks.append(0.0)
       return np.mean(reciprocal_ranks)

   def calculate_ndcg(results: list[list[str]], relevance: list[list[int]], k: int = 10) -> float:
       """Calculate NDCG@k."""
       # Implementation
   ```

2. **Create golden dataset**
   ```python
   # evaluation/golden_dataset.py
   GOLDEN_QUERIES = [
       {
           "query": "How to implement binary search in Python",
           "relevant_ids": ["uuid1", "uuid2"],
           "expected_type": "file",
       },
       # ... more queries
   ]
   ```

3. **Create evaluation runner**
   ```python
   # evaluation/runner.py
   async def run_evaluation(dataset: list[dict]) -> EvaluationReport:
       """Run full evaluation suite."""
       results = []

       for item in dataset:
           search_results = await search(item["query"])
           results.append({
               "query": item["query"],
               "found_relevant": any(
                   r.id in item["relevant_ids"]
                   for r in search_results
               ),
               "top_result_relevant": (
                   search_results[0].id in item["relevant_ids"]
                   if search_results else False
               ),
           })

       return EvaluationReport(
           mrr=calculate_mrr(...),
           precision_at_1=...,
           # ...
       )
   ```

**Review Checklist:**
- [ ] MRR calculation correct
- [ ] NDCG calculation correct
- [ ] Golden dataset created
- [ ] Evaluation runner works
- [ ] Results exportable

---

### P31: Mutation Testing

**Gap:** Test quality unknown

**Files to Modify:**
- `pyproject.toml`

**Implementation Steps:**

1. **Add mutmut**
   ```toml
   # pyproject.toml
   [project.optional-dependencies]
   dev = [
       # ... existing
       "mutmut>=2.4.0",
   ]

   [tool.mutmut]
   paths_to_mutate = "src/knowledge/"
   tests_dir = "tests/"
   runner = "pytest"
   ```

2. **Run mutation testing**
   ```bash
   # Run mutation testing
   mutmut run

   # View results
   mutmut results

   # Show surviving mutants
   mutmut show <id>
   ```

3. **Add to CI** (later in P38)

**Review Checklist:**
- [ ] mutmut configured
- [ ] Can run locally
- [ ] Baseline mutation score documented
- [ ] High-priority surviving mutants fixed

---

### P32: Security Testing

**Gap:** No security scanning

**Files to Create:**
- `tests/security/test_injection.py`
- `.github/workflows/security.yml` (in P38)

**Implementation Steps:**

1. **Add bandit**
   ```toml
   # pyproject.toml
   [project.optional-dependencies]
   dev = [
       # ... existing
       "bandit>=1.7.0",
   ]

   [tool.bandit]
   exclude_dirs = ["tests", ".venv"]
   ```

2. **Create security tests**
   ```python
   # tests/security/test_injection.py
   import pytest

   class TestSQLInjection:
       @pytest.mark.parametrize("payload", [
           "'; DROP TABLE content; --",
           "1 OR 1=1",
           "1; SELECT * FROM users",
           "' UNION SELECT * FROM api_keys --",
       ])
       async def test_search_rejects_sql_injection(self, client, payload):
           """Test search sanitizes SQL injection attempts."""
           response = await client.post(
               "/api/v1/search",
               json={"query": payload}
           )
           # Should not error, just return no/filtered results
           assert response.status_code == 200

   class TestPathTraversal:
       @pytest.mark.parametrize("path", [
           "../../../etc/passwd",
           "..\\..\\..\\windows\\system32",
           "/etc/passwd",
       ])
       async def test_filepath_rejects_traversal(self, client, path):
           """Test filepath validation blocks traversal."""
           response = await client.post(
               "/api/v1/content",
               json={"filepath": path, "title": "test", "content_type": "note"}
           )
           assert response.status_code == 400
   ```

3. **Run security scans**
   ```bash
   # Run bandit
   bandit -r src/knowledge/

   # Run npm audit on MCP server
   cd mcp-server && npm audit
   ```

**Review Checklist:**
- [ ] bandit configured and passing
- [ ] SQL injection tests
- [ ] Path traversal tests
- [ ] npm audit clean
- [ ] No hardcoded secrets

---

## Phase 5: Developer Experience

### P33: CLI Completeness

**Gap:** Missing essential CLI commands

**Files to Modify:**
- `cli.py`

**Implementation Steps:**

1. **Add new commands**
   ```python
   # cli.py
   import typer
   from rich.console import Console
   from rich.table import Table

   app = typer.Typer()
   console = Console()

   @app.command()
   def config(
       show: bool = typer.Option(False, "--show", help="Show current config"),
       validate: bool = typer.Option(False, "--validate", help="Validate config"),
   ):
       """Manage configuration."""
       settings = get_settings()

       if show:
           table = Table(title="Configuration")
           table.add_column("Setting")
           table.add_column("Value")

           for key, value in settings.model_dump().items():
               # Mask sensitive values
               if "key" in key.lower() or "password" in key.lower():
                   value = "***"
               table.add_row(key, str(value))

           console.print(table)

       if validate:
           try:
               Settings()
               console.print("[green]Configuration valid[/green]")
           except Exception as e:
               console.print(f"[red]Configuration error: {e}[/red]")
               raise typer.Exit(1)

   @app.command()
   def stats():
       """Show database statistics."""
       async def _stats():
           db = await get_db()
           stats = await db.get_stats()

           table = Table(title="KAS Statistics")
           table.add_column("Metric")
           table.add_column("Value")

           table.add_row("Total Content", str(stats["total_content"]))
           table.add_row("Total Chunks", str(stats["total_chunks"]))
           # ... more stats

           console.print(table)

       asyncio.run(_stats())

   @app.command()
   def doctor():
       """Run diagnostics."""
       async def _doctor():
           checks = []

           # Check database
           try:
               db = await get_db()
               health = await db.check_health()
               checks.append(("Database", health["status"] == "healthy", health))
           except Exception as e:
               checks.append(("Database", False, str(e)))

           # Check Ollama
           try:
               # ... check ollama
               checks.append(("Ollama", True, {}))
           except Exception as e:
               checks.append(("Ollama", False, str(e)))

           # Print results
           for name, ok, details in checks:
               status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
               console.print(f"{name}: {status}")

       asyncio.run(_doctor())

   @app.command()
   def maintenance(
       vacuum: bool = typer.Option(False, "--vacuum", help="Vacuum database"),
       reindex: bool = typer.Option(False, "--reindex", help="Reindex content"),
       cleanup: bool = typer.Option(False, "--cleanup", help="Cleanup deleted content"),
   ):
       """Database maintenance tasks."""
       # Implementation

   @app.command()
   def export(
       output: Path = typer.Option(..., "--output", "-o"),
       format: str = typer.Option("json", "--format", "-f"),
   ):
       """Export content."""
       # Implementation

   @app.command()
   def import_data(  # 'import' is reserved
       input: Path = typer.Option(..., "--input", "-i"),
       format: str = typer.Option("json", "--format", "-f"),
   ):
       """Import content."""
       # Implementation
   ```

**Review Checklist:**
- [ ] `kas config` shows/validates settings
- [ ] `kas stats` shows database stats
- [ ] `kas doctor` runs diagnostics
- [ ] `kas maintenance` has vacuum/reindex/cleanup
- [ ] `kas export/import` works
- [ ] Rich formatting for output
- [ ] Help text for all commands

---

### P34: MCP Server Enhancement

**Gap:** Basic search only

**Files to Modify:**
- `mcp-server/src/index.ts`
- `mcp-server/src/kas-client.ts`

**Implementation Steps:**

1. **Add new tools**
   ```typescript
   // mcp-server/src/index.ts

   // kas_ingest tool
   server.setRequestHandler(CallToolRequestSchema, async (request) => {
     if (request.params.name === "kas_ingest") {
       const { type, source, title } = request.params.arguments;

       const result = await kasClient.ingest({
         content_type: type,
         source,
         title,
       });

       return {
         content: [{
           type: "text",
           text: JSON.stringify(result, null, 2),
         }],
       };
     }

     if (request.params.name === "kas_stats") {
       const stats = await kasClient.getStats();
       return {
         content: [{
           type: "text",
           text: formatStats(stats),
         }],
       };
     }

     if (request.params.name === "kas_review") {
       const { action, content_id, rating } = request.params.arguments;

       if (action === "get") {
         const cards = await kasClient.getReviewCards();
         return { content: [{ type: "text", text: formatCards(cards) }] };
       }

       if (action === "submit") {
         await kasClient.submitReview(content_id, rating);
         return { content: [{ type: "text", text: "Review submitted" }] };
       }
     }
   });

   // Register tools
   server.setRequestHandler(ListToolsRequestSchema, async () => ({
     tools: [
       {
         name: "kas_search",
         description: "Search the knowledge base",
         inputSchema: { /* ... */ },
       },
       {
         name: "kas_ingest",
         description: "Ingest content into the knowledge base",
         inputSchema: {
           type: "object",
           properties: {
             type: { type: "string", enum: ["youtube", "bookmark", "url"] },
             source: { type: "string", description: "URL or ID to ingest" },
             title: { type: "string", description: "Optional title" },
           },
           required: ["type", "source"],
         },
       },
       {
         name: "kas_stats",
         description: "Get knowledge base statistics",
         inputSchema: { type: "object", properties: {} },
       },
       {
         name: "kas_review",
         description: "Spaced repetition review",
         inputSchema: {
           type: "object",
           properties: {
             action: { type: "string", enum: ["get", "submit"] },
             content_id: { type: "string" },
             rating: { type: "number", minimum: 1, maximum: 4 },
           },
           required: ["action"],
         },
       },
     ],
   }));
   ```

**Review Checklist:**
- [ ] `kas_ingest` tool added
- [ ] `kas_stats` tool added
- [ ] `kas_review` tool added
- [ ] Error handling includes context
- [ ] Input schemas validated
- [ ] README updated

---

### P35: Local Development Setup

**Gap:** Manual setup required

**Files to Create:**
- `docker-compose.dev.yml`
- `scripts/seed_dev.py`

**Implementation Steps:**

1. **Create dev compose file**
   ```yaml
   # docker-compose.dev.yml
   version: "3.8"

   services:
     db:
       image: pgvector/pgvector:pg16
       environment:
         POSTGRES_USER: knowledge
         POSTGRES_PASSWORD: localdev
         POSTGRES_DB: knowledge
       ports:
         - "5432:5432"
       volumes:
         - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/01_init.sql
         - ./docker/postgres/migrations:/docker-entrypoint-initdb.d/migrations
         - kas_dev_data:/var/lib/postgresql/data
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U knowledge"]
         interval: 5s
         timeout: 5s
         retries: 5

     ollama:
       image: ollama/ollama:latest
       ports:
         - "11434:11434"
       volumes:
         - ollama_models:/root/.ollama
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: 1
                 capabilities: [gpu]

     api:
       build:
         context: .
         dockerfile: Dockerfile.dev
       ports:
         - "8000:8000"
       environment:
         KNOWLEDGE_DATABASE_URL: postgresql://knowledge:localdev@db:5432/knowledge
         KNOWLEDGE_OLLAMA_URL: http://ollama:11434
       volumes:
         - ./src:/app/src
       depends_on:
         db:
           condition: service_healthy
       command: uvicorn knowledge.api.main:app --host 0.0.0.0 --reload

   volumes:
     kas_dev_data:
     ollama_models:
   ```

2. **Create seeding script**
   ```python
   # scripts/seed_dev.py
   """Seed development database with sample content."""
   import asyncio
   from knowledge.db import Database, get_db

   SAMPLE_CONTENT = [
       {
           "filepath": "dev/sample1.md",
           "content_type": "note",
           "title": "Sample Note 1",
           "content": "This is sample content for development...",
       },
       # ... more samples
   ]

   async def seed():
       db = await get_db()

       for item in SAMPLE_CONTENT:
           await db.insert_content(
               filepath=item["filepath"],
               content_type=item["content_type"],
               title=item["title"],
               content_for_hash=item["content"],
           )

       print(f"Seeded {len(SAMPLE_CONTENT)} items")

   if __name__ == "__main__":
       asyncio.run(seed())
   ```

**Review Checklist:**
- [ ] Single command starts all services
- [ ] Hot reload works for API
- [ ] Database persists across restarts
- [ ] Ollama models cached
- [ ] Seed script creates test data

---

### P36: SDK/Client Library

**Gap:** No client libraries

**Files to Create:**
- `sdk/python/kas_client/__init__.py`
- `sdk/python/kas_client/client.py`
- `sdk/typescript/src/index.ts`

**Implementation Steps:**

1. **Create Python SDK**
   ```python
   # sdk/python/kas_client/client.py
   from typing import Any
   import httpx

   class KASClient:
       def __init__(
           self,
           base_url: str = "http://localhost:8000",
           api_key: str | None = None,
           timeout: float = 30.0,
       ):
           self.base_url = base_url.rstrip("/")
           self.api_key = api_key
           self.timeout = timeout
           self._client = httpx.AsyncClient(
               base_url=self.base_url,
               timeout=timeout,
               headers=self._headers(),
           )

       def _headers(self) -> dict[str, str]:
           headers = {"Content-Type": "application/json"}
           if self.api_key:
               headers["X-API-Key"] = self.api_key
           return headers

       async def search(
           self,
           query: str,
           limit: int = 10,
           namespace: str | None = None,
           rerank: bool = False,
       ) -> list[dict]:
           response = await self._client.post(
               "/api/v1/search",
               json={
                   "query": query,
                   "limit": limit,
                   "namespace": namespace,
                   "rerank": rerank,
               },
           )
           response.raise_for_status()
           return response.json()["results"]

       async def ingest(
           self,
           content_type: str,
           source: str,
           title: str | None = None,
       ) -> dict:
           response = await self._client.post(
               "/api/v1/content",
               json={
                   "content_type": content_type,
                   "source": source,
                   "title": title,
               },
           )
           response.raise_for_status()
           return response.json()

       async def close(self):
           await self._client.aclose()

       async def __aenter__(self):
           return self

       async def __aexit__(self, *args):
           await self.close()
   ```

2. **Create TypeScript SDK**
   ```typescript
   // sdk/typescript/src/index.ts
   export interface KASClientOptions {
     baseUrl?: string;
     apiKey?: string;
     timeout?: number;
   }

   export class KASClient {
     private baseUrl: string;
     private apiKey?: string;
     private timeout: number;

     constructor(options: KASClientOptions = {}) {
       this.baseUrl = options.baseUrl ?? "http://localhost:8000";
       this.apiKey = options.apiKey;
       this.timeout = options.timeout ?? 30000;
     }

     async search(query: string, options?: SearchOptions): Promise<SearchResult[]> {
       const response = await fetch(`${this.baseUrl}/api/v1/search`, {
         method: "POST",
         headers: this.headers(),
         body: JSON.stringify({
           query,
           limit: options?.limit ?? 10,
           namespace: options?.namespace,
           rerank: options?.rerank ?? false,
         }),
       });

       if (!response.ok) {
         throw new Error(`Search failed: ${response.statusText}`);
       }

       const data = await response.json();
       return data.results;
     }

     // ... more methods
   }
   ```

**Review Checklist:**
- [ ] Python SDK published to PyPI (optional)
- [ ] TypeScript SDK published to npm (optional)
- [ ] Auth handling built in
- [ ] Retry logic included
- [ ] Type hints/TypeScript types
- [ ] Examples in README

---

## Phase 6: Production Operations

### P37: Backup & Recovery

**Gap:** No backup strategy

**Files to Create:**
- `scripts/backup.sh`
- `scripts/restore.sh`
- `docs/RECOVERY.md`

**Implementation Steps:**

1. **Create backup script**
   ```bash
   #!/bin/bash
   # scripts/backup.sh

   set -euo pipefail

   # Configuration
   BACKUP_DIR="${BACKUP_DIR:-./backups}"
   DB_HOST="${DB_HOST:-localhost}"
   DB_PORT="${DB_PORT:-5432}"
   DB_NAME="${DB_NAME:-knowledge}"
   DB_USER="${DB_USER:-knowledge}"
   RETENTION_DAYS="${RETENTION_DAYS:-7}"

   # Create backup directory
   mkdir -p "$BACKUP_DIR"

   # Generate timestamp
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   BACKUP_FILE="$BACKUP_DIR/kas_backup_$TIMESTAMP.sql.gz"

   echo "Starting backup..."

   # Dump database
   pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
       --no-owner --no-acl \
       | gzip > "$BACKUP_FILE"

   echo "Backup created: $BACKUP_FILE"

   # Cleanup old backups
   find "$BACKUP_DIR" -name "kas_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

   echo "Old backups cleaned up (retention: $RETENTION_DAYS days)"

   # Verify backup
   if gzip -t "$BACKUP_FILE"; then
       echo "Backup verified successfully"
   else
       echo "ERROR: Backup verification failed!"
       exit 1
   fi
   ```

2. **Create restore script**
   ```bash
   #!/bin/bash
   # scripts/restore.sh

   set -euo pipefail

   BACKUP_FILE="${1:-}"

   if [ -z "$BACKUP_FILE" ]; then
       echo "Usage: restore.sh <backup_file>"
       exit 1
   fi

   if [ ! -f "$BACKUP_FILE" ]; then
       echo "ERROR: Backup file not found: $BACKUP_FILE"
       exit 1
   fi

   echo "WARNING: This will overwrite the current database!"
   read -p "Continue? (y/N) " confirm

   if [ "$confirm" != "y" ]; then
       echo "Aborted"
       exit 0
   fi

   echo "Restoring from $BACKUP_FILE..."

   gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"

   echo "Restore complete"
   ```

3. **Create recovery documentation**
   ```markdown
   # docs/RECOVERY.md

   ## Backup Schedule

   - **Daily**: Full database dump at 02:00 UTC
   - **Retention**: 7 days

   ## Backup Location

   Backups stored in `./backups/` or configured `$BACKUP_DIR`

   ## Recovery Procedures

   ### Full Database Restore

   1. Stop the API server
   2. Run restore: `./scripts/restore.sh backups/kas_backup_YYYYMMDD_HHMMSS.sql.gz`
   3. Verify data: `kas doctor`
   4. Restart API server

   ### Point-in-Time Recovery

   Requires WAL archiving (not configured by default).

   ### Partial Recovery

   To restore specific content:
   1. Restore to a temporary database
   2. Export needed records
   3. Import to production
   ```

**Review Checklist:**
- [ ] Backup script creates compressed dumps
- [ ] Restore script with confirmation
- [ ] Retention policy implemented
- [ ] Backup verification
- [ ] Recovery documentation
- [ ] Can be scheduled via cron

---

### P38: Deployment Automation

**Gap:** Manual deployment only

**Files to Create:**
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `Dockerfile`

**Implementation Steps:**

1. **Create CI workflow**
   ```yaml
   # .github/workflows/ci.yml
   name: CI

   on:
     push:
       branches: [main, feat/*]
     pull_request:
       branches: [main]

   jobs:
     test:
       runs-on: ubuntu-latest

       services:
         postgres:
           image: pgvector/pgvector:pg16
           env:
             POSTGRES_USER: knowledge
             POSTGRES_PASSWORD: testpass
             POSTGRES_DB: knowledge_test
           ports:
             - 5432:5432
           options: >-
             --health-cmd pg_isready
             --health-interval 10s
             --health-timeout 5s
             --health-retries 5

       steps:
         - uses: actions/checkout@v4

         - name: Install uv
           uses: astral-sh/setup-uv@v4

         - name: Set up Python
           run: uv python install 3.12

         - name: Install dependencies
           run: uv sync --all-extras

         - name: Run linting
           run: |
             uv run ruff check src/
             uv run ruff format --check src/

         - name: Run type checking
           run: uv run mypy src/knowledge/

         - name: Run tests
           run: uv run pytest tests/ -v --cov=knowledge
           env:
             KNOWLEDGE_DATABASE_URL: postgresql://knowledge:testpass@localhost:5432/knowledge_test

         - name: Run security scan
           run: uv run bandit -r src/knowledge/

     build:
       runs-on: ubuntu-latest
       needs: test

       steps:
         - uses: actions/checkout@v4

         - name: Build Docker image
           run: docker build -t kas:${{ github.sha }} .
   ```

2. **Create Dockerfile**
   ```dockerfile
   # Dockerfile
   FROM python:3.12-slim

   WORKDIR /app

   # Install uv
   COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

   # Copy dependency files
   COPY pyproject.toml uv.lock ./

   # Install dependencies
   RUN uv sync --frozen --no-dev

   # Copy application
   COPY src/ ./src/
   COPY cli.py ./

   # Expose port
   EXPOSE 8000

   # Run
   CMD ["uv", "run", "uvicorn", "knowledge.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

3. **Create release workflow**
   ```yaml
   # .github/workflows/release.yml
   name: Release

   on:
     push:
       tags:
         - 'v*'

   jobs:
     release:
       runs-on: ubuntu-latest

       steps:
         - uses: actions/checkout@v4

         - name: Build and push Docker image
           uses: docker/build-push-action@v5
           with:
             push: true
             tags: |
               ghcr.io/${{ github.repository }}:${{ github.ref_name }}
               ghcr.io/${{ github.repository }}:latest
   ```

**Review Checklist:**
- [ ] CI runs on PR and push
- [ ] Tests run with real Postgres
- [ ] Linting and type checking
- [ ] Security scanning
- [ ] Docker image builds
- [ ] Release workflow publishes image

---

## Summary

This implementation plan covers 27 priorities (P12-P38) with:

- **~150-200 implementation tasks**
- **~100 new tests**
- **~15 new files**
- **~30 modified files**

### Execution Timeline (Suggested)

| Batch | Priorities | Scope |
|-------|------------|-------|
| 1 | P12-P15 | Foundation |
| 2 | P16-P18 | Security |
| 3 | P19-P22 | API Features |
| 4 | P23-P27 | Reliability |
| 5 | P28-P32 | Testing |
| 6 | P33-P36 | Developer Experience |
| 7 | P37-P38 | Production |

### Key Dependencies

- P14 (Error Handling) should come before P26 (Circuit Breaker)
- P15 (Logging) should come before P24 (Metrics) and P25 (Tracing)
- P17 (Authentication) should come before P18 (Rate Limiting)
- P28 (Integration Tests) should come before P29 (Load Testing)

---

**Document Version:** 1.0
**Last Updated:** 2026-01-13

# MLX Model Hub - Comprehensive Implementation Plan

**Version:** 1.0.0
**Created:** 2026-01-11
**Status:** Awaiting Approval
**Philosophy:** Quality over speed. Solid, stable, safe. Backend-first. TDD strictly enforced.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technical Decisions](#2-technical-decisions)
3. [Architecture Overview](#3-architecture-overview)
4. [Dependency Graph](#4-dependency-graph)
5. [Phase 1: Foundation](#5-phase-1-foundation-tasks-1-3)
6. [Phase 2: Data & Orchestration](#6-phase-2-data--orchestration-tasks-4-5)
7. [Phase 3: ML Core](#7-phase-3-ml-core-tasks-6-7)
8. [Phase 4: Operations](#8-phase-4-operations-tasks-8-9)
9. [Phase 5: Frontend](#9-phase-5-frontend-tasks-10-12)
10. [Success Criteria](#10-success-criteria)
11. [Risk Register](#11-risk-register)
12. [Audit Checklist](#12-audit-checklist)
13. [References](#13-references)

---

## 1. Executive Summary

### Purpose
Build a local-first MLX Model Hub optimized for Apple Silicon (M4 Pro, 48GB) that provides:
- Model registry with versioning and lineage tracking
- Training orchestration for fine-tuning (LoRA/QLoRA)
- Inference serving with streaming support
- Observability via metrics dashboard and admin UI

### Scope
- **In Scope:** Single-node local deployment, model CRUD, training jobs, inference API, admin dashboard
- **Out of Scope:** Multi-node distribution, cloud deployment, enterprise auth, model marketplace

### Key Metrics
| Metric | Target |
|--------|--------|
| Tasks | 12 |
| Subtasks | 63 |
| Phases | 5 |
| Inference TTFT | < 100ms (7B 4-bit) |
| Memory Budget | 36GB for MLX |
| Stability | 24h training without OOM |

---

## 2. Technical Decisions

### 2.1 Confirmed Decisions

| Area | Decision | Rationale |
|------|----------|-----------|
| **Base Models** | All sizes (1B-13B+) | Auto-enforce quantization for larger models |
| **Data Format** | JSONL chat format | `{messages: [{role, content}]}` ShareGPT-style standard |
| **Authentication** | None (localhost only) | Bind to 127.0.0.1, no external exposure |
| **Inference Concurrency** | Single request | One at a time, predictable memory |
| **Artifact Organization** | Hierarchical by model | `storage/models/{name}/versions/{v}/adapter.safetensors` |
| **Job Worker** | In-process BackgroundTasks | FastAPI native, simplest for single-node |
| **Database** | New dedicated Postgres container | Clean isolation in project docker-compose |
| **Memory Limit** | 36GB for MLX | 48GB total - 12GB headroom |
| **Development Order** | Backend first | Tasks 1-9 complete before frontend |

### 2.2 Technology Stack

#### Backend
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Web Framework | FastAPI | >=0.128.0 | REST API with async support |
| ASGI Server | Uvicorn | >=0.30.0 | Production server |
| ORM | SQLModel | >=0.0.22 | Pydantic + SQLAlchemy integration |
| Migrations | Alembic | >=1.14.0 | Database schema versioning |
| Config | pydantic-settings | >=2.5.0 | Environment-based configuration |
| ML Tracking | MLflow | >=3.8.0 | Experiment tracking, model registry |
| ML Framework | MLX | >=0.30.0 | Apple Silicon optimized training |
| LLM Tools | mlx-lm | >=0.21.0 | Model loading, LoRA, inference |
| Tracing | OpenTelemetry | >=0.48b0 | Distributed tracing |
| Metrics | prometheus-client | >=0.21.0 | Prometheus metrics |
| SSE | sse-starlette | >=3.1.0 | Server-sent events streaming |
| Testing | pytest | >=8.0.0 | Test framework |
| HTTP Client | httpx | >=0.27.0 | Async HTTP testing |
| Linting | ruff | >=0.8.0 | Fast Python linter |
| Async DB Driver | asyncpg | >=0.30.0 | PostgreSQL async driver |

#### Frontend
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Framework | Next.js | >=15.0.0 | React framework with App Router |
| UI Library | React | >=19.0.0 | Component library |
| Components | shadcn/ui | latest | Accessible component system |
| Charts | Recharts | >=2.13.0 | Data visualization |
| Data Fetching | TanStack Query | >=5.0.0 | Client-side data management |
| Testing | Playwright | >=1.48.0 | E2E testing |

#### Infrastructure
| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Containers | Docker Compose | v3.8 | Local orchestration |
| Database | PostgreSQL | 17 | Metadata storage |
| ML Tracking | MLflow Server | >=3.8.0 | UI and API |
| Metrics DB | Prometheus | latest | Time-series metrics |
| Dashboards | Grafana | latest | Visualization |

---

## 3. Architecture Overview

### 3.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MLX Model Hub                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │   Next.js 15     │    │    FastAPI       │    │   MLX Runtime    │  │
│  │   Dashboard      │───▶│    Backend       │───▶│   (Training/     │  │
│  │   (Frontend)     │    │    (API)         │    │    Inference)    │  │
│  └──────────────────┘    └────────┬─────────┘    └──────────────────┘  │
│                                   │                                      │
│                    ┌──────────────┼──────────────┐                      │
│                    │              │              │                      │
│                    ▼              ▼              ▼                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐     │
│  │   PostgreSQL     │  │     MLflow       │  │    Prometheus    │     │
│  │   (Metadata)     │  │   (Tracking)     │  │    (Metrics)     │     │
│  └──────────────────┘  └──────────────────┘  └────────┬─────────┘     │
│                                                        │                │
│                                              ┌─────────▼────────┐      │
│                                              │     Grafana      │      │
│                                              │   (Dashboards)   │      │
│                                              └──────────────────┘      │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                     Local File System                             │  │
│  │  storage/models/{name}/versions/{v}/adapter.safetensors          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

```
1. REGISTRATION
   Client → POST /models → Validate → Create DB Row → Create MLflow Experiment → Return 201

2. TRAINING
   Client → POST /training/jobs → Validate → Queue Job → Worker Picks Up
   Worker → Load Model → Load Dataset → Train with MLX → Save Adapter → Log to MLflow → Update Status

3. INFERENCE
   Client → POST /inference → Load Model (or cache hit) → Generate → Return Response
   Client → POST /inference/stream → Load Model → Stream Tokens via SSE → Done Event
```

### 3.3 Directory Structure

```
mlx-model-hub/
├── .taskmaster/
│   ├── docs/
│   │   └── prd.txt
│   ├── tasks/
│   │   └── tasks.json
│   └── .taskmasterrc
├── backend/
│   ├── src/
│   │   └── mlx_hub/
│   │       ├── __init__.py
│   │       ├── main.py                 # FastAPI app entry point
│   │       ├── config.py               # pydantic-settings configuration
│   │       ├── api/
│   │       │   ├── __init__.py
│   │       │   ├── models.py           # /models endpoints
│   │       │   ├── datasets.py         # /datasets endpoints
│   │       │   ├── training.py         # /training/jobs endpoints
│   │       │   ├── inference.py        # /inference endpoints
│   │       │   └── health.py           # /health, /metrics endpoints
│   │       ├── db/
│   │       │   ├── __init__.py
│   │       │   ├── models.py           # SQLModel classes
│   │       │   ├── session.py          # AsyncSession management
│   │       │   └── enums.py            # Status enums
│   │       ├── training/
│   │       │   ├── __init__.py
│   │       │   ├── worker.py           # Background job worker
│   │       │   └── runner.py           # MLX training runner
│   │       ├── inference/
│   │       │   ├── __init__.py
│   │       │   ├── engine.py           # InferenceEngine class
│   │       │   └── cache.py            # LRU model cache
│   │       └── observability/
│   │           ├── __init__.py
│   │           ├── metrics.py          # Prometheus metrics
│   │           └── tracing.py          # OpenTelemetry setup
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Shared fixtures
│   │   ├── test_config.py
│   │   ├── test_models_api.py
│   │   ├── test_datasets_api.py
│   │   ├── test_training_api.py
│   │   ├── test_inference_api.py
│   │   └── test_db_constraints.py
│   ├── migrations/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── models/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── training/
│   │   │   └── page.tsx
│   │   ├── inference/
│   │   │   └── page.tsx
│   │   └── metrics/
│   │       └── page.tsx
│   ├── components/
│   │   └── ui/                         # shadcn components
│   ├── lib/
│   │   ├── api.ts                      # API client
│   │   └── hooks/                      # TanStack Query hooks
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.js
│   └── playwright.config.ts
├── storage/
│   ├── models/                         # Model artifacts (hierarchical)
│   │   └── .gitkeep
│   └── datasets/                       # Dataset storage
│       └── .gitkeep
├── docker/
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── dashboards/
│           └── mlx-hub.json
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── IMPLEMENTATION_PLAN.md              # This document
```

---

## 4. Dependency Graph

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    PHASE 1: Foundation                  │
                    ├─────────────────────────────────────────────────────────┤
                    │                                                          │
                    │  ┌────────────┐                                         │
                    │  │  Task 1    │ Project Scaffolding                     │
                    │  │ (no deps)  │                                         │
                    │  └─────┬──────┘                                         │
                    │        │                                                 │
                    │        ▼                                                 │
                    │  ┌────────────┐                                         │
                    │  │  Task 2    │ Database Schema                         │
                    │  │ (deps: 1)  │                                         │
                    │  └─────┬──────┘                                         │
                    │        │                                                 │
                    │        ▼                                                 │
                    │  ┌────────────┐                                         │
                    │  │  Task 3    │ Model Registry API                      │
                    │  │ (deps: 2)  │                                         │
                    │  └─────┬──────┘                                         │
                    │        │                                                 │
                    └────────┼────────────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    │                    ▼
┌───────────────────┐        │        ┌───────────────────────────────────────┐
│  PHASE 2          │        │        │  PHASE 5: Frontend (after backend)   │
├───────────────────┤        │        ├───────────────────────────────────────┤
│                   │        │        │                                        │
│  ┌────────────┐   │        │        │  ┌────────────┐                       │
│  │  Task 4    │   │        │        │  │  Task 10   │ Frontend Setup        │
│  │ (deps: 2)  │   │        └───────▶│  │ (deps: 3)  │                       │
│  │ Datasets   │   │                 │  └─────┬──────┘                       │
│  └─────┬──────┘   │                 │        │                               │
│        │          │                 │        ▼                               │
│        └─────┐    │                 │  ┌────────────┐                       │
│              │    │                 │  │  Task 11   │ Core Pages            │
│              ▼    │                 │  │ (deps: 10) │                       │
│        ┌────────────┐               │  └─────┬──────┘                       │
│        │  Task 5    │               │        │                               │
│        │ (deps:3,4) │               │        │                               │
│        │ Orchestr.  │               │        │                               │
│        └─────┬──────┘               │        │                               │
│              │                      │        │                               │
└──────────────┼──────────────────────┤        │                               │
               │                      │        │                               │
               ▼                      │        │                               │
┌───────────────────┐                 │        │                               │
│  PHASE 3: ML Core │                 │        │                               │
├───────────────────┤                 │        │                               │
│                   │                 │        │                               │
│  ┌────────────┐   │                 │        │                               │
│  │  Task 6    │   │                 │        │                               │
│  │ (deps: 5)  │   │                 │        │                               │
│  │ Training   │   │                 │        │                               │
│  └─────┬──────┘   │                 │        │                               │
│        │          │                 │        │                               │
│        ▼          │                 │        │                               │
│  ┌────────────┐   │                 │        │                               │
│  │  Task 7    │   │                 │        │                               │
│  │ (deps: 6)  │   │                 │        │                               │
│  │ Inference  │   │                 │        │                               │
│  └─────┬──────┘   │                 │        │                               │
│        │          │                 │        │                               │
└────────┼──────────┘                 │        │                               │
         │                            │        │                               │
         ▼                            │        │                               │
┌───────────────────┐                 │        │                               │
│  PHASE 4: Ops     │                 │        │                               │
├───────────────────┤                 │        │                               │
│                   │                 │        │                               │
│  ┌────────────┐   │                 │        │                               │
│  │  Task 8    │   │                 │        │                               │
│  │ (deps:3,7) │   │                 │        │                               │
│  │ Observ.    │   │                 │        │                               │
│  └─────┬──────┘   │                 │        │                               │
│        │          │                 │        │                               │
│        ▼          │                 │        │                               │
│  ┌────────────┐   │                 │        │                               │
│  │  Task 9    │◀──┼─────────────────┼────────┘                               │
│  │ (deps: 8)  │   │                 │                                        │
│  │ Docker     │   │                 │  ┌────────────┐                       │
│  └─────┬──────┘   │                 │  │  Task 12   │ E2E Tests + Docs      │
│        │          │                 │  │(deps:9,11) │                       │
└────────┼──────────┘                 │  └────────────┘                       │
         │                            │                                        │
         └────────────────────────────┴────────────────────────────────────────┘

CRITICAL PATH: 1 → 2 → 3 → 5 → 6 → 7 → 8 → 9 → 12
```

---

## 5. Phase 1: Foundation (Tasks 1-3)

### Task 1: Project Scaffolding and Environment Setup

**Objective:** Initialize the project structure with uv, configure dependencies, create storage directories, and set up configuration management.

**Dependencies:** None

**Estimated Effort:** 2-3 hours

#### Subtask 1.1: Initialize uv project with pyproject.toml

**Description:** Create the Python project configuration with all backend dependencies.

**Steps:**
1. Navigate to `mlx-model-hub/backend/`
2. Run `uv init --package --name mlx-hub`
3. Edit `pyproject.toml` with full dependency list

**Files to Create:**
```toml
# backend/pyproject.toml
[project]
name = "mlx-hub"
version = "0.1.0"
description = "Local-first MLX Model Hub for Apple Silicon"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.128.0",
    "uvicorn[standard]>=0.30.0",
    "sqlmodel>=0.0.22",
    "alembic>=1.14.0",
    "pydantic-settings>=2.5.0",
    "mlflow>=3.8.0",
    "mlx>=0.30.0",
    "mlx-lm>=0.21.0",
    "opentelemetry-api>=1.28.0",
    "opentelemetry-sdk>=1.28.0",
    "opentelemetry-instrumentation-fastapi>=0.48b0",
    "prometheus-client>=0.21.0",
    "sse-starlette>=3.1.0",
    "asyncpg>=0.30.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "ruff>=0.8.0",
    "mypy>=1.13.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
```

**Verification:**
```bash
cd backend && uv sync
uv run python -c "import fastapi; import mlx; print('OK')"
```

#### Subtask 1.2: Create backend directory structure

**Description:** Create all necessary directories and `__init__.py` files.

**Steps:**
1. Create directory tree as shown in Directory Structure section
2. Add `__init__.py` to all Python package directories
3. Create placeholder files

**Commands:**
```bash
mkdir -p backend/src/mlx_hub/{api,db,training,inference,observability}
mkdir -p backend/tests
mkdir -p backend/migrations/versions
touch backend/src/mlx_hub/__init__.py
touch backend/src/mlx_hub/{api,db,training,inference,observability}/__init__.py
```

#### Subtask 1.3: Implement config.py with pydantic-settings

**Description:** Create configuration management using pydantic-settings for type-safe environment variable handling.

**Files to Create:**
```python
# backend/src/mlx_hub/config.py
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "MLX Model Hub"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://mlxhub:mlxhub@localhost:5432/mlxhub"

    # MLflow
    mlflow_tracking_uri: str = "http://localhost:5001"

    # Storage
    storage_base_path: Path = Path("./storage")
    storage_models_path: Path = Path("./storage/models")
    storage_datasets_path: Path = Path("./storage/datasets")

    # MLX
    mlx_memory_limit_gb: int = 36
    mlx_default_quantization: Literal["4bit", "8bit", "none"] = "4bit"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    def ensure_directories(self) -> None:
        """Create storage directories if they don't exist."""
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
        self.storage_models_path.mkdir(parents=True, exist_ok=True)
        self.storage_datasets_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.ensure_directories()
    return settings
```

#### Subtask 1.4: Create storage directories

**Description:** Create the hierarchical storage structure for models and datasets.

**Commands:**
```bash
mkdir -p storage/models
mkdir -p storage/datasets
touch storage/models/.gitkeep
touch storage/datasets/.gitkeep
```

**Add to .gitignore:**
```
# Storage (keep structure, ignore contents)
storage/models/*
!storage/models/.gitkeep
storage/datasets/*
!storage/datasets/.gitkeep
```

#### Subtask 1.5: Configure pytest and ruff

**Description:** Set up testing and linting configuration.

**Files to Create:**
```python
# backend/tests/conftest.py
import asyncio
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from mlx_hub.config import Settings, get_settings
from mlx_hub.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def settings() -> Settings:
    """Get test settings."""
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        storage_base_path="./test_storage",
        storage_models_path="./test_storage/models",
        storage_datasets_path="./test_storage/datasets",
    )


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
```

#### Subtask 1.6: Write first failing test (TDD)

**Description:** Create the first test that validates configuration loading.

**Files to Create:**
```python
# backend/tests/test_config.py
import os
from pathlib import Path

import pytest

from mlx_hub.config import Settings, get_settings


class TestSettings:
    """Test configuration management."""

    def test_settings_load_defaults(self):
        """Settings should load with sensible defaults."""
        settings = Settings()

        assert settings.app_name == "MLX Model Hub"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000

    def test_settings_load_from_env(self, monkeypatch):
        """Settings should load from environment variables."""
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("PORT", "9000")

        # Clear cache to reload settings
        get_settings.cache_clear()
        settings = Settings()

        assert settings.debug is True
        assert settings.log_level == "DEBUG"
        assert settings.port == 9000

    def test_settings_database_url_format(self):
        """Database URL should be valid asyncpg format."""
        settings = Settings()

        assert "postgresql+asyncpg://" in settings.database_url

    def test_storage_directories_created(self, tmp_path):
        """Storage directories should be created on initialization."""
        settings = Settings(
            storage_base_path=tmp_path / "storage",
            storage_models_path=tmp_path / "storage/models",
            storage_datasets_path=tmp_path / "storage/datasets",
        )
        settings.ensure_directories()

        assert settings.storage_base_path.exists()
        assert settings.storage_models_path.exists()
        assert settings.storage_datasets_path.exists()

    def test_mlx_memory_limit_reasonable(self):
        """MLX memory limit should be within hardware constraints."""
        settings = Settings()

        # Should be less than 48GB total, leaving headroom
        assert settings.mlx_memory_limit_gb <= 36
        assert settings.mlx_memory_limit_gb > 0

    def test_get_settings_cached(self):
        """get_settings should return cached instance."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
```

**Verification:**
```bash
cd backend
uv run pytest tests/test_config.py -v
# Should pass after implementing config.py
```

**Acceptance Criteria:**
- [ ] `uv sync` completes without errors
- [ ] `python -c "import mlx"` succeeds
- [ ] All tests in `test_config.py` pass
- [ ] Storage directories exist and are writable
- [ ] Ruff linting passes with no errors

**Potential Issues:**
| Issue | Mitigation |
|-------|------------|
| MLX not found on non-Apple hardware | Skip MLX import in tests, use CI with Apple runners |
| asyncpg requires Postgres running | Use SQLite for unit tests, Postgres for integration |
| Environment variable conflicts | Use unique test env vars, clear cache between tests |

---

### Task 2: Database Schema and Migrations

**Objective:** Define SQLModel classes for Model, ModelVersion, Dataset, and TrainingJob with proper relationships and constraints. Set up Alembic for migrations.

**Dependencies:** Task 1

**Estimated Effort:** 3-4 hours

#### Subtask 2.1: Create SQLModel base classes

**Description:** Define all database models with SQLModel, including proper typing and relationships.

**Files to Create:**
```python
# backend/src/mlx_hub/db/models.py
from datetime import datetime
from typing import Optional
import uuid

from sqlmodel import Field, Relationship, SQLModel

from .enums import JobStatus, ModelVersionStatus, TaskType


class ModelBase(SQLModel):
    """Base model fields."""
    name: str = Field(index=True, unique=True, max_length=255)
    task_type: TaskType = Field(default=TaskType.TEXT_GENERATION)
    description: Optional[str] = Field(default=None, max_length=2000)
    base_model: str = Field(max_length=500)  # HuggingFace model ID
    tags: dict = Field(default_factory=dict, sa_type=JSON)


class Model(ModelBase, table=True):
    """Registered model in the hub."""
    __tablename__ = "models"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    mlflow_experiment_id: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    versions: list["ModelVersion"] = Relationship(back_populates="model")
    training_jobs: list["TrainingJob"] = Relationship(back_populates="model")


class ModelVersionBase(SQLModel):
    """Base model version fields."""
    version: str = Field(max_length=50)  # semver format
    status: ModelVersionStatus = Field(default=ModelVersionStatus.TRAINING)
    metrics: dict = Field(default_factory=dict, sa_type=JSON)
    artifact_path: Optional[str] = Field(default=None, max_length=1000)


class ModelVersion(ModelVersionBase, table=True):
    """Specific version of a model with trained weights."""
    __tablename__ = "model_versions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_id: uuid.UUID = Field(foreign_key="models.id", index=True)
    mlflow_run_id: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    model: Model = Relationship(back_populates="versions")


class DatasetBase(SQLModel):
    """Base dataset fields."""
    name: str = Field(index=True, unique=True, max_length=255)
    path: str = Field(max_length=1000)
    checksum: str = Field(max_length=64)  # SHA256
    schema_info: dict = Field(default_factory=dict, sa_type=JSON)


class Dataset(DatasetBase, table=True):
    """Registered dataset for training."""
    __tablename__ = "datasets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    training_jobs: list["TrainingJob"] = Relationship(back_populates="dataset")


class TrainingJobBase(SQLModel):
    """Base training job fields."""
    status: JobStatus = Field(default=JobStatus.QUEUED, index=True)
    config: dict = Field(default_factory=dict, sa_type=JSON)
    error_message: Optional[str] = Field(default=None, max_length=5000)


class TrainingJob(TrainingJobBase, table=True):
    """Training job for fine-tuning a model."""
    __tablename__ = "training_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_id: uuid.UUID = Field(foreign_key="models.id", index=True)
    dataset_id: uuid.UUID = Field(foreign_key="datasets.id", index=True)
    model_version_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="model_versions.id"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    heartbeat_at: Optional[datetime] = Field(default=None)

    # Relationships
    model: Model = Relationship(back_populates="training_jobs")
    dataset: Dataset = Relationship(back_populates="training_jobs")
```

#### Subtask 2.2: Define enums for status fields

**Description:** Create type-safe enums for all status fields.

**Files to Create:**
```python
# backend/src/mlx_hub/db/enums.py
from enum import Enum


class TaskType(str, Enum):
    """Types of ML tasks supported."""
    TEXT_GENERATION = "text-generation"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question-answering"
    CHAT = "chat"


class ModelVersionStatus(str, Enum):
    """Status of a model version."""
    TRAINING = "training"
    READY = "ready"
    ARCHIVED = "archived"
    FAILED = "failed"


class JobStatus(str, Enum):
    """Status of a training job."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

#### Subtask 2.3: Initialize Alembic

**Description:** Set up Alembic for async migrations with SQLModel.

**Commands:**
```bash
cd backend
uv run alembic init -t async migrations
```

**Files to Modify:**
```python
# backend/migrations/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

# Import all models to register them with SQLModel.metadata
from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob
from mlx_hub.config import get_settings

config = context.config
settings = get_settings()

# Set database URL from settings
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        user_module_prefix="sqlmodel.sql.sqltypes.",
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        user_module_prefix="sqlmodel.sql.sqltypes.",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

#### Subtask 2.4: Create initial migration

**Description:** Generate the initial database migration with proper indexes.

**Commands:**
```bash
cd backend
uv run alembic revision --autogenerate -m "initial_schema"
uv run alembic upgrade head
```

**Verification:**
```bash
# Check migration was created
ls backend/migrations/versions/

# Apply migration (requires Postgres running)
docker compose up -d postgres
uv run alembic upgrade head
```

#### Subtask 2.5: Write constraint tests

**Description:** Test that database constraints are properly enforced.

**Files to Create:**
```python
# backend/tests/test_db_constraints.py
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from mlx_hub.db.models import Dataset, Model, ModelVersion, TrainingJob
from mlx_hub.db.enums import TaskType, ModelVersionStatus, JobStatus


class TestDatabaseConstraints:
    """Test database constraint enforcement."""

    @pytest.mark.asyncio
    async def test_model_name_unique(self, db_session: AsyncSession):
        """Model names must be unique."""
        model1 = Model(
            name="test-model",
            base_model="meta-llama/Llama-3.2-1B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model1)
        await db_session.commit()

        model2 = Model(
            name="test-model",  # Duplicate name
            base_model="meta-llama/Llama-3.2-3B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_model_version_requires_model(self, db_session: AsyncSession):
        """ModelVersion must reference existing Model."""
        version = ModelVersion(
            model_id=uuid.uuid4(),  # Non-existent model
            version="1.0.0",
            status=ModelVersionStatus.TRAINING,
        )
        db_session.add(version)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_training_job_requires_model_and_dataset(
        self, db_session: AsyncSession
    ):
        """TrainingJob must reference existing Model and Dataset."""
        job = TrainingJob(
            model_id=uuid.uuid4(),  # Non-existent
            dataset_id=uuid.uuid4(),  # Non-existent
            status=JobStatus.QUEUED,
            config={"lora_rank": 16},
        )
        db_session.add(job)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_dataset_name_unique(self, db_session: AsyncSession):
        """Dataset names must be unique."""
        dataset1 = Dataset(
            name="training-data",
            path="/data/train.jsonl",
            checksum="abc123",
        )
        db_session.add(dataset1)
        await db_session.commit()

        dataset2 = Dataset(
            name="training-data",  # Duplicate
            path="/data/train2.jsonl",
            checksum="def456",
        )
        db_session.add(dataset2)

        with pytest.raises(IntegrityError):
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_cascade_delete_model_versions(self, db_session: AsyncSession):
        """Deleting a Model should cascade to its versions."""
        model = Model(
            name="cascade-test",
            base_model="meta-llama/Llama-3.2-1B",
            task_type=TaskType.TEXT_GENERATION,
        )
        db_session.add(model)
        await db_session.commit()
        await db_session.refresh(model)

        version = ModelVersion(
            model_id=model.id,
            version="1.0.0",
            status=ModelVersionStatus.READY,
        )
        db_session.add(version)
        await db_session.commit()

        # Delete model
        await db_session.delete(model)
        await db_session.commit()

        # Version should be deleted too
        result = await db_session.exec(
            select(ModelVersion).where(ModelVersion.model_id == model.id)
        )
        assert result.first() is None
```

**Acceptance Criteria:**
- [ ] `alembic upgrade head` runs without errors
- [ ] FK constraints enforced (version without model fails)
- [ ] Unique constraints enforced (duplicate model name fails)
- [ ] Indexes created on `Model.name`, `ModelVersion.version`, `TrainingJob.status`
- [ ] All constraint tests pass

**Potential Issues:**
| Issue | Mitigation |
|-------|------------|
| Migration drift between environments | Always run `alembic upgrade head` before tests |
| SQLite doesn't enforce FK by default | Add `PRAGMA foreign_keys = ON` in test setup |
| JSON column type varies by DB | Use SQLAlchemy's `JSON` type for portability |

---

### Task 3: Model Registry API with MLflow Integration

**Objective:** Implement FastAPI router for model CRUD operations with MLflow experiment creation and tracking.

**Dependencies:** Task 2

**Estimated Effort:** 4-5 hours

#### Subtask 3.1: Create async database session dependency

**Description:** Implement the database session factory and dependency injection.

**Files to Create:**
```python
# backend/src/mlx_hub/db/session.py
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from mlx_hub.config import Settings, get_settings


def get_engine(settings: Settings):
    """Create async database engine."""
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
    )


def get_session_factory(settings: Settings):
    """Create async session factory."""
    engine = get_engine(settings)
    return sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    settings: Annotated[Settings, Depends(get_settings)]
) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for request."""
    session_factory = get_session_factory(settings)
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_session)]
```

#### Subtask 3.2: Implement model router

**Description:** Create the FastAPI router for model endpoints.

**Files to Create:**
```python
# backend/src/mlx_hub/api/models.py
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import select

from mlx_hub.db.models import Model, ModelVersion
from mlx_hub.db.session import SessionDep
from mlx_hub.db.enums import TaskType

router = APIRouter(prefix="/models", tags=["models"])


# Request/Response schemas
class ModelCreate(SQLModel):
    """Request schema for creating a model."""
    name: str
    task_type: TaskType = TaskType.TEXT_GENERATION
    description: Optional[str] = None
    base_model: str
    tags: dict = {}


class ModelResponse(SQLModel):
    """Response schema for a model."""
    id: UUID
    name: str
    task_type: TaskType
    description: Optional[str]
    base_model: str
    tags: dict
    mlflow_experiment_id: Optional[str]
    created_at: datetime
    version_count: int = 0


class ModelListResponse(SQLModel):
    """Response schema for model list."""
    items: list[ModelResponse]
    total: int
    page: int
    page_size: int


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ModelResponse)
async def create_model(
    model_in: ModelCreate,
    session: SessionDep,
) -> ModelResponse:
    """Register a new model in the hub."""
    # Check for duplicate name
    existing = await session.exec(
        select(Model).where(Model.name == model_in.name)
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model with name '{model_in.name}' already exists",
        )

    # Create model
    model = Model(**model_in.model_dump())
    session.add(model)
    await session.commit()
    await session.refresh(model)

    # TODO: Create MLflow experiment (Subtask 3.3)

    return ModelResponse(
        **model.model_dump(),
        version_count=0,
    )


@router.get("", response_model=ModelListResponse)
async def list_models(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    task_type: Optional[TaskType] = None,
) -> ModelListResponse:
    """List all registered models with pagination."""
    # Build query
    query = select(Model)
    if task_type:
        query = query.where(Model.task_type == task_type)

    # Get total count
    count_query = select(func.count()).select_from(Model)
    if task_type:
        count_query = count_query.where(Model.task_type == task_type)
    total = await session.exec(count_query)

    # Get paginated results
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Model.created_at.desc())

    result = await session.exec(query)
    models = result.all()

    # Get version counts
    items = []
    for model in models:
        version_count = len(model.versions) if model.versions else 0
        items.append(ModelResponse(
            **model.model_dump(),
            version_count=version_count,
        ))

    return ModelListResponse(
        items=items,
        total=total.first() or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: UUID,
    session: SessionDep,
) -> ModelResponse:
    """Get a specific model by ID."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    return ModelResponse(
        **model.model_dump(),
        version_count=len(model.versions) if model.versions else 0,
    )


@router.get("/{model_id}/history")
async def get_model_history(
    model_id: UUID,
    session: SessionDep,
) -> dict:
    """Get MLflow run history for a model."""
    model = await session.get(Model, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found",
        )

    if not model.mlflow_experiment_id:
        return {"runs": [], "experiment_id": None}

    # TODO: Fetch from MLflow (Subtask 3.3)
    return {
        "runs": [],
        "experiment_id": model.mlflow_experiment_id,
    }
```

#### Subtask 3.3: Integrate MLflow experiment creation

**Description:** Create MLflow experiments when models are registered.

**Files to Create:**
```python
# backend/src/mlx_hub/api/mlflow_client.py
from typing import Optional
import logging

import mlflow
from mlflow.tracking import MlflowClient

from mlx_hub.config import get_settings

logger = logging.getLogger(__name__)


class MLflowService:
    """Service for MLflow operations."""

    def __init__(self):
        settings = get_settings()
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        self.client = MlflowClient()

    def create_experiment(self, name: str, tags: Optional[dict] = None) -> str:
        """Create a new MLflow experiment."""
        try:
            experiment_id = mlflow.create_experiment(
                name=name,
                tags=tags or {},
            )
            logger.info(f"Created MLflow experiment: {name} (ID: {experiment_id})")
            return experiment_id
        except Exception as e:
            logger.error(f"Failed to create MLflow experiment: {e}")
            raise

    def get_experiment_runs(self, experiment_id: str) -> list[dict]:
        """Get all runs for an experiment."""
        try:
            runs = self.client.search_runs(
                experiment_ids=[experiment_id],
                order_by=["start_time DESC"],
            )
            return [
                {
                    "run_id": run.info.run_id,
                    "status": run.info.status,
                    "start_time": run.info.start_time,
                    "end_time": run.info.end_time,
                    "metrics": run.data.metrics,
                    "params": run.data.params,
                }
                for run in runs
            ]
        except Exception as e:
            logger.error(f"Failed to get MLflow runs: {e}")
            return []

    def is_available(self) -> bool:
        """Check if MLflow server is available."""
        try:
            self.client.search_experiments()
            return True
        except Exception:
            return False


def get_mlflow_service() -> MLflowService:
    """Get MLflow service instance."""
    return MLflowService()
```

**Update create_model in models.py:**
```python
@router.post("", status_code=status.HTTP_201_CREATED, response_model=ModelResponse)
async def create_model(
    model_in: ModelCreate,
    session: SessionDep,
    mlflow_service: Annotated[MLflowService, Depends(get_mlflow_service)],
) -> ModelResponse:
    """Register a new model in the hub."""
    # Check for duplicate name
    existing = await session.exec(
        select(Model).where(Model.name == model_in.name)
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model with name '{model_in.name}' already exists",
        )

    # Create MLflow experiment
    experiment_id = None
    try:
        experiment_id = mlflow_service.create_experiment(
            name=f"mlx-hub/{model_in.name}",
            tags={"base_model": model_in.base_model, "task_type": model_in.task_type},
        )
    except Exception as e:
        logger.warning(f"MLflow unavailable, continuing without experiment: {e}")

    # Create model
    model = Model(**model_in.model_dump(), mlflow_experiment_id=experiment_id)
    session.add(model)
    await session.commit()
    await session.refresh(model)

    return ModelResponse(
        **model.model_dump(),
        version_count=0,
    )
```

#### Subtask 3.4: Handle MLflow unavailability

**Description:** Implement graceful degradation when MLflow is unavailable.

**Update the API to handle MLflow failures:**
```python
# In models.py, add error handling
from fastapi import BackgroundTasks

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ModelResponse)
async def create_model(
    model_in: ModelCreate,
    session: SessionDep,
    mlflow_service: Annotated[MLflowService, Depends(get_mlflow_service)],
    background_tasks: BackgroundTasks,
) -> ModelResponse:
    """Register a new model in the hub."""
    # ... existing validation ...

    # Check MLflow availability
    mlflow_available = mlflow_service.is_available()
    experiment_id = None

    if mlflow_available:
        try:
            experiment_id = mlflow_service.create_experiment(
                name=f"mlx-hub/{model_in.name}",
                tags={"base_model": model_in.base_model},
            )
        except Exception as e:
            logger.warning(f"MLflow experiment creation failed: {e}")
    else:
        logger.warning("MLflow unavailable, model created without experiment")

    # Create model regardless of MLflow status
    model = Model(**model_in.model_dump(), mlflow_experiment_id=experiment_id)
    session.add(model)
    await session.commit()
    await session.refresh(model)

    # If MLflow was unavailable, schedule retry
    if not mlflow_available:
        background_tasks.add_task(retry_mlflow_experiment, model.id, model_in.name)

    return ModelResponse(**model.model_dump(), version_count=0)


async def retry_mlflow_experiment(model_id: UUID, name: str):
    """Background task to retry MLflow experiment creation."""
    # Implementation with exponential backoff
    pass
```

#### Subtask 3.5: Write integration tests

**Description:** Test the complete model registration flow.

**Files to Create:**
```python
# backend/tests/test_models_api.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from mlx_hub.db.enums import TaskType


class TestModelsAPI:
    """Integration tests for /models endpoints."""

    @pytest.mark.asyncio
    async def test_create_model_success(self, async_client: AsyncClient):
        """POST /models should create a new model."""
        response = await async_client.post(
            "/models",
            json={
                "name": "test-llama",
                "task_type": "text-generation",
                "description": "Test model for unit tests",
                "base_model": "meta-llama/Llama-3.2-1B",
                "tags": {"test": True},
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-llama"
        assert data["task_type"] == "text-generation"
        assert data["base_model"] == "meta-llama/Llama-3.2-1B"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_model_duplicate_name(self, async_client: AsyncClient):
        """POST /models should reject duplicate names."""
        # Create first model
        await async_client.post(
            "/models",
            json={
                "name": "duplicate-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )

        # Try to create duplicate
        response = await async_client.post(
            "/models",
            json={
                "name": "duplicate-test",
                "base_model": "meta-llama/Llama-3.2-3B",
            },
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_models_pagination(self, async_client: AsyncClient):
        """GET /models should return paginated results."""
        # Create multiple models
        for i in range(25):
            await async_client.post(
                "/models",
                json={
                    "name": f"pagination-test-{i}",
                    "base_model": "meta-llama/Llama-3.2-1B",
                },
            )

        # Get first page
        response = await async_client.get("/models?page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["total"] >= 25
        assert data["page"] == 1
        assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_get_model_by_id(self, async_client: AsyncClient):
        """GET /models/{id} should return specific model."""
        # Create model
        create_response = await async_client.post(
            "/models",
            json={
                "name": "get-by-id-test",
                "base_model": "meta-llama/Llama-3.2-1B",
            },
        )
        model_id = create_response.json()["id"]

        # Get by ID
        response = await async_client.get(f"/models/{model_id}")
        assert response.status_code == 200
        assert response.json()["id"] == model_id

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, async_client: AsyncClient):
        """GET /models/{id} should return 404 for non-existent model."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await async_client.get(f"/models/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_model_mlflow_unavailable(
        self, async_client: AsyncClient
    ):
        """POST /models should succeed even if MLflow is unavailable."""
        with patch("mlx_hub.api.models.get_mlflow_service") as mock:
            mock_service = AsyncMock()
            mock_service.is_available.return_value = False
            mock.return_value = mock_service

            response = await async_client.post(
                "/models",
                json={
                    "name": "mlflow-down-test",
                    "base_model": "meta-llama/Llama-3.2-1B",
                },
            )

            assert response.status_code == 201
            data = response.json()
            assert data["mlflow_experiment_id"] is None
```

**Acceptance Criteria:**
- [ ] POST /models returns 201 with model JSON
- [ ] Model exists in both database and MLflow (when available)
- [ ] GET /models returns paginated list
- [ ] GET /models/{id} returns specific model
- [ ] 409 returned for duplicate model names
- [ ] Graceful degradation when MLflow unavailable
- [ ] All integration tests pass

---

## 6. Phase 2: Data & Orchestration (Tasks 4-5)

### Task 4: Dataset Registry API

**Objective:** Implement dataset registration with checksum validation for reproducibility tracking.

**Dependencies:** Task 2

**Estimated Effort:** 2-3 hours

#### Subtask 4.1: Implement dataset router

**Files to Create:**
```python
# backend/src/mlx_hub/api/datasets.py
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional
from uuid import UUID
import hashlib

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from mlx_hub.config import get_settings
from mlx_hub.db.models import Dataset
from mlx_hub.db.session import SessionDep

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetCreate(SQLModel):
    """Request schema for creating a dataset."""
    name: str
    path: str
    schema_info: dict = {}


class DatasetResponse(SQLModel):
    """Response schema for a dataset."""
    id: UUID
    name: str
    path: str
    checksum: str
    schema_info: dict
    created_at: datetime


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def validate_dataset_path(path: str) -> Path:
    """Validate dataset path is within allowed directories."""
    settings = get_settings()

    # Resolve to absolute path
    dataset_path = Path(path).resolve()
    allowed_base = settings.storage_datasets_path.resolve()

    # Check path is within allowed directory
    try:
        dataset_path.relative_to(allowed_base)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset path must be within {allowed_base}",
        )

    # Check file exists
    if not dataset_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dataset file not found: {path}",
        )

    return dataset_path


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DatasetResponse)
async def create_dataset(
    dataset_in: DatasetCreate,
    session: SessionDep,
) -> DatasetResponse:
    """Register a new dataset."""
    # Validate path
    file_path = validate_dataset_path(dataset_in.path)

    # Check for duplicate name
    existing = await session.exec(
        select(Dataset).where(Dataset.name == dataset_in.name)
    )
    if existing.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset with name '{dataset_in.name}' already exists",
        )

    # Calculate checksum
    checksum = calculate_checksum(file_path)

    # Check for duplicate checksum (same file, different name)
    existing_checksum = await session.exec(
        select(Dataset).where(Dataset.checksum == checksum)
    )
    duplicate = existing_checksum.first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dataset with same content already exists: '{duplicate.name}'",
        )

    # Create dataset
    dataset = Dataset(
        name=dataset_in.name,
        path=str(file_path),
        checksum=checksum,
        schema_info=dataset_in.schema_info,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)

    return DatasetResponse(**dataset.model_dump())


@router.get("", response_model=list[DatasetResponse])
async def list_datasets(
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DatasetResponse]:
    """List all registered datasets."""
    query = select(Dataset).offset((page - 1) * page_size).limit(page_size)
    result = await session.exec(query)
    return [DatasetResponse(**d.model_dump()) for d in result.all()]


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: UUID,
    session: SessionDep,
) -> DatasetResponse:
    """Get a specific dataset by ID."""
    dataset = await session.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found",
        )
    return DatasetResponse(**dataset.model_dump())
```

#### Subtask 4.2-4.4: See datasets.py above (integrated)

**Acceptance Criteria:**
- [ ] Dataset registration calculates and stores SHA256 checksum
- [ ] Path traversal attacks prevented (paths outside storage rejected)
- [ ] Duplicate datasets detected by checksum
- [ ] All dataset tests pass

---

### Task 5: Training Job Orchestration

**Objective:** Implement job queue with FIFO ordering, sequential execution, and status transitions.

**Dependencies:** Tasks 3, 4

**Estimated Effort:** 5-6 hours

#### Subtask 5.1: Implement training jobs router

```python
# backend/src/mlx_hub/api/training.py
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlmodel import select

from mlx_hub.db.models import Dataset, Model, TrainingJob
from mlx_hub.db.session import SessionDep
from mlx_hub.db.enums import JobStatus

router = APIRouter(prefix="/training", tags=["training"])


class TrainingJobCreate(SQLModel):
    """Request schema for creating a training job."""
    model_id: UUID
    dataset_id: UUID
    config: dict = {
        "lora_rank": 16,
        "lora_alpha": 32,
        "learning_rate": 5e-5,
        "epochs": 3,
        "batch_size": 4,
        "seed": 42,
    }


class TrainingJobResponse(SQLModel):
    """Response schema for a training job."""
    id: UUID
    model_id: UUID
    dataset_id: UUID
    status: JobStatus
    config: dict
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_training_job(
    job_in: TrainingJobCreate,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> TrainingJobResponse:
    """Submit a new training job."""
    # Validate model exists
    model = await session.get(Model, job_in.model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {job_in.model_id} not found",
        )

    # Validate dataset exists
    dataset = await session.get(Dataset, job_in.dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {job_in.dataset_id} not found",
        )

    # Create job
    job = TrainingJob(
        model_id=job_in.model_id,
        dataset_id=job_in.dataset_id,
        status=JobStatus.QUEUED,
        config=job_in.config,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Trigger worker to check queue
    background_tasks.add_task(trigger_worker)

    return TrainingJobResponse(**job.model_dump())


@router.get("/jobs", response_model=list[TrainingJobResponse])
async def list_training_jobs(
    session: SessionDep,
    status: Optional[JobStatus] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[TrainingJobResponse]:
    """List training jobs with optional status filter."""
    query = select(TrainingJob)
    if status:
        query = query.where(TrainingJob.status == status)
    query = query.order_by(TrainingJob.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await session.exec(query)
    return [TrainingJobResponse(**j.model_dump()) for j in result.all()]


@router.get("/jobs/{job_id}", response_model=TrainingJobResponse)
async def get_training_job(
    job_id: UUID,
    session: SessionDep,
) -> TrainingJobResponse:
    """Get a specific training job by ID."""
    job = await session.get(TrainingJob, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training job {job_id} not found",
        )
    return TrainingJobResponse(**job.model_dump())
```

#### Subtask 5.2-5.6: Worker implementation

```python
# backend/src/mlx_hub/training/worker.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from mlx_hub.db.models import TrainingJob, Model, Dataset
from mlx_hub.db.enums import JobStatus
from mlx_hub.db.session import get_session_factory
from mlx_hub.config import get_settings
from mlx_hub.training.runner import TrainingRunner

logger = logging.getLogger(__name__)

# Worker state
_worker_running = False
_worker_task: Optional[asyncio.Task] = None


async def trigger_worker():
    """Trigger the worker to check the queue."""
    global _worker_running, _worker_task

    if _worker_running:
        return  # Already running

    _worker_running = True
    _worker_task = asyncio.create_task(run_worker())


async def run_worker():
    """Main worker loop - processes jobs from queue."""
    global _worker_running
    settings = get_settings()
    session_factory = get_session_factory(settings)

    try:
        while True:
            async with session_factory() as session:
                # Check for running job (single active job constraint)
                running = await session.exec(
                    select(TrainingJob).where(
                        TrainingJob.status == JobStatus.RUNNING
                    )
                )
                if running.first():
                    await asyncio.sleep(5)
                    continue

                # Get next queued job (FIFO)
                result = await session.exec(
                    select(TrainingJob)
                    .where(TrainingJob.status == JobStatus.QUEUED)
                    .order_by(TrainingJob.created_at)
                    .limit(1)
                )
                job = result.first()

                if not job:
                    # No jobs in queue, stop worker
                    break

                # Check memory before starting
                if not check_memory_available():
                    logger.warning("Insufficient memory, waiting...")
                    await asyncio.sleep(30)
                    continue

                # Process job
                await process_job(session, job)

    finally:
        _worker_running = False


async def process_job(session: AsyncSession, job: TrainingJob):
    """Process a single training job."""
    logger.info(f"Starting job {job.id}")

    # Update status to running
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    job.heartbeat_at = datetime.utcnow()
    session.add(job)
    await session.commit()

    try:
        # Load model and dataset info
        model = await session.get(Model, job.model_id)
        dataset = await session.get(Dataset, job.dataset_id)

        # Run training
        runner = TrainingRunner(
            model=model,
            dataset=dataset,
            config=job.config,
        )

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(
            update_heartbeat(session, job.id)
        )

        try:
            result = await runner.run()
        finally:
            heartbeat_task.cancel()

        # Update job on success
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()

        logger.info(f"Job {job.id} completed successfully")

    except Exception as e:
        logger.error(f"Job {job.id} failed: {e}")
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.completed_at = datetime.utcnow()

    finally:
        session.add(job)
        await session.commit()


async def update_heartbeat(session: AsyncSession, job_id: UUID):
    """Update job heartbeat periodically."""
    while True:
        try:
            await asyncio.sleep(30)
            job = await session.get(TrainingJob, job_id)
            if job and job.status == JobStatus.RUNNING:
                job.heartbeat_at = datetime.utcnow()
                session.add(job)
                await session.commit()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Heartbeat update failed: {e}")


def check_memory_available() -> bool:
    """Check if enough memory is available for training."""
    import psutil

    settings = get_settings()
    available_gb = psutil.virtual_memory().available / (1024 ** 3)
    required_gb = settings.mlx_memory_limit_gb

    return available_gb >= required_gb


async def cleanup_stale_jobs():
    """Mark stale running jobs as failed."""
    settings = get_settings()
    session_factory = get_session_factory(settings)

    async with session_factory() as session:
        stale_threshold = datetime.utcnow() - timedelta(minutes=5)

        result = await session.exec(
            select(TrainingJob).where(
                TrainingJob.status == JobStatus.RUNNING,
                TrainingJob.heartbeat_at < stale_threshold,
            )
        )

        for job in result.all():
            logger.warning(f"Marking stale job {job.id} as failed")
            job.status = JobStatus.FAILED
            job.error_message = "Job timed out (no heartbeat)"
            job.completed_at = datetime.utcnow()
            session.add(job)

        await session.commit()
```

**Acceptance Criteria:**
- [ ] Jobs execute in FIFO order
- [ ] Only one job running at a time
- [ ] Status transitions correctly (queued → running → completed/failed)
- [ ] Heartbeat monitoring detects stale jobs
- [ ] Memory check prevents OOM
- [ ] All orchestration tests pass

---

## 7. Phase 3: ML Core (Tasks 6-7)

### Task 6: MLX Training Runner

**Objective:** Implement the actual MLX training loop with LoRA/QLoRA support.

**Dependencies:** Task 5

**Estimated Effort:** 6-8 hours

#### Complete Implementation

```python
# backend/src/mlx_hub/training/runner.py
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import hashlib
import json

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_flatten
import mlflow

from mlx_hub.db.models import Dataset, Model
from mlx_hub.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Training configuration."""
    lora_rank: int = 16
    lora_alpha: int = 32
    learning_rate: float = 5e-5
    epochs: int = 3
    batch_size: int = 4
    seed: int = 42
    gradient_accumulation_steps: int = 1
    max_seq_length: int = 512
    warmup_steps: int = 100

    @classmethod
    def from_dict(cls, d: dict) -> "TrainingConfig":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class TrainingRunner:
    """MLX training runner with LoRA support."""

    def __init__(
        self,
        model: Model,
        dataset: Dataset,
        config: dict,
    ):
        self.model_info = model
        self.dataset_info = dataset
        self.config = TrainingConfig.from_dict(config)
        self.settings = get_settings()

        # Will be set during training
        self.mlx_model = None
        self.tokenizer = None
        self.optimizer = None

    async def run(self) -> dict:
        """Execute the training loop."""
        logger.info(f"Starting training for model {self.model_info.name}")

        # Set seed for reproducibility
        mx.random.seed(self.config.seed)

        # Load model and tokenizer
        await self._load_model()

        # Load dataset
        train_data = await self._load_dataset()

        # Setup optimizer
        self._setup_optimizer()

        # Start MLflow run
        with mlflow.start_run(
            experiment_id=self.model_info.mlflow_experiment_id,
            run_name=f"train-{datetime.utcnow().isoformat()}",
        ) as run:
            # Log parameters
            mlflow.log_params({
                "lora_rank": self.config.lora_rank,
                "lora_alpha": self.config.lora_alpha,
                "learning_rate": self.config.learning_rate,
                "epochs": self.config.epochs,
                "batch_size": self.config.batch_size,
                "seed": self.config.seed,
                "dataset_checksum": self.dataset_info.checksum,
            })

            # Training loop
            total_loss = 0.0
            step = 0

            for epoch in range(self.config.epochs):
                epoch_loss = 0.0

                for batch in self._batch_iterator(train_data):
                    loss, grads = self._train_step(batch)

                    # Check for NaN/Inf
                    if self._check_nan_inf(loss):
                        raise ValueError(f"NaN/Inf loss detected at step {step}")

                    # Update optimizer
                    self.optimizer.update(self.mlx_model, grads)
                    mx.eval(self.mlx_model.parameters(), self.optimizer.state)

                    epoch_loss += loss.item()
                    total_loss += loss.item()
                    step += 1

                    # Log metrics
                    if step % 10 == 0:
                        mlflow.log_metrics({
                            "loss": loss.item(),
                            "epoch": epoch,
                            "step": step,
                        }, step=step)

                avg_epoch_loss = epoch_loss / max(1, len(train_data) // self.config.batch_size)
                logger.info(f"Epoch {epoch + 1}/{self.config.epochs}, Loss: {avg_epoch_loss:.4f}")

            # Save adapter
            artifact_path = await self._save_adapter()

            # Log artifact to MLflow
            mlflow.log_artifact(str(artifact_path))

            return {
                "run_id": run.info.run_id,
                "artifact_path": str(artifact_path),
                "final_loss": total_loss / step,
                "total_steps": step,
            }

    async def _load_model(self):
        """Load the base model with LoRA adapters."""
        from mlx_lm import load

        logger.info(f"Loading base model: {self.model_info.base_model}")

        self.mlx_model, self.tokenizer = load(
            self.model_info.base_model,
            tokenizer_config={"trust_remote_code": True},
        )

        # Apply LoRA
        self._apply_lora()

    def _apply_lora(self):
        """Apply LoRA adapters to the model."""
        # LoRA implementation using mlx_lm patterns
        # This freezes base weights and adds trainable adapters
        from mlx_lm.tuner.lora import LoRALinear

        # Get layers to adapt (typically attention layers)
        num_layers = len(self.mlx_model.model.layers)
        target_layers = min(self.config.lora_rank, num_layers)

        for i in range(num_layers - target_layers, num_layers):
            layer = self.mlx_model.model.layers[i]
            # Replace attention projections with LoRA versions
            # Implementation details depend on model architecture
            pass

        # Freeze non-LoRA parameters
        self.mlx_model.freeze()

        # Unfreeze LoRA parameters
        for name, param in tree_flatten(self.mlx_model.parameters()):
            if "lora" in name.lower():
                param.requires_grad = True

    async def _load_dataset(self) -> list[dict]:
        """Load and preprocess the training dataset."""
        dataset_path = Path(self.dataset_info.path)

        data = []
        with open(dataset_path, "r") as f:
            for line in f:
                item = json.loads(line)
                # Expect chat format: {"messages": [{"role": "...", "content": "..."}]}
                if "messages" in item:
                    data.append(item)

        logger.info(f"Loaded {len(data)} training examples")
        return data

    def _setup_optimizer(self):
        """Setup the optimizer."""
        self.optimizer = optim.AdamW(
            learning_rate=self.config.learning_rate,
            weight_decay=0.01,
        )

    def _batch_iterator(self, data: list[dict]):
        """Iterate over data in batches."""
        for i in range(0, len(data), self.config.batch_size):
            batch = data[i:i + self.config.batch_size]
            yield self._prepare_batch(batch)

    def _prepare_batch(self, batch: list[dict]) -> dict:
        """Prepare a batch for training."""
        # Tokenize and pad
        texts = []
        for item in batch:
            # Convert chat format to training text
            text = self._format_chat(item["messages"])
            texts.append(text)

        # Tokenize
        encoded = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=self.config.max_seq_length,
            return_tensors="np",
        )

        return {
            "input_ids": mx.array(encoded["input_ids"]),
            "attention_mask": mx.array(encoded["attention_mask"]),
        }

    def _format_chat(self, messages: list[dict]) -> str:
        """Format chat messages for training."""
        # Use tokenizer's chat template if available
        if hasattr(self.tokenizer, "apply_chat_template"):
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=False,
            )

        # Fallback formatting
        text = ""
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            text += f"<|{role}|>\n{content}\n"
        return text

    def _train_step(self, batch: dict) -> tuple[mx.array, dict]:
        """Execute a single training step."""
        def loss_fn(model):
            logits = model(batch["input_ids"])
            # Shift for causal LM loss
            shift_logits = logits[:, :-1, :]
            shift_labels = batch["input_ids"][:, 1:]

            loss = nn.losses.cross_entropy(
                shift_logits.reshape(-1, shift_logits.shape[-1]),
                shift_labels.reshape(-1),
                reduction="mean",
            )
            return loss

        loss_and_grad_fn = nn.value_and_grad(self.mlx_model, loss_fn)
        loss, grads = loss_and_grad_fn(self.mlx_model)

        return loss, grads

    def _check_nan_inf(self, loss: mx.array) -> bool:
        """Check if loss contains NaN or Inf."""
        loss_val = loss.item()
        return loss_val != loss_val or abs(loss_val) == float("inf")

    async def _save_adapter(self) -> Path:
        """Save the LoRA adapter weights."""
        # Create versioned directory
        version = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        adapter_dir = (
            self.settings.storage_models_path
            / self.model_info.name
            / "versions"
            / version
        )
        adapter_dir.mkdir(parents=True, exist_ok=True)

        adapter_path = adapter_dir / "adapter.safetensors"

        # Extract LoRA weights
        lora_weights = {}
        for name, param in tree_flatten(self.mlx_model.parameters()):
            if "lora" in name.lower():
                lora_weights[name] = param

        # Save with atomic write (temp file + rename)
        temp_path = adapter_path.with_suffix(".tmp")
        mx.save_safetensors(str(temp_path), lora_weights)
        temp_path.rename(adapter_path)

        # Calculate and save checksum
        checksum = self._calculate_checksum(adapter_path)
        checksum_path = adapter_dir / "checksum.sha256"
        checksum_path.write_text(checksum)

        # Save config
        config_path = adapter_dir / "config.json"
        config_path.write_text(json.dumps({
            "lora_rank": self.config.lora_rank,
            "lora_alpha": self.config.lora_alpha,
            "base_model": self.model_info.base_model,
            "dataset_checksum": self.dataset_info.checksum,
            "seed": self.config.seed,
        }, indent=2))

        logger.info(f"Saved adapter to {adapter_path}")
        return adapter_path

    def _calculate_checksum(self, path: Path) -> str:
        """Calculate SHA256 checksum of a file."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
```

**Acceptance Criteria:**
- [ ] Training completes on test model
- [ ] Loss decreases over epochs
- [ ] Adapter .safetensors file generated with valid structure
- [ ] Checksum matches file contents
- [ ] MLflow run logged with all metrics and params
- [ ] NaN/Inf detection stops training early
- [ ] All training tests pass

---

### Task 7: Inference Engine

**Objective:** Implement model loading, caching, and inference with streaming support.

**Dependencies:** Task 6

**Estimated Effort:** 6-8 hours

*(Full implementation similar to Task 6 - see tasks.json for details)*

**Key Components:**
- `InferenceEngine` class with `load_model`, `unload_model`, `generate`
- LRU cache for loaded models with memory limit
- SSE streaming using `sse-starlette`
- Prometheus metrics for TTFT, tokens/sec

**Acceptance Criteria:**
- [ ] POST /inference returns generated text
- [ ] SSE streaming works with real-time token delivery
- [ ] TTFT < 100ms on 7B 4-bit model
- [ ] LRU cache evicts correctly under memory pressure
- [ ] Metrics exposed for Prometheus

---

## 8. Phase 4: Operations (Tasks 8-9)

### Task 8: OpenTelemetry and Prometheus Integration

**Dependencies:** Tasks 3, 7

**Key Files:**
- `backend/src/mlx_hub/observability/metrics.py` - Prometheus metrics
- `backend/src/mlx_hub/observability/tracing.py` - OTel setup

**Acceptance Criteria:**
- [ ] /metrics returns valid Prometheus format
- [ ] Traces generated for all API requests
- [ ] Request IDs correlate logs and traces
- [ ] RED metrics exposed

---

### Task 9: Docker Compose Infrastructure

**Dependencies:** Task 8

**Key Files:**
- `docker-compose.yml`
- `docker/prometheus/prometheus.yml`
- `docker/grafana/dashboards/mlx-hub.json`
- `.env.example`

**Acceptance Criteria:**
- [ ] `docker compose up -d` starts all services
- [ ] Postgres accessible
- [ ] MLflow UI accessible at localhost:5001
- [ ] Prometheus scrapes backend metrics
- [ ] Grafana dashboards show data

---

## 9. Phase 5: Frontend (Tasks 10-12)

### Task 10: Frontend Dashboard - Project Setup

**Dependencies:** Task 3

**Key Steps:**
1. Initialize Next.js 15 with App Router
2. Configure shadcn/ui
3. Set up TanStack Query
4. Create layout and navigation

---

### Task 11: Frontend Dashboard - Core Pages

**Dependencies:** Task 10

**Key Pages:**
- Models list and detail
- Training jobs with status
- Metrics dashboard with charts

---

### Task 12: End-to-End Testing and Documentation

**Dependencies:** Tasks 9, 11

**Deliverables:**
- Playwright E2E tests
- OpenAPI documentation
- Deployment README

---

## 10. Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| End-to-end flow | Works | register → train → version → serve → monitor |
| Reproducibility | 100% | Same inputs produce same outputs |
| Inference TTFT | < 100ms | 7B 4-bit model benchmark |
| Stability | 24h | Sequential training without OOM |
| Test Coverage | > 80% | pytest-cov report |
| Documentation | Complete | All endpoints documented |

---

## 11. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| MLX API changes | Medium | High | Pin version, isolate adapter layer |
| Memory pressure during training | High | High | Enforce 36GB limit, memory checks |
| Thermal throttling | Medium | Medium | Cooldown between epochs, monitoring |
| MLflow unavailability | Low | Medium | Graceful degradation, retry logic |
| Artifact corruption | Low | High | Atomic writes, checksums |
| Database migration drift | Medium | Medium | Always run migrations in CI |

---

## 12. Audit Checklist

### Pre-Implementation Audit

- [x] All dependencies are current (validated via web search)
- [x] Architecture supports all success criteria
- [x] No circular dependencies in task graph
- [x] TDD approach documented for each task
- [x] Error handling strategy defined
- [x] Security considerations addressed (localhost binding, path validation)
- [x] Memory management strategy documented

### Per-Task Audit

For each task, verify:
- [ ] Tests written before implementation (TDD)
- [ ] All subtasks have clear deliverables
- [ ] Acceptance criteria are measurable
- [ ] Rollback strategy exists
- [ ] No breaking changes to existing functionality

### Post-Implementation Audit

- [ ] All tests pass
- [ ] Linting passes (ruff)
- [ ] Type checking passes (mypy)
- [ ] Documentation complete
- [ ] Performance benchmarks met
- [ ] Security scan clean

---

## 13. References

### Official Documentation
- [MLX Documentation](https://ml-explore.github.io/mlx/build/html/)
- [MLX-LM GitHub](https://github.com/ml-explore/mlx-lm)
- [MLflow 3.x Docs](https://mlflow.org/docs/latest/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [SQLModel Docs](https://sqlmodel.tiangolo.com/)
- [Next.js 15 Docs](https://nextjs.org/docs)

### Best Practices Sources
- [FastAPI Production Best Practices](https://render.com/articles/fastapi-production-deployment-best-practices)
- [SQLModel with Alembic](https://testdriven.io/blog/fastapi-sqlmodel/)
- [MLX LoRA Fine-tuning](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
- [OpenTelemetry FastAPI](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html)
- [TanStack Query with Next.js](https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr)

### Research Conducted
- UV workspace/monorepo patterns (2025)
- FastAPI error handling middleware (2025)
- Async SQLModel migrations (2025)
- MLX LoRA training configuration (2025)
- FastAPI BackgroundTasks vs task queues (2025)
- pytest-asyncio testing patterns (2025)
- Docker Compose with Postgres/MLflow (2025)

---

**Document Status:** Complete - Awaiting Approval

**Next Action:** Upon approval, begin Task 1: Project Scaffolding and Environment Setup

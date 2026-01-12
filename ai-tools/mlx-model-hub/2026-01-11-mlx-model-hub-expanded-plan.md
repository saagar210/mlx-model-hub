# MLX Model Hub Expanded Implementation Plan (2026)

## 0. Document Intent
This is a fully fleshed out, local-first plan to build an MLX Model Hub optimized for Apple Silicon. It includes: methodology updates (2024-2026), local machine audit and optimization guidance, TDD flow per task, success criteria, risks, and concrete implementation steps.

**Scope:** local-first single-node deployment on macOS (M4 Pro) with Postgres in Docker, MLX for training/inference, FastAPI backend, Next.js admin UI.

**Out of scope (initial phase):** multi-node orchestration, cloud deployment, enterprise auth, model marketplace.

---

## 1. Goals and Success Criteria

### Goals
- Train, version, and serve MLX models locally via clean API + admin UI.
- Maintain reproducibility and lineage (datasets, params, artifacts, metrics).
- Provide observability: latency, memory pressure, job health, and model quality trends.

### Success Criteria
1. **Lifecycle flow works end-to-end:** register -> train -> version -> serve -> monitor.
2. **Reproducibility:** each model version ties to git commit + dataset hash + params.
3. **Performance:** inference TTFT < 100ms for a 7B 4-bit model.
4. **Operational stability:** sequential training jobs for 24h without memory thrash.
5. **Visibility:** Prometheus/Grafana show key metrics (CPU/GPU/memory, job queue).

---

## 2. Local Machine Audit and Optimization Plan

### Machine Summary
- CPU: Apple M4 Pro (14 cores: 10P, 4E)
- GPU: 20-core Apple GPU (Metal 4)
- Memory: 48GB Unified Memory
- OS: macOS 26.2 (Darwin)
- Storage: local NVMe, 256Gi available
- Tooling available: Python 3.12.12, uv 0.9.24, Node 22.21.1, pnpm 10.28.0, Docker 29.1.3

### Optimization Guidance
- **Unified Memory Budget:** Reserve 12GB headroom; enforce a 36GB MLX limit.
- **MLX Compilation:** Use `@mx.compile` for hot paths (forward + loss + update).
- **Quantization:** Prefer 4-bit or 8-bit weights for models > 7B parameters.
- **Streaming I/O:** Overlap dataset loading with compute via MLX streams.
- **Disk Layout:** Separate `storage/active` and `storage/archive` to reduce I/O contention.

---

## 3. Methodology Updates (2024-2026)

These practices are integrated into the plan:

1. **MLflow 3.x registry and tracking** for model versioning and lineage.
2. **Artifact tiering** (local filesystem now, MinIO/S3 later) for scalability.
3. **OpenTelemetry + Prometheus** for unified traces + metrics.
4. **Reproducibility pillars:** code commit, environment lock, dataset hash, params, seeds.
5. **Local-first MLOps:** avoid premature cloud infrastructure; optimize for iteration speed.

---

## 4. System Architecture

### Backend (FastAPI)
- REST API for model registry, training jobs, inference, datasets.
- BackgroundTasks or lightweight job runner for training.
- SQLModel + Alembic for relational metadata.

### MLX Training Runner
- MLX-native training loop for fine-tuning (LoRA/QLoRA).
- Artifact output in `.safetensors` with checksum validation.

### Inference Engine
- MLX inference with streamed token generation (SSE).
- KV cache control for long prompts.

### Storage
- Metadata: Postgres
- Artifacts: `storage/active` -> `storage/archive`
- Optional future: MinIO

### Frontend (Next.js 15)
- Dashboard for models, datasets, training jobs, and metrics.

---

## 5. Directory Layout (Target)
```
mlx-model-hub/
  backend/
    src/mlx_hub/
      api/
      config.py
      db/
      inference/
      training/
    tests/
  frontend/
    app/
    components/
    tests/
  storage/
    active/
    archive/
  docker-compose.yml
  scripts/
  docs/
```

---

## 6. Task Plan (TDD Flow Maintained)

Each task includes: failing test, minimal implementation, verification, and acceptance criteria.

### Task 1: Project Scaffolding and Environment
**Goal:** Base structure with dependencies and config.

**TDD Flow:**
1. Failing test in `backend/tests/test_config.py` verifying `settings` values and directory existence.
2. Run test, expect fail.
3. Implement `config.py` and create required directories.
4. Re-run test, expect pass.

**Implementation Details:**
- Use `uv` for Python dependencies.
- Pin versions for MLX, MLflow, SQLModel, FastAPI.
- Create `storage/active` and `storage/archive`.

**Acceptance Criteria:**
- `uv run pytest backend/tests/test_config.py -v` passes.

---

### Task 2: Database Schema and Migrations
**Goal:** SQLModel schema for Model, ModelVersion, Dataset, TrainingJob.

**TDD Flow:**
1. Failing test: create `ModelVersion` with missing `Model` -> should fail (FK).
2. Implement schema and migrations.
3. Pass tests.

**Implementation Details:**
- `Model`: name, task_type, created_at
- `ModelVersion`: model_id, version, status, metrics, artifact_path
- `Dataset`: name, path, checksum, schema
- `TrainingJob`: model_id, dataset_id, status, started_at, finished_at

**Acceptance Criteria:**
- Migration runs clean; schema enforced; test passes.

---

### Task 3: Model Registry API (MLflow Integration)
**Goal:** Registry endpoints and MLflow sync.

**TDD Flow:**
1. Failing test: POST /models should create DB entry and MLflow experiment.
2. Implement endpoints + MLflow client integration.
3. Pass tests.

**Implementation Details:**
- `POST /models`: register model metadata
- `GET /models`: list models
- `GET /models/{id}/history`: MLflow run history

**Acceptance Criteria:**
- Model appears in DB and MLflow UI after POST.

---

### Task 4: Training Job Orchestration
**Goal:** Queue and run MLX training jobs sequentially.

**TDD Flow:**
1. Failing test: create job -> status should be queued.
2. Implement queue + BackgroundTasks.
3. Pass tests.

**Implementation Details:**
- `POST /training/jobs` creates job
- Scheduler ensures one job at a time to avoid OOM
- Status transitions: queued -> running -> completed/failed

**Acceptance Criteria:**
- Submitting multiple jobs results in sequential execution.

---

### Task 5: MLX Training Runner
**Goal:** MLX-based training loop with quantization support.

**TDD Flow:**
1. Failing test: training on dummy dataset should reduce loss.
2. Implement minimal loop.
3. Pass tests.

**Implementation Details:**
- Use `mlx.nn`, `mlx.optimizers`
- Support LoRA or QLoRA
- Save `.safetensors` + checksum

**Acceptance Criteria:**
- Adapter weights generated and loss decreases on dummy data.

---

### Task 6: Inference Engine
**Goal:** Serve MLX inference via API.

**TDD Flow:**
1. Failing test: POST /inference returns output.
2. Implement MLX inference engine.
3. Pass tests.

**Implementation Details:**
- Streaming SSE endpoint
- KV cache handling
- Latency targets via benchmarks

**Acceptance Criteria:**
- Inference responds with output and TTFT < 100ms for small models.

---

### Task 7: Frontend Dashboard
**Goal:** Admin UI for models, jobs, and metrics.

**TDD Flow:**
1. Failing test: page renders "MLX Model Hub".
2. Implement minimal Next.js page.
3. Pass tests.

**Implementation Details:**
- Dashboard pages: Models, Training, Inference
- Training charts (loss, accuracy)
- Status updates via polling or SSE

**Acceptance Criteria:**
- UI shows models and jobs; training updates visible.

---

### Task 8: Observability + Docker Compose
**Goal:** Metrics, tracing, and local infra wiring.

**TDD Flow:**
1. Manual verification: `docker compose up` fails with missing config.
2. Implement compose and metrics endpoints.
3. Verify config.

**Implementation Details:**
- Prometheus + Grafana for metrics
- OpenTelemetry tracing in FastAPI
- MLflow in Docker

**Acceptance Criteria:**
- Prometheus scrapes metrics; Grafana dashboards show data.

---

## 7. Verification Commands

```bash
# Run backend tests
uv run pytest backend/tests -v

# Run frontend tests
pnpm test

# Validate Docker Compose
docker compose config
```

---

## 8. Risks and Mitigation

- **Memory Pressure:** enforce model load limits and LRU eviction.
- **Thermal Throttling:** schedule training cooldowns, monitor temperature.
- **MLX API Changes:** pin MLX version and isolate adapter layer.
- **Artifact Corruption:** use checksum verification and atomic writes.

---

## 9. Next Step Recommendation
Proceed with Task 1 implementation once you confirm this plan is acceptable. The plan is structured for strict TDD compliance.

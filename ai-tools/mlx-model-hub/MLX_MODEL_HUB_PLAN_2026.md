# MLX Model Hub: Full Implementation Plan (2026)

## 0. Purpose
Build a local-first MLX Model Hub optimized for Apple Silicon that provides model registry, training orchestration, inference serving, and observability with a clean API and an admin UI. The system must be reliable on a single MacBook Pro (M4 Pro, 48GB), reproducible, and production-grade in structure even when running locally.

## 1. Constraints and Goals
### Goals
- Local-first model lifecycle management: register, train, evaluate, serve.
- Tight integration with MLX for Apple Silicon performance.
- Reproducible experiments and artifacts with clear lineage.
- Observability for latency, memory usage, and training throughput.
- Admin UI for visibility and operational control.

### Non-Goals
- Multi-tenant cloud hosting or global HA.
- Massive distributed training across many hosts (design for later expansion).
- Automated data labeling pipelines.

### Success Criteria
- End-to-end flow works: register model -> run training -> view metrics -> serve inference.
- Inference p50 latency < 100ms for small models locally.
- Training job orchestration is stable under sequential runs.
- Reproducibility: same code+data+seed yields stable metrics within tolerance.

## 2. Local Machine Audit (2026-01-11)
### Findings
- CPU: Apple M4 Pro, 14 cores (10P/4E)
- GPU: 20-core Apple GPU (Metal 4)
- RAM: 48GB unified memory
- OS: macOS 26.2 (Darwin 25.2.0)
- Storage: NVMe, ~256GB free

### Optimization Strategy
- Use MLX compile and lazy evaluation for kernel fusion.
- Enforce memory budgets and single active training job by default.
- Prefer 4-bit/8-bit weights for larger models.
- Use local filesystem artifacts for low latency; expand to S3/MinIO later if needed.

## 3. Methodology Updates (2024-2026)
These are incorporated into the plan below:
- MLflow 3.x as registry + experiment tracking (local-first).
- OpenTelemetry + Prometheus for tracing and metrics.
- Artifact tiering: metadata in DB, weights on disk, optional S3-compatible store later.
- Structured reproducibility: code commit tags, dataset hashes, env lockfiles.

References:
- MLflow Model Registry: https://mlflow.org/docs/latest/ml/model-registry/
- MLflow Tracking: https://mlflow.org/docs/latest/ml/tracking/
- OpenTelemetry for FastAPI: https://opentelemetry.io/docs/instrumentation/python/
- Prometheus OTLP receiver: https://prometheus.io/docs/prometheus/latest/feature_flags/

## 4. Architecture
### Components
- **Backend**: FastAPI app with API routers for models, jobs, datasets, inference.
- **Registry**: SQLModel + Postgres for metadata. MLflow for experiment tracking.
- **Training**: MLX training runner, job scheduler, artifact writer.
- **Inference**: MLX inference engine with caching and streaming responses.
- **Frontend**: Next.js 15 admin UI for models, jobs, metrics, datasets.
- **Observability**: OTel traces, Prometheus metrics, optional Grafana.

### Data Flow
1. User registers model metadata (API).
2. Training job enqueued -> MLX runner executes -> artifacts written.
3. MLflow run logged; metrics stored for UI.
4. Inference loads model + adapter; serves responses.

## 5. Repository Structure
```
mlx-model-hub/
  backend/
    src/mlx_hub/
      api/
      config.py
      db/
      training/
      inference/
    tests/
    pyproject.toml
  frontend/
    app/
    components/
    package.json
  docker-compose.yml
  scripts/
  storage/
    active/
    archive/
```

## 6. Detailed Execution Plan (TDD)
Each task follows:
1) Write failing test
2) Minimal implementation
3) Refactor for performance or stability
4) Run tests

### Task 1: Scaffold Project and Environment
**Objective**: Set up Python, FastAPI, MLflow, and core configs.

Steps:
- Create `backend/pyproject.toml` with dependencies: fastapi, uvicorn, sqlmodel, pydantic-settings, mlflow, pytest, ruff.
- Add `mlx_hub/config.py` with settings for DB URL, artifact paths, MLflow tracking URI.
- Add `mlx_hub/main.py` with app factory and health route.

Test:
- `backend/tests/test_config.py` checks settings load.

Validation:
- `uv run pytest backend/tests/test_config.py -v` passes.

### Task 2: Database Schema and Migrations
**Objective**: Define Models, ModelVersions, Datasets, TrainingJobs.

Steps:
- Implement SQLModel models with constraints and timestamps.
- Create Alembic migration init.
- Write session helpers for DB access.

Test:
- Ensure creating ModelVersion without Model fails or is blocked.

Validation:
- `alembic upgrade head` works.

### Task 3: Model Registry API with MLflow
**Objective**: CRUD models and sync experiments in MLflow.

Steps:
- API endpoints: POST /models, GET /models, GET /models/{id}.
- When model created, initialize MLflow experiment.
- Store MLflow experiment ID in metadata.

Test:
- After POST /models, verify MLflow experiment exists.

### Task 4: Training Job Orchestration
**Objective**: Queue and execute MLX training jobs sequentially.

Steps:
- Implement TrainingJob model with status transitions.
- Use background tasks or a simple worker loop.
- Enforce single active job to respect memory budget.

Test:
- Submit multiple jobs, ensure sequential execution.

### Task 5: MLX Training Runner
**Objective**: Implement MLX training pipeline with stability checks.

Steps:
- Implement `training/runner.py` with MLX train loop.
- Add `@mx.compile` for performance.
- Implement loss NaN detection and early stop.
- Write artifacts to `storage/active/` then archive.

Test:
- Train a dummy dataset and assert loss decreases.

### Task 6: Inference Engine
**Objective**: Serve inference with streaming option and metrics.

Steps:
- Implement `inference/engine.py` with model load/unload.
- Add POST /inference endpoint, optional SSE streaming.
- Track latency and memory metrics.

Test:
- Benchmark endpoint < 100ms on small model.

### Task 7: Admin UI
**Objective**: Provide visibility into models, runs, jobs.

Steps:
- Add Model List, Job Status, Metric Charts.
- Implement API calls to backend endpoints.
- Add UI for start/cancel training.

Test:
- Playwright tests for basic interaction.

### Task 8: Docker Compose + Observability
**Objective**: Local deployment stack.

Steps:
- Compose services: Postgres, MLflow server, optional Prometheus/Grafana.
- Add scripts/start.sh to run services.
- Document environment variables.

Test:
- `docker compose config` passes.

## 7. Observability Plan
- **Metrics**: latency_ms, throughput_tps, memory_bytes, training_step_time.
- **Tracing**: use OTel middleware for API endpoints.
- **Dashboard**: optional Grafana dashboards for CPU/GPU/memory.

## 8. Security and Safety
- No external network exposure by default.
- Environment variables for secrets (DB password).
- Validate file paths to prevent path traversal.

## 9. Risks and Mitigations
- Memory pressure: enforce job queue single-runner, prefer quantized models.
- Thermal throttling: add cooldown sleep between epochs if needed.
- MLX API changes: pin versions and track changes in lockfile.

## 10. Verification Commands
```
uv run pytest backend/tests -v
uv run python scripts/profile_mlx.py --model 7b --batch 4
curl http://localhost:8000/health
```

## 11. Next Decisions (Optional)
- Choose MLflow vs pure DB registry.
- Decide on MinIO for artifacts if multi-host needed.
- Decide on Redis-based queue if scaling jobs.

---
End of plan.

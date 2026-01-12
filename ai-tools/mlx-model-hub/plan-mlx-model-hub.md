# MLX Model Hub Implementation Plan (Canonical)

## 0. Purpose
Build a local-first MLX Model Hub optimized for Apple Silicon that provides model registry, training orchestration, inference serving, and observability via a clean API and admin UI. The plan is explicit about steps, data contracts, tests, risks, and deployment checklists to avoid surprises.

Scope: local-first single-node deployment on macOS (M4 Pro) with Postgres in Docker, MLX for training/inference, FastAPI backend, Next.js admin UI.

Out of scope (initial phase): multi-node orchestration, cloud deployment, enterprise auth/SSO, model marketplace, automated labeling pipelines.

---

## 1. Goals and Success Criteria

Goals:
- Train, version, and serve MLX models locally via API and admin UI.
- Maintain reproducibility and lineage across datasets, params, artifacts, and metrics.
- Provide observability for latency, memory pressure, job health, and model quality trends.

Success Criteria:
1. End-to-end flow works: register -> train -> version -> serve -> monitor.
2. Reproducibility: each model version ties to git commit, dataset hash, params, and seeds.
3. Performance: inference TTFT < 100ms for a 7B 4-bit model locally.
4. Operational stability: sequential training jobs for 24h without memory thrash.
5. Visibility: metrics dashboard shows CPU/GPU/memory, job queue, latency.

---

## 2. Local Machine Audit and Optimization Plan

Machine Summary:
- CPU: Apple M4 Pro (14 cores: 10P, 4E)
- GPU: 20-core Apple GPU (Metal 4)
- Memory: 48GB Unified Memory
- OS: macOS 26.2 (Darwin)
- Storage: local NVMe, ~256Gi available
- Tooling: Python 3.12.12, uv 0.9.24, Node 22.21.1, pnpm 10.28.0, Docker 29.1.3

Optimization Guidance:
- Unified memory budget: reserve 12GB headroom; enforce a 36GB MLX limit.
- MLX compilation: use @mx.compile for hot paths (forward, loss, update).
- Quantization: prefer 4-bit or 8-bit weights for models > 7B params.
- Streaming I/O: overlap dataset loading with compute via MLX streams.
- Disk layout: separate storage/active and storage/archive to reduce I/O contention.

Operational Guardrails:
- Single active training job by default.
- Explicit memory checks before model load; refuse job if insufficient headroom.
- Cache eviction for inference models (LRU) when memory pressure is detected.
- Cooldown between training epochs if temperature exceeds threshold (tracked via metrics).

---

## 3. Methodology Updates (2024-2026)

Integrated practices:
1. MLflow 3.x registry and tracking for model versioning and lineage.
2. Artifact tiering (local filesystem now, MinIO/S3 later) for scalability.
3. OpenTelemetry + Prometheus for unified traces and metrics.
4. Reproducibility pillars: code commit, environment lock, dataset hash, params, seeds.
5. Local-first MLOps: avoid premature cloud infra; optimize for iteration speed.

References:
- MLflow Model Registry: https://mlflow.org/docs/latest/ml/model-registry/
- MLflow Tracking: https://mlflow.org/docs/latest/ml/tracking/
- MLflow Evaluation: https://mlflow.org/docs/latest/ml/evaluation/
- MLX Distributed: https://ml-explore.github.io/mlx/build/html/usage/distributed.html
- OpenTelemetry FastAPI: https://opentelemetry.io/docs/instrumentation/python/instrumentation/fastapi/
- Prometheus OTLP receiver: https://prometheus.io/docs/prometheus/latest/feature_flags/#otlp-receiver

---

## 4. Architecture

Components:
- Backend: FastAPI app with model, dataset, job, inference endpoints.
- Registry: SQLModel + Postgres for metadata; MLflow for experiment tracking.
- Training: MLX runner, job scheduler, artifact writer.
- Inference: MLX inference engine with streaming support and caching.
- Frontend: Next.js 15 admin UI for models, jobs, metrics.
- Observability: OpenTelemetry traces + Prometheus metrics + optional Grafana.

Data Flow:
1. Register model metadata via API.
2. Training job queued and executed by MLX runner.
3. Metrics/params/artifacts logged to MLflow and storage paths.
4. Inference loads model + adapter; serves response; metrics emitted.

Security Boundaries:
- No external network exposure by default.
- Secrets loaded via environment variables.
- Validation of file paths to prevent traversal.

---

## 5. Repository Layout (Target)
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
    pyproject.toml
  frontend/
    app/
    components/
    tests/
    package.json
  storage/
    active/
    archive/
  docker-compose.yml
  scripts/
  docs/
```

---

## 6. Interfaces and Data Contracts

API Endpoints:
- POST /models
- GET /models
- GET /models/{id}
- GET /models/{id}/history
- POST /datasets
- GET /datasets
- POST /training/jobs
- GET /training/jobs
- GET /training/jobs/{id}
- POST /inference
- POST /inference/stream (SSE)
- GET /health
- GET /metrics

Model Metadata Schema (Example):
- name: str
- task_type: str
- description: str
- base_model: str
- created_at: datetime
- tags: dict

Model Version Schema (Example):
- model_id: int
- version: str
- status: str
- metrics: dict
- artifact_path: str
- created_at: datetime

Dataset Schema (Example):
- name: str
- path: str
- checksum: str (sha256)
- schema: dict

Training Job Payload (Example):
- model_id: int
- dataset_id: int
- lora_rank: int
- learning_rate: float
- epochs: int
- batch_size: int
- seed: int

Inference Request (Example):
- model_id: int
- prompt: str
- max_tokens: int
- temperature: float
- top_p: float

Inference Response (Example):
- text: str
- tokens: int
- latency_ms: float

---

## 7. Dependencies and Tooling

Backend:
- fastapi
- uvicorn
- sqlmodel
- alembic
- pydantic-settings
- mlflow
- opentelemetry-sdk
- prometheus-client
- pytest
- ruff

Frontend:
- next
- react
- shadcn/ui
- @testing-library/react
- playwright

Infrastructure:
- docker-compose
- postgres
- optional: prometheus, grafana, mlflow server

---

## 8. Environment Variables

Backend:
- DATABASE_URL
- MLFLOW_TRACKING_URI
- ARTIFACT_ROOT
- STORAGE_ACTIVE_PATH
- STORAGE_ARCHIVE_PATH
- LOG_LEVEL

Frontend:
- NEXT_PUBLIC_API_BASE_URL

---

## 9. Task Plan (TDD Flow Maintained)

Each task includes: failing test, minimal implementation, verification, acceptance criteria, and failure modes.

### Task 1: Project Scaffolding and Environment
Objective: Base structure with dependencies and config.

Steps:
1. Initialize uv project and lockfile.
2. Create src/mlx_hub/config.py with settings validation.
3. Create storage/active and storage/archive directories.
4. Configure logging defaults.

Tests:
- backend/tests/test_config.py validates settings and path existence.

Validation:
- uv run pytest backend/tests/test_config.py -v
- python -c "import mlx"

Acceptance Criteria:
- Settings load successfully and directories are created.

Failure Modes:
- Missing arm64 wheels -> pin supported versions and verify platform markers.
- Misconfigured env vars -> defaults with warnings.

Rollback:
- Remove created dirs, revert lockfile and config changes.

---

### Task 2: Database Schema and Migrations
Objective: SQLModel schema for Model, ModelVersion, Dataset, TrainingJob.

Steps:
1. Define SQLModel classes and relationships.
2. Initialize Alembic, generate migration.
3. Add indexes on Model.name and ModelVersion.version.

Tests:
- Attempt to create ModelVersion without Model should fail.

Validation:
- alembic upgrade head
- Unit tests pass

Acceptance Criteria:
- Schema enforces FK relationships and defaults.

Failure Modes:
- DB lock under concurrent writes -> serialize queue and add retry.
- Migration drift -> enforce revision history in CI.

Rollback:
- Downgrade migration or reset local DB.

---

### Task 3: Model Registry API (MLflow Integration)
Objective: Registry endpoints and MLflow sync.

Steps:
1. Implement POST /models, GET /models, GET /models/{id}.
2. Create MLflow experiment on model registration.
3. Store experiment_id in DB.

Tests:
- POST /models creates DB row and MLflow experiment.

Validation:
- MLflow UI shows experiment.
- API returns 201 with JSON body.

Acceptance Criteria:
- Model exists in DB and MLflow.

Failure Modes:
- MLflow unavailable -> fallback DB only, return 503.
- Invalid metadata -> Pydantic validation error.

Rollback:
- Remove model row and MLflow experiment.

---

### Task 4: Training Job Orchestration
Objective: Queue and run MLX training jobs sequentially.

Steps:
1. Implement job table with status transitions.
2. Build worker loop or BackgroundTasks scheduler.
3. Enforce single active job with FIFO ordering.

Tests:
- Submitting multiple jobs runs sequentially.

Validation:
- Status transitions: queued -> running -> completed/failed.
- Artifacts moved from storage/active to storage/archive.

Acceptance Criteria:
- Jobs execute sequentially; statuses accurate.

Failure Modes:
- Orphaned running job -> heartbeat check + timeout.
- Queue starvation -> FIFO ordering and retry limits.

Rollback:
- Mark running job failed and reschedule.

---

### Task 5: MLX Training Runner
Objective: MLX-based training loop with quantization support.

Steps:
1. Implement training loop with mlx.nn and mlx.optimizers.
2. Add LoRA/QLoRA adapters.
3. Save .safetensors + checksum.
4. Add NaN/Inf detection and early stop.

Tests:
- Dummy dataset loss decreases over steps.

Validation:
- Adapter weights written with checksum.

Acceptance Criteria:
- Training completes and adapter file generated.

Failure Modes:
- NaN loss -> lower LR, enable gradient clipping.
- Memory fragmentation -> clear caches between jobs.

Rollback:
- Delete partial artifacts and mark job failed.

---

### Task 6: Inference Engine
Objective: Serve MLX inference via API.

Steps:
1. Implement InferenceEngine with model load/unload.
2. Add POST /inference endpoint.
3. Add SSE streaming endpoint.
4. Implement KV cache controls.

Tests:
- POST /inference returns output.

Validation:
- TTFT < 100ms on small model.
- Metrics emitted to /metrics.

Acceptance Criteria:
- API returns output; streaming works.

Failure Modes:
- Adapter mismatch -> validate metadata before load.
- Context overflow -> enforce max tokens.

Rollback:
- Unload model and return 400/500 as appropriate.

---

### Task 7: Frontend Dashboard
Objective: Admin UI for models, jobs, and metrics.

Steps:
1. Scaffold Next.js app in frontend/.
2. Build Models list view.
3. Add Training Jobs view with status.
4. Add Metrics charts.

Tests:
- Playwright test renders dashboard.

Validation:
- UI shows models/jobs and updates status.

Acceptance Criteria:
- UI functional with live updates.

Failure Modes:
- SSE disconnects -> fallback to polling.
- Large logs slow rendering -> virtualize lists.

Rollback:
- Revert UI components if unstable.

---

### Task 8: Observability and Docker Compose
Objective: Metrics, tracing, and local infra wiring.

Steps:
1. Create docker-compose.yml for Postgres, MLflow, Prometheus, Grafana.
2. Configure Prometheus scraping.
3. Add OTel middleware to FastAPI.
4. Provide Grafana dashboards.

Tests:
- docker compose config passes.

Validation:
- Prometheus /targets shows backend up.
- Grafana dashboards display data.

Acceptance Criteria:
- Local stack starts cleanly and provides metrics/traces.

Failure Modes:
- Port conflicts -> use explicit ports.
- OTel misconfig -> fallback to metrics only.

Rollback:
- Disable OTel, run core stack only.

---

## 10. Deployment Checklist (Local)
1. Ensure Docker Desktop running.
2. Configure env vars in .env.
3. Run migrations: alembic upgrade head.
4. Start services: docker compose up -d.
5. Start backend: uv run uvicorn mlx_hub.main:app.
6. Start frontend: pnpm dev.
7. Verify /health and /metrics endpoints.

---

## 11. Verification Commands
```
# Run backend tests
uv run pytest backend/tests -v

# Run frontend tests
pnpm test

# Validate Docker Compose
docker compose config
```

---

## 12. Risks and Mitigation (Summary)
- Memory pressure: enforce model load limits and LRU eviction.
- Thermal throttling: schedule training cooldowns and monitor temperature.
- MLX API changes: pin MLX version and isolate adapter layer.
- Artifact corruption: checksum verification and atomic writes.

---

## 13. Next Step
Proceed with Task 1 implementation once this plan is approved.

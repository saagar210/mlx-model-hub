# MLX MODEL HUB IMPLEMENTATION PLAN

## 1. PROJECT OVERVIEW
The MLX Model Hub is a localized, high-performance MLOps platform designed specifically for Apple Silicon (M4 Pro). It provides a full lifecycle management system for MLX models, including registry, fine-tuning (LoRA/QLoRA), inference serving, and observability.

## 2. LOCAL MACHINE AUDIT FINDINGS
- CPU: Apple M4 Pro (14 cores: 10 performance, 4 efficiency)
- GPU: 20-core GPU
- RAM: 48GB Unified Memory
- OS: macOS 26.2 (Darwin)
- Storage: Local NVMe
- Optimization Strategy:
    - Maximize Unified Memory: Allocate up to 36GB (75%) for large model weights/KV cache.
    - Compute: Utilize MLX's direct Metal integration for GPU acceleration.
    - Efficiency: Use 4-bit and 8-bit quantization to fit 7B-32B parameter models.

## 3. METHODOLOGY UPDATES (2024-2026)
- Model Registry: Upgraded from basic DB to MLflow 3.x for artifact lineage and versioning.
- Experiment Tracking: MLflow Tracking with OpenTelemetry integration for system-level tracing.
- Observability: Prometheus + Grafana stack to monitor M4 Pro GPU/CPU thermals and memory pressure.
- Reproducibility: Lockfiles (uv.lock) and environment snapshots for consistent training runs.
- Distributed Logic: MLX-based data parallelism for future multi-node or multi-GPU support.

## 4. RISKS & MITIGATIONS
- Risk: Memory Pressure / OOM. Mitigation: Implement strict memory budget checks before job execution; use QLoRA.
- Risk: Thermal Throttling. Mitigation: Prometheus monitoring of SoC temperature; cooling-off periods between training batches.
- Risk: MLX API Instability. Mitigation: Version-pinned dependencies and abstraction layers for MLX-LM calls.
- Risk: Artifact Corruption. Mitigation: Atomic writes and checksum validation for model weights.

## 5. TASK BREAKDOWN

### TASK 1: PROJECT SCAFFOLDING & ENVIRONMENT
Set up the core directory structure and dependency management using 'uv' for high-speed Python tooling.

- Substeps:
    1. Initialize 'uv' project and create virtual environment.
    2. Configure pyproject.toml with strict type checking (Pyright/Mypy).
    3. Set up directory structure: /api, /core, /web, /scripts, /tests, /infra.
    4. Configure CI/CD hooks for linting (Ruff).
- Inputs: Dependency list (fastapi, mlx, mlflow, opentelemetry, pytest).
- Outputs: Functional development environment with lockfiles.
- Failure Modes: Architecture mismatch (ensure arm64 binaries).
- Validation: 'uv run pytest' executes with 0 tests found.
- Acceptance Criteria: Environment active, 'import mlx' succeeds, directory structure verified.

### TASK 2: DATABASE SCHEMA & ARTIFACT STORAGE
Define the relational schema for model metadata and the filesystem layout for model weights.

- Substeps:
    1. Define SQLAlchemy models for Models, Versions, Jobs, and Evaluations.
    2. Implement Alembic migrations for schema versioning.
    3. Design local artifact storage tree: /artifacts/{model_id}/{version_tag}/.
    4. Implement ModelDAO (Data Access Object) with TDD.
- Inputs: Schema definitions, local storage path configuration.
- Outputs: SQLite database with initial tables; storage utility classes.
- Failure Modes: DB locking under concurrent job writes; Disk full.
- Validation: Script to insert/retrieve mock model metadata.
- Acceptance Criteria: Schema supports 1:N model-to-version relationships; artifacts mapped to UUIDs.

### TASK 3: MODEL REGISTRY API (MLFLOW 3.X INTEGRATION)
Expose endpoints for model registration, versioning, and metadata retrieval.

- Substeps:
    1. Create FastAPI router for /models and /versions.
    2. Integrate MLflow 3.x Client for background experiment tracking.
    3. Implement TDD for POST /models (registration) and GET /models/{id}.
    4. Add validation for model configuration (config.json).
- Inputs: Model metadata JSON, MLflow server URL.
- Outputs: RESTful API for model lifecycle management.
- Failure Modes: MLflow service unreachable; Invalid metadata format.
- Validation: HTTPie or Curl tests against registration endpoints.
- Acceptance Criteria: Model registered in local DB and MLflow simultaneously.

### TASK 4: TRAINING JOB MANAGEMENT (QUEUE & ORCHESTRATION)
Implement a lightweight job queue to manage MLX training tasks without overlapping memory usage.

- Substeps:
    1. Implement a job queue using Redis or a simple SQLite-backed 'pending' table.
    2. Create JobScheduler to ensure only ONE training job runs at a time (M4 Pro memory limit).
    3. Implement POST /jobs endpoint to submit fine-tuning configs.
    4. Add job cancellation and timeout logic.
- Inputs: Training config (base_model, dataset_path, lora_rank, epochs).
- Outputs: Job management system with state tracking (QUEUED, RUNNING, COMPLETED, FAILED).
- Failure Modes: Race conditions in job selection; Orphaned 'RUNNING' jobs after crash.
- Validation: Submit 5 jobs; verify they execute sequentially.
- Acceptance Criteria: Queue correctly serializes tasks; job status updates in real-time.

### TASK 5: MLX TRAINING RUNNER (HARDWARE-OPTIMIZED)
The core logic for executing LoRA/QLoRA fine-tuning using MLX.

- Substeps:
    1. Implement TrainingRunner using mlx.optimizers and mlx.nn.
    2. Add hardware-aware batch sizing (auto-scale based on available 48GB RAM).
    3. Implement checkpointing and early stopping.
    4. Integrate OpenTelemetry to track iterations-per-second and loss curves.
- Inputs: Model weights, training dataset, hyperparameter set.
- Outputs: Trained adapter weights (.safetensors).
- Failure Modes: NaN loss; GPU memory fragmentation.
- Validation: Unit test for single-step gradient update.
- Acceptance Criteria: Training completes on a sample dataset; adapter file generated.

### TASK 6: INFERENCE API (MLX SERVING)
Expose fine-tuned models for real-time inference using mlx-lm.

- Substeps:
    1. Create InferenceEngine class to load base model + adapters.
    2. Implement POST /completions and POST /chat/completions (OpenAI compatible).
    3. Add streaming support (Server-Sent Events).
    4. Implement KV cache management for long context windows.
- Inputs: Model ID, prompt, sampling parameters (temp, top_p).
- Outputs: Generated text tokens.
- Failure Modes: Context window overflow; Adapter mismatch with base model.
- Validation: Measure time-to-first-token (TTFT) on M4 Pro (Target < 50ms).
- Acceptance Criteria: API returns valid responses; supports streaming.

### TASK 7: FRONTEND DASHBOARD
A modern React/Next.js dashboard to visualize the Hub.

- Substeps:
    1. Scaffold Next.js app in /web.
    2. Create Model Browser (List/Card view).
    3. Build Training Monitor with real-time loss charts (Recharts/D3).
    4. Add Inference Playground for testing models.
- Inputs: API endpoint responses.
- Outputs: Responsive web UI.
- Failure Modes: WebSocket disconnection; Slow rendering of large logs.
- Validation: Lighthouse audit (Performance > 90).
- Acceptance Criteria: User can trigger training and see loss curves without refresh.

### TASK 8: INFRASTRUCTURE & OBSERVABILITY
Deployment and monitoring stack using Docker Compose.

- Substeps:
    1. Create Docker Compose for MLflow, Prometheus, and Grafana.
    2. Configure Prometheus to scrape FastAPI metrics and macOS system stats.
    3. Set up Grafana dashboards for GPU/CPU/Memory usage.
    4. Finalize README and setup scripts.
- Inputs: Docker images, Prometheus config.
- Outputs: Orchestrated observability stack.
- Failure Modes: Container port conflicts; Prometheus scraping failures.
- Validation: 'docker-compose up' starts all services; Grafana shows live data.
- Acceptance Criteria: Centralized logging and metrics accessible via web.

## 6. VERIFICATION COMMANDS

### Environment & Unit Tests
```bash
# Verify environment and run core tests
uv run pytest tests/unit -v
```

### API Integration
```bash
# Test model registration
curl -X POST http://localhost:8000/models \
     -H "Content-Type: application/json" \
     -d '{"name": "Llama-3-8B-MLX", "base_model": "mlx-community/Meta-Llama-3-8B-4bit"}'
```

### Hardware Performance
```bash
# Profile MLX memory usage during dummy training
uv run python scripts/profile_mlx.py --model 8b --batch 4
```

### Observability
```bash
# Check Prometheus health
curl http://localhost:9090/-/healthy
```

## 7. FINAL ACCEPTANCE CRITERIA
1. End-to-end flow: Register model -> Start Job -> Monitor Training -> Serve Inference.
2. Performance: Inference TTFT < 50ms for 7B 4-bit models on M4 Pro.
3. Stability: System survives 24h of sequential fine-tuning jobs.
4. Visibility: GPU and RAM usage visible in Grafana during all operations.
5. Code Quality: 100% type coverage, >80% test coverage.

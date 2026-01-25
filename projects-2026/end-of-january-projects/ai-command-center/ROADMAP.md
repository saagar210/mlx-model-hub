# AI Command Center - Improvement Roadmap

**Generated:** 2026-01-25
**Based on:** Comprehensive data validation protocol audit

---

## Current State Summary

| Component | Status | Tests |
|-----------|--------|-------|
| Smart Router | ✅ Healthy | 29/29 passing |
| Desktop App (Tauri) | ✅ Builds | 8/8 passing |
| LiteLLM Proxy | ✅ Running | Integrated |
| Langfuse | ✅ Docker | Operational |
| Redis | ✅ Homebrew | Caching enabled |

**Audit Results:**
- 6 bugs identified and fixed
- 0 critical issues remaining
- 37 total tests passing (29 Python + 8 Rust)

---

## Phase 1: Production Hardening (Priority: HIGH)

**Goal:** Make the system production-ready with proper resilience patterns.

### 1.1 Circuit Breaker for LiteLLM
**Why:** If LiteLLM is down, the router keeps trying, causing cascading failures.
**Effort:** 2-3 hours

```python
# Implementation approach using pybreaker
from pybreaker import CircuitBreaker

litellm_breaker = CircuitBreaker(
    fail_max=5,           # Open after 5 failures
    timeout_duration=60,  # Stay open for 60s
    name="litellm_proxy"
)

@litellm_breaker
async def forward_to_litellm(url: str, body: dict, headers: dict):
    return await http_client.post(url, json=body, headers=headers)
```

**Files to modify:**
- `~/.config/ai-command-center/routing/smart_router.py`

### 1.2 Request Rate Limiting
**Why:** Prevent abuse and ensure fair resource usage.
**Effort:** 1-2 hours

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/v1/chat/completions")
@limiter.limit("100/minute")
async def chat_completions(request: Request):
    # ... existing code
```

**Files to modify:**
- `~/.config/ai-command-center/routing/smart_router.py`

### 1.3 Request Size Validation
**Why:** Large payloads can cause memory issues and slow processing.
**Effort:** 1 hour

```python
@app.middleware("http")
async def validate_request_size(request: Request, call_next):
    max_size = 1024 * 1024  # 1MB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_size:
        return JSONResponse(status_code=413, content={"error": "Request too large"})
    return await call_next(request)
```

---

## Phase 2: Observability Enhancements (Priority: HIGH)

**Goal:** Improve monitoring, debugging, and operational visibility.

### 2.1 Structured Logging with JSON
**Why:** Easier log parsing for analysis tools.
**Effort:** 2 hours

```python
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

# Usage
logger.info("request_routed",
    original_model=original_model,
    routed_model=routed_model,
    reason=decision.reason,
    latency_ms=decision.latency_ms)
```

### 2.2 Health Check Endpoint Expansion
**Why:** More granular health status for monitoring.
**Effort:** 1 hour

```python
@app.get("/health/detailed")
async def detailed_health():
    return {
        "status": "healthy",
        "components": {
            "litellm": await check_litellm(),
            "ollama": await check_ollama(),
            "redis": await check_redis(),
            "langfuse": await check_langfuse(),
        },
        "metrics": metrics_store.get_metrics(),
        "uptime_seconds": time.time() - start_time,
    }
```

### 2.3 Request Tracing with Correlation IDs
**Why:** Track requests across services for debugging.
**Effort:** 2 hours

```python
import uuid

@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
```

---

## Phase 3: Performance Optimizations (Priority: MEDIUM)

**Goal:** Reduce latency and improve throughput.

### 3.1 Connection Pooling Optimization
**Why:** Reduce connection overhead to LiteLLM.
**Effort:** 1 hour

```python
# Use limits for connection pool
http_client = httpx.AsyncClient(
    timeout=120.0,
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100,
        keepalive_expiry=30.0
    )
)
```

### 3.2 Response Caching for Repeated Queries
**Why:** Skip LiteLLM for identical requests (semantic caching already exists in LiteLLM).
**Effort:** 3-4 hours

```python
# Add request-level caching at router layer
import hashlib

def get_cache_key(messages: list) -> str:
    content = json.dumps(messages, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()

# Check cache before routing
cache_key = get_cache_key(messages)
cached = await redis_client.get(f"response:{cache_key}")
if cached:
    metrics_store.record_request(..., cache_hit=True)
    return json.loads(cached)
```

### 3.3 Async Metrics Recording
**Why:** Don't block request processing for metrics.
**Effort:** 1 hour

```python
import asyncio

async def record_metrics_async(**kwargs):
    """Record metrics without blocking the response."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, lambda: metrics_store.record_request(**kwargs))
```

---

## Phase 4: Security Enhancements (Priority: MEDIUM)

**Goal:** Strengthen security posture.

### 4.1 API Key Rotation Support
**Why:** Allow key rotation without downtime.
**Effort:** 2 hours

```yaml
# config.yaml
general_settings:
  master_keys:
    - sk-command-center-local
    - sk-command-center-backup  # New key for rotation
  deprecated_keys:
    - sk-old-key  # Accept but log warning
```

### 4.2 CORS Configuration by Environment
**Why:** Tighten CORS for production.
**Effort:** 1 hour

```python
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://127.0.0.1:4000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-AICC-*"],
)
```

### 4.3 Request Signature Verification (Optional)
**Why:** Prevent request tampering for sensitive deployments.
**Effort:** 3-4 hours

```python
import hmac
import hashlib

def verify_signature(request: Request, secret: str) -> bool:
    signature = request.headers.get("X-AICC-Signature")
    if not signature:
        return False
    body = await request.body()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, f"sha256={expected}")
```

---

## Phase 5: Developer Experience (Priority: MEDIUM)

**Goal:** Make the system easier to use and extend.

### 5.1 CLI Tool for Management
**Why:** Easier management without opening desktop app.
**Effort:** 4-6 hours

```bash
# Proposed CLI commands
aicc status           # Show service status
aicc logs [service]   # Tail logs
aicc config edit      # Open config in editor
aicc test             # Run test requests
aicc metrics          # Show current metrics
aicc restart          # Restart services
```

### 5.2 Configuration Validation on Startup
**Why:** Fail fast with clear error messages.
**Effort:** 2 hours

```python
from pydantic import BaseModel, validator

class PolicyConfig(BaseModel):
    privacy: PrivacyConfig
    complexity: ComplexityConfig
    injection: InjectionConfig
    routing: RoutingConfig

    @validator('routing')
    def validate_routes_exist(cls, v, values):
        # Validate all routes point to models in config.yaml
        pass
```

### 5.3 Hot Reload for Policy Changes
**Why:** Apply policy changes without restart.
**Effort:** 3 hours

```python
from watchfiles import awatch

async def watch_policy_changes():
    async for changes in awatch(POLICY_PATH):
        logger.info("Policy file changed, reloading...")
        policy = load_policy()
        reinitialize_routers()
```

---

## Phase 6: Desktop App Enhancements (Priority: LOW)

**Goal:** Improve the desktop user experience.

### 6.1 Real-time Log Streaming (WebSocket)
**Why:** More efficient than polling.
**Effort:** 4 hours

```rust
// Tauri command for WebSocket log streaming
#[tauri::command]
async fn stream_logs_websocket(service: String, window: Window) -> Result<(), String> {
    // Use tokio::spawn for background streaming
}
```

### 6.2 Dark/Light Theme Toggle
**Why:** User preference.
**Effort:** 2 hours

### 6.3 Export Metrics to CSV/JSON
**Why:** For external analysis.
**Effort:** 1 hour

### 6.4 Keyboard Shortcuts
**Why:** Power user efficiency.
**Effort:** 2 hours

```
Cmd+1 - Status tab
Cmd+2 - Dashboard tab
Cmd+3 - Config tab
Cmd+4 - Logs tab
Cmd+R - Refresh
Cmd+S - Save config
```

---

## Phase 7: Advanced Features (Priority: LOW)

**Goal:** Add capabilities for advanced use cases.

### 7.1 Multi-tenant Support
**Why:** Separate usage tracking per API key.
**Effort:** 8-10 hours

### 7.2 Cost Tracking and Budgets
**Why:** Monitor and limit spending.
**Effort:** 6-8 hours

### 7.3 A/B Testing for Prompts
**Why:** Experiment with different prompts.
**Effort:** 6-8 hours

### 7.4 Prompt Template Library
**Why:** Reusable prompts for common tasks.
**Effort:** 4-6 hours

---

## Implementation Timeline

| Phase | Effort | Priority | Suggested Sprint |
|-------|--------|----------|------------------|
| Phase 1 | 4-6 hours | HIGH | Week 1 |
| Phase 2 | 5-7 hours | HIGH | Week 1-2 |
| Phase 3 | 5-6 hours | MEDIUM | Week 2 |
| Phase 4 | 6-8 hours | MEDIUM | Week 3 |
| Phase 5 | 9-11 hours | MEDIUM | Week 3-4 |
| Phase 6 | 9-11 hours | LOW | Week 5 |
| Phase 7 | 24-32 hours | LOW | Future |

**Total Estimated Effort:** 62-81 hours

---

## Quick Wins (Can Do Now)

1. **Connection pooling** - 1 hour, immediate latency benefit
2. **CORS tightening** - 1 hour, better security
3. **Detailed health endpoint** - 1 hour, better monitoring
4. **Rate limiting** - 2 hours, abuse prevention

---

## Metrics to Track

| Metric | Current | Target |
|--------|---------|--------|
| Request latency P50 | ~50ms | <30ms |
| Request latency P99 | ~200ms | <100ms |
| Error rate | <1% | <0.1% |
| Cache hit rate | ~30% | >50% |
| Uptime | 99%+ | 99.9% |

---

## Dependencies to Add

```bash
# Python packages for new features
pip install pybreaker       # Circuit breaker
pip install slowapi          # Rate limiting
pip install structlog        # Structured logging
pip install watchfiles       # Hot reload
pip install typer            # CLI tool
```

---

## Next Steps

1. Review this roadmap and prioritize based on your needs
2. Create GitHub issues for Phase 1 tasks
3. Implement Phase 1 (circuit breaker, rate limiting, request validation)
4. Run load tests to establish baseline metrics
5. Iterate on subsequent phases based on usage patterns

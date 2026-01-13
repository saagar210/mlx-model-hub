# Load Testing (P29)

Load testing for the Knowledge Activation System API using Locust.

## Prerequisites

Install dev dependencies:
```bash
uv pip install "knowledge-activation-system[dev]"
# or
uv pip install locust
```

## Running Load Tests

### Interactive Web UI

```bash
# Start Locust with web interface
locust -f tests/load/locustfile.py --host http://localhost:8000
```

Then open http://localhost:8089 in your browser.

### Headless Mode (CI/CD)

```bash
# Run for 60 seconds with 50 users
locust -f tests/load/locustfile.py \
    --host http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 60s \
    --headless \
    --csv results/load_test

# Generate HTML report
locust -f tests/load/locustfile.py \
    --host http://localhost:8000 \
    --users 100 \
    --spawn-rate 10 \
    --run-time 120s \
    --headless \
    --html results/load_test_report.html
```

## User Types

| User Class | Description | Weight |
|------------|-------------|--------|
| `KASSearchUser` | Search-focused operations | High |
| `KASContentUser` | Content CRUD operations | Medium |
| `KASBatchUser` | Batch operations | Low |
| `KASHealthCheckUser` | Monitoring simulation | Low |
| `KASMixedUser` | Typical mixed usage | Default |

## Performance Baselines

Target performance metrics:

| Endpoint | P50 | P95 | P99 |
|----------|-----|-----|-----|
| `/search` | <100ms | <200ms | <500ms |
| `/search (rerank)` | <300ms | <500ms | <1000ms |
| `/api/v1/content` | <50ms | <100ms | <200ms |
| `/health` | <10ms | <20ms | <50ms |

## Environment Variables

```bash
# Optional: Set API key for authenticated testing
export KAS_API_KEY="your-test-api-key"
```

## Tips

1. **Start small**: Begin with 10-20 users before scaling up
2. **Monitor resources**: Watch CPU, memory, and database connections
3. **Isolate tests**: Use a dedicated test database
4. **Clean up**: Remove load test content after runs

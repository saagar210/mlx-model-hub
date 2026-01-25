# Troubleshooting Guide

Common issues and solutions for the Universal Context Engine.

## Service Issues

### Ollama Not Running

**Symptom:** Embedding or generation fails with connection error.

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Verify required models
ollama list
# Should include: nomic-embed-text, qwen2.5:14b
```

**If models are missing:**
```bash
ollama pull nomic-embed-text
ollama pull qwen2.5:14b
```

---

### Redis Connection Failed

**Symptom:** Session management fails with Redis connection error.

**Solution:**
```bash
# Check Redis status
redis-cli ping
# Should return: PONG

# Start Redis
redis-server --daemonize yes

# Or on macOS with Homebrew
brew services start redis
```

---

### KAS API Unavailable

**Symptom:** `unified_search` or `ingest_to_kas` fails.

**Solution:**
```bash
# Check KAS health
curl http://localhost:8000/health

# Start KAS
cd ~/claude-code/personal/knowledge-activation-system
uv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000

# Check logs
tail -f /tmp/kas.log
```

---

### LocalCrew API Unavailable

**Symptom:** `research` or `decompose_task` fails.

**Solution:**
```bash
# Check LocalCrew health
curl http://localhost:8001/health

# Start LocalCrew
cd ~/claude-code/personal/crewai-automation-platform
uv run uvicorn localcrew.api.main:app --host 0.0.0.0 --port 8001

# Check logs
tail -f /tmp/localcrew.log
```

---

### PostgreSQL Not Running

**Symptom:** KAS or LocalCrew fail with database connection error.

**Solution:**
```bash
# Start PostgreSQL via Docker
cd ~/claude-code/personal/knowledge-activation-system
docker compose -f docker/docker-compose.yml up -d postgres

# Check status
docker ps | grep postgres

# Verify connection
psql -h localhost -p 5433 -U postgres -c "SELECT 1"
```

---

## ChromaDB Issues

### Settings Conflict Error

**Symptom:**
```
ValueError: An instance of Chroma already exists for path with different settings
```

**Cause:** Multiple components trying to use ChromaDB with different settings.

**Solution:** All components must use identical settings:
```python
ChromaSettings(
    anonymized_telemetry=False,
    allow_reset=True,
)
```

The system is designed to use lazy initialization with consistent settings. If you see this error, restart the MCP server.

---

### ChromaDB Corruption

**Symptom:** Queries fail or return unexpected results.

**Solution:**
```bash
# Backup existing data
cp -r ~/.local/share/universal-context/chromadb ~/.local/share/universal-context/chromadb.bak

# Delete and recreate
rm -rf ~/.local/share/universal-context/chromadb

# Restart the MCP server to recreate collections
```

---

### ChromaDB Path Permission

**Symptom:** Permission denied errors.

**Solution:**
```bash
# Check permissions
ls -la ~/.local/share/universal-context/

# Fix permissions
chmod -R u+rw ~/.local/share/universal-context/
```

---

## MCP Server Issues

### Server Won't Start

**Symptom:** Claude Code can't connect to universal-context MCP server.

**Check 1: Dependencies**
```bash
cd /path/to/ai-native-dev-environment
uv sync
```

**Check 2: Module loads**
```bash
uv run python -c "from universal_context_engine import mcp; print('OK')"
```

**Check 3: MCP registration**
Verify `~/.claude/mcp_settings.json` contains:
```json
{
  "universal-context": {
    "command": "uv",
    "args": ["run", "--directory", "/correct/path/to/ai-native-dev-environment", "python", "-m", "universal_context_engine.server"]
  }
}
```

**Check 4: Manual server start**
```bash
cd /path/to/ai-native-dev-environment
uv run python -m universal_context_engine.server
```

---

### Tools Not Appearing

**Symptom:** MCP server starts but tools aren't available in Claude Code.

**Solution:**
1. Restart Claude Code completely
2. Check MCP server logs for registration errors
3. Verify all tool decorators use correct FastMCP syntax

---

## Embedding Issues

### Slow Embedding Generation

**Symptom:** `save_context` takes too long.

**Possible causes:**
1. Ollama running on CPU instead of GPU
2. Model not loaded in memory

**Solution:**
```bash
# Pre-load model
curl http://localhost:11434/api/generate -d '{"model": "nomic-embed-text", "prompt": "test"}'

# Check Ollama GPU usage
ollama ps
```

---

### Embedding Dimension Mismatch

**Symptom:** Search returns no results or errors.

**Solution:**
If you changed embedding models, you need to re-embed all content:
```bash
# Clear existing embeddings
rm -rf ~/.local/share/universal-context/chromadb

# Restart and re-ingest content
```

---

## Session Issues

### Session Not Persisting

**Symptom:** Session data lost between `start_session` and `end_session`.

**Check Redis:**
```bash
redis-cli keys "session:*"
```

**Solution:**
Ensure Redis is running and accessible at the configured URL.

---

### Session Summary Generation Fails

**Symptom:** `end_session` fails during summarization.

**Cause:** Ollama qwen2.5:14b model not available or overloaded.

**Solution:**
```bash
# Check model
ollama list | grep qwen

# Test generation
curl http://localhost:11434/api/generate -d '{"model": "qwen2.5:14b", "prompt": "Hello", "stream": false}'
```

---

## Dashboard Issues

### Dashboard Won't Start

**Symptom:** Port 8002 already in use or connection refused.

**Solution:**
```bash
# Check if port in use
lsof -i :8002

# Kill existing process
pkill -f "uvicorn universal_context_engine.dashboard"

# Start dashboard
cd /path/to/ai-native-dev-environment
uv run uvicorn universal_context_engine.dashboard.api:app --host 0.0.0.0 --port 8002
```

---

### Dashboard Shows Degraded Status

**Symptom:** `/health` shows one or more services as unhealthy.

**Action:** Check individual service health:
```bash
# Check each service
curl http://localhost:11434/api/tags   # Ollama
curl http://localhost:8000/health       # KAS
curl http://localhost:8001/health       # LocalCrew
redis-cli ping                          # Redis
```

Start any services that are down.

---

## Performance Issues

### Slow Search Results

**Possible causes:**
1. ChromaDB collection too large
2. Ollama embedding latency
3. Too many results requested

**Solutions:**
1. Use more specific queries
2. Add filters (project, context_type)
3. Reduce limit parameter
4. Consider archiving old context

---

### High Memory Usage

**Possible causes:**
1. Large Redis session buffer
2. ChromaDB in-memory operations
3. Multiple large embeddings

**Solutions:**
```bash
# Check Redis memory
redis-cli info memory

# Flush old sessions
redis-cli KEYS "session:*" | xargs redis-cli DEL

# Monitor system memory
top -l 1 | head -20
```

---

## Testing

### Run All Tests

```bash
cd /path/to/ai-native-dev-environment
uv run pytest
```

### Run Specific Tests

```bash
# Context store tests
uv run pytest tests/test_context_store.py -v

# Server tests
uv run pytest tests/test_server.py -v

# Session tests
uv run pytest tests/test_session.py -v
```

### Test with Coverage

```bash
uv run pytest --cov=universal_context_engine --cov-report=term-missing
```

---

## Logs

### Service Logs

```bash
# KAS
tail -f /tmp/kas.log

# LocalCrew
tail -f /tmp/localcrew.log

# UCE Dashboard
tail -f /tmp/uce-dashboard.log
```

### MCP Server Logs

The MCP server logs to stderr. In Claude Code, check the MCP server output panel or run manually:
```bash
uv run python -m universal_context_engine.server 2>&1 | tee /tmp/uce.log
```

---

## Getting Help

1. Check service health: `service_status` tool
2. Check dashboard: http://localhost:8002/health
3. Run tests: `uv run pytest`
4. Check logs in `/tmp/*.log`
5. File an issue with:
   - Error message
   - Service status output
   - Relevant log entries

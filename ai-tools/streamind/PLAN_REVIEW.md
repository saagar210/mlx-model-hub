# StreamMind Implementation Plan Review
# Generated: January 12, 2026

## Executive Summary

This document captures all identified improvements, risks, and removals based on comprehensive web and local research. These changes will be applied to the main IMPLEMENTATION_PLAN.md.

---

## CRITICAL IMPROVEMENTS REQUIRED

### 1. CLI Framework: Typer Instead of Click

**Current Plan:** Click + Rich
**Recommendation:** Typer + Rich

**Rationale:**
- Typer is built on Click but provides better DX
- Auto-generates help from type hints
- Already installed locally (v0.21.1)
- Used successfully in KAS project (`cli.py`)
- Modern Python 3.11+ friendly with native type hints

**Code Pattern (from KAS):**
```python
import typer
from rich.console import Console

app = typer.Typer(help="StreamMind - Real-time screen analysis")
console = Console()

@app.command()
def ask(
    query: str = typer.Argument(..., help="Question about your screen"),
    monitor: int = typer.Option(1, "--monitor", "-m", help="Monitor ID"),
    stream: bool = typer.Option(False, "--stream", "-s", help="Stream response"),
):
    """Ask a question about your current screen."""
    # Implementation
```

### 2. Package Manager: uv Instead of pip

**Current Plan:** pip install
**Recommendation:** uv

**Rationale:**
- 10-100x faster than pip
- Already installed locally (v0.9.24)
- Drop-in replacement for pip
- Better dependency resolution
- Native lockfile support

**Commands:**
```bash
# Instead of: pip install -e ".[dev]"
uv pip install -e ".[dev]"

# Create venv
uv venv

# Sync dependencies
uv sync
```

### 3. Logging: loguru Instead of stdlib logging

**Current Plan:** stdlib logging
**Recommendation:** loguru

**Rationale:**
- Already installed (v0.7.3)
- Zero configuration needed
- Better formatting out of the box
- Easier exception handling
- Rotation and retention built-in

**Code Pattern:**
```python
from loguru import logger

# Configure once in main
logger.add(
    "~/.streamind/logs/streamind.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO"
)

# Use throughout
logger.info("Starting capture")
logger.error("Failed to connect to Ollama")
logger.debug(f"Frame hash: {hash_value}")
```

### 4. Retry Logic: tenacity

**Current Plan:** No retry logic
**Recommendation:** Add tenacity for Ollama API calls

**Rationale:**
- Already installed (v9.1.2)
- Handles transient failures gracefully
- Configurable backoff strategies
- Clean decorator syntax

**Code Pattern:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def analyze(self, image, prompt):
    """Analyze with automatic retry on failure."""
    return await self._analyze_ollama(image, prompt)
```

### 5. macOS Tahoe Permission Handling

**Current Plan:** Basic permission request
**Recommendation:** .app bundle requirement + first-run guide

**Critical Finding:**
Starting with macOS Tahoe (15.x), **non-bundled executables do NOT appear in the Screen Recording permission list**. Users cannot grant permission to Python scripts directly.

**Solutions:**
1. **Primary:** Use py2app to create .app bundle (already planned)
2. **Fallback:** Create minimal Swift helper app that captures and pipes to Python
3. **Development:** Use `tccutil` for development testing (requires SIP disabled)

**Implementation:**
```python
# First-run check in menubar.py
def check_screen_permission():
    """Check if running as .app bundle with Screen Recording permission."""
    import sys
    if not sys.executable.endswith('.app/Contents/MacOS/python'):
        console.print(
            "[yellow]Warning:[/yellow] Running outside .app bundle.\n"
            "Screen Recording may not work on macOS Tahoe+.\n"
            "Build with: python scripts/build_app.py py2app"
        )
```

### 6. Response Caching

**Current Plan:** No response caching
**Recommendation:** Add response cache for repeated queries

**Rationale:**
- Same screen + same query = same response
- Reduces Ollama load
- Instant responses for cache hits
- Pattern exists in inference-server

**Code Pattern (from response_cache.py):**
```python
from functools import lru_cache
import hashlib

class ResponseCache:
    def __init__(self, max_size: int = 100):
        self._cache = {}
        self._max_size = max_size

    def get_key(self, image_hash: str, query: str) -> str:
        return hashlib.sha256(f"{image_hash}:{query}".encode()).hexdigest()[:16]

    def get(self, image_hash: str, query: str) -> str | None:
        key = self.get_key(image_hash, query)
        return self._cache.get(key)

    def set(self, image_hash: str, query: str, response: str):
        key = self.get_key(image_hash, query)
        if len(self._cache) >= self._max_size:
            # Remove oldest entry
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = response
```

---

## IDENTIFIED RISKS

### High Priority Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **macOS Tahoe permissions** | HIGH | CRITICAL | Build as .app bundle, test on Tahoe before release |
| **Ollama model loading slow** | MEDIUM | HIGH | Keep model warm, add loading indicator, consider model preloading |
| **Vision response latency** | MEDIUM | HIGH | Image size optimization, response streaming, caching |

### Medium Priority Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **PyObjC complexity** | MEDIUM | MEDIUM | Graceful fallback, comprehensive error handling |
| **Memory leaks in continuous mode** | MEDIUM | MEDIUM | Frame buffer limits, periodic cleanup |
| **rumps app stability** | LOW | MEDIUM | CLI-first approach, menu bar optional |

### Low Priority Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **Ollama API changes** | LOW | LOW | Abstract client, version pinning |
| **SQLite corruption** | LOW | MEDIUM | WAL mode, regular backups |

---

## THINGS TO REMOVE

### 1. Click References
- Replace all Click imports with Typer
- Update CLI code templates
- Update pyproject.toml

### 2. pip Install Instructions
- Replace with uv commands
- Update README
- Update development setup

### 3. Redundant Logging Setup
- Remove stdlib logging.basicConfig
- Use loguru throughout

### 4. Time Estimates
- Remove all "Estimated Effort: X hours" (per user preferences)
- Focus on what, not when

---

## EXPANDED TASK DETAILS

### Tasks 11-20 Need Full Expansion

The current plan summarizes Tasks 11-20. Each needs:
- Full subtask breakdown
- Code templates
- Acceptance criteria
- Test requirements

---

## LOCAL ASSETS TO LEVERAGE

### Already Installed Packages (Relevant)
```
uv                  0.9.24    # Package manager
typer               0.21.1    # CLI framework
loguru              0.7.3     # Logging
tenacity            9.1.2     # Retry logic
structlog           25.5.0    # Structured logging (alternative)
watchdog            6.0.0     # File system events
APScheduler         3.10.4    # Task scheduling
ruff                0.14.11   # Linting
ollama              0.6.1     # Ollama client
httpx               0.28.1    # HTTP client
fastapi             0.116.2   # API framework
aiosqlite           0.22.1    # Async SQLite
pydantic            2.x       # Data validation
pydantic-settings   2.x       # Settings management
```

### Reusable Code Patterns

1. **CLI Pattern** - KAS `cli.py`: Typer + Rich console
2. **Config Pattern** - inference-server `config.py`: pydantic-settings
3. **Cache Pattern** - inference-server `response_cache.py`: SQLite caching
4. **Vision Service** - inference-server `ollama_vision_service.py`: Ollama client

---

## NEXT STEPS

1. Update IMPLEMENTATION_PLAN.md Section 4 (Technology Decisions)
2. Update all CLI code templates to use Typer
3. Add loguru and tenacity patterns
4. Expand Tasks 11-20 with full details
5. Add macOS Tahoe permission section
6. Add response caching module
7. Update installation instructions for uv

---

**Review Status:** Complete
**Ready for Implementation Plan Update:** Yes

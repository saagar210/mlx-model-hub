# Phase 7 Remediation Roadmap

**Status:** NO-GO — Critical security and architectural issues identified
**Auditor:** Codex (Senior Architect)
**Date:** 2026-01-25
**Revision:** 2 — Docker-free architecture

---

## Executive Summary

The Phase 7 implementation has fundamental security flaws that must be addressed before proceeding to Phase 8. The sandbox provides a **false sense of security** — subprocess mode has no real isolation.

### Blocker Issues (Must Fix)
1. **Sandbox isolation is theater** — subprocess mode only sets NO_PROXY
2. **Rollback integrity unverified** — tampered JSON can be restored
3. **Orchestrator broken** — passes wrong params, never creates sandbox

### Design Decision: Docker-Free Architecture

Per stakeholder decision, we will **not use Docker** for sandboxing. Instead, we implement a multi-layered pure-Python isolation strategy:

1. **RestrictedPython** — Compile-time restrictions on dangerous constructs
2. **AST Validation** — Pre-execution security analysis
3. **Restricted Builtins** — Custom safe_builtins with no dangerous functions
4. **Import Hooks** — Control what modules can be imported
5. **Resource Limits** — Memory, CPU, time limits via `resource` module
6. **Timeout Enforcement** — Hard timeouts via `signal` module

This provides defense-in-depth without external dependencies.

**References:**
- [RestrictedPython](https://github.com/zopefoundation/RestrictedPython) — Mature restricted execution environment
- [Python Sandboxing Wiki](https://wiki.python.org/moin/SandboxedPython) — Overview of approaches
- [CodeJail](https://github.com/openedx/codejail) — OpenEdX's approach (AppArmor-based)

---

## Remediation Phases

### Phase R1: Critical Security Fixes (BLOCKER)
**Estimated Effort:** 6-8 hours
**Priority:** P0 — Must complete before any other work

#### R1.1: Implement RestrictedPython Sandbox

**Problem:** Current subprocess execution has no real isolation — code runs with full host access.

**Solution:** Replace subprocess execution with RestrictedPython-based execution.

**New Architecture:**
```python
# sandbox.py - RestrictedPython-based execution
from RestrictedPython import compile_restricted, safe_builtins
from RestrictedPython.Guards import safe_builtins, guarded_iter_unpack_sequence
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem

@dataclass
class SandboxConfig:
    # Resource limits
    max_memory_mb: int = 256
    timeout_seconds: int = 30
    max_output_size: int = 1_000_000  # 1MB output limit

    # Security settings
    allowed_imports: set[str] = field(default_factory=lambda: SAFE_IMPORTS)
    security_mode: str = "high"  # "standard", "high", "strict"

    # Execution settings
    enable_print: bool = True
    enable_getattr: bool = False  # Dangerous - disabled by default


# Safe imports whitelist
SAFE_IMPORTS = {
    # Math & numbers
    "math", "statistics", "decimal", "fractions", "random",
    # Data structures
    "collections", "itertools", "functools", "operator",
    # Text
    "string", "re", "textwrap",
    # Data formats (read-only)
    "json", "csv",
    # Time (read-only)
    "datetime", "time", "calendar",
    # Typing & structure
    "typing", "dataclasses", "enum", "abc",
    # Safe utilities
    "copy", "pprint", "logging", "warnings",
}


class RestrictedSandbox:
    """Pure-Python sandbox using RestrictedPython."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._setup_restricted_globals()

    def _setup_restricted_globals(self):
        """Create restricted execution environment."""
        self.restricted_globals = {
            "__builtins__": self._get_safe_builtins(),
            "_getiter_": default_guarded_getiter,
            "_getitem_": default_guarded_getitem,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_print_": self._guarded_print if self.config.enable_print else None,
            "_getattr_": self._guarded_getattr if self.config.enable_getattr else None,
        }

    def _get_safe_builtins(self) -> dict:
        """Return safe builtins based on security mode."""
        builtins = dict(safe_builtins)

        # Remove dangerous builtins even from safe_builtins
        dangerous = {"compile", "eval", "exec", "open", "input", "__import__"}
        for name in dangerous:
            builtins.pop(name, None)

        # Add controlled import
        builtins["__import__"] = self._guarded_import

        return builtins

    def _guarded_import(self, name, *args, **kwargs):
        """Only allow whitelisted imports."""
        base_module = name.split(".")[0]
        if base_module not in self.config.allowed_imports:
            raise ImportError(f"Import of '{name}' is not allowed in sandbox")
        return __import__(name, *args, **kwargs)

    async def execute(self, code: str) -> SandboxResult:
        """Execute code in restricted environment."""
        result = SandboxResult()

        # 1. Compile with RestrictedPython
        try:
            byte_code = compile_restricted(
                code,
                filename="<sandbox>",
                mode="exec",
            )
            if byte_code.errors:
                result.error = f"Compilation errors: {byte_code.errors}"
                return result
        except SyntaxError as e:
            result.error = f"Syntax error: {e}"
            return result

        # 2. Execute with resource limits
        result = await self._execute_with_limits(byte_code.code)
        return result
```

**Implementation Tasks:**
- [ ] Add `RestrictedPython>=7.0` to dependencies
- [ ] Create `RestrictedSandbox` class with compile_restricted
- [ ] Implement `_guarded_import` with whitelist checking
- [ ] Implement `_guarded_getattr` (disabled by default)
- [ ] Implement `_guarded_print` with output size limit
- [ ] Create `SAFE_IMPORTS` whitelist constant
- [ ] Add `security_mode` setting for tiered restrictions
- [ ] Remove Docker-related code from sandbox.py
- [ ] Update `SandboxConfig` to remove Docker fields

**Acceptance Criteria:**
- Code compiled through RestrictedPython only
- Dangerous builtins removed (eval, exec, open, __import__)
- Import whitelist enforced
- No Docker dependency

---

#### R1.2: Add Resource Limits Enforcement

**Problem:** No memory, CPU, or time limits on code execution.

**Solution:** Use Python's `resource` module (Unix/macOS) and `signal` for timeouts.

```python
import resource
import signal
from contextlib import contextmanager

class ResourceLimiter:
    """Enforce resource limits on code execution."""

    def __init__(self, config: SandboxConfig):
        self.config = config

    @contextmanager
    def enforce_limits(self):
        """Context manager to enforce resource limits."""
        old_limits = {}

        try:
            # Set memory limit
            mem_bytes = self.config.max_memory_mb * 1024 * 1024
            old_limits["AS"] = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

            # Set CPU time limit (backup for timeout)
            cpu_seconds = self.config.timeout_seconds + 5
            old_limits["CPU"] = resource.getrlimit(resource.RLIMIT_CPU)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))

            # Set up signal-based timeout
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Execution timed out after {self.config.timeout_seconds}s")

            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.config.timeout_seconds)

            yield

        finally:
            # Restore limits
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler if 'old_handler' in dir() else signal.SIG_DFL)

            for name, limit in old_limits.items():
                resource.setrlimit(getattr(resource, f"RLIMIT_{name}"), limit)
```

**Implementation Tasks:**
- [ ] Create `ResourceLimiter` class
- [ ] Implement memory limit via `RLIMIT_AS`
- [ ] Implement CPU limit via `RLIMIT_CPU`
- [ ] Implement timeout via `signal.SIGALRM`
- [ ] Handle Windows gracefully (log warning, no enforcement)
- [ ] Integrate with RestrictedSandbox execution

**Acceptance Criteria:**
- Memory limit causes MemoryError on violation
- Timeout raises TimeoutError
- Limits restored after execution

---

#### R1.3: Fix Orchestrator Sandbox Integration

**Problem:** Orchestrator passes wrong params and doesn't properly integrate sandbox.

**Current Broken Code (orchestrator.py:428-461):**
```python
config = SandboxConfig(
    timeout=self.config.sandbox_timeout,  # WRONG: field is timeout_seconds
    network_disabled=True,  # WRONG: field doesn't exist
)
```

**Fix:**
```python
async def _run_sandbox_tests(self, code: str) -> SandboxResult:
    config = SandboxConfig(
        timeout_seconds=self.config.sandbox_timeout,
        max_memory_mb=self.config.max_memory_mb,
        security_mode="high",
    )

    sandbox = RestrictedSandbox(config)

    # Validate with AST first (fast)
    validation = self.validator.validate(code)
    if not validation.syntax_valid:
        return SandboxResult(
            success=False,
            error=f"Syntax invalid: {validation.issues}"
        )

    # Execute in restricted environment
    result = await sandbox.execute(code)
    return result
```

**Implementation Tasks:**
- [ ] Fix parameter names in orchestrator
- [ ] Use new `RestrictedSandbox` class
- [ ] Remove Docker-specific configuration
- [ ] Add AST validation before sandbox execution

**Acceptance Criteria:**
- Orchestrator uses correct parameter names
- RestrictedSandbox properly instantiated
- No "Sandbox not created" errors

---

#### R1.3: Rollback Integrity Verification

**Problem:** `_load_snapshots()` trusts stored `code_hash` without recomputation.

**Current Vulnerable Code (rollback.py:527-561):**
```python
def _load_snapshots(self) -> None:
    with open(file_path) as f:
        data = json.load(f)

    for s in data.get("snapshots", []):
        snapshot = CodeSnapshot(
            code=s["code"],
            code_hash=s["code_hash"],  # TRUSTED WITHOUT VERIFICATION
            ...
        )
```

**Fix:**
```python
def _load_snapshots(self) -> None:
    with open(file_path) as f:
        data = json.load(f)

    for s in data.get("snapshots", []):
        # Recompute hash and verify
        stored_hash = s["code_hash"]
        computed_hash = hashlib.sha256(s["code"].encode()).hexdigest()[:16]

        if stored_hash != computed_hash:
            raise IntegrityError(
                f"Snapshot {s['id']} failed integrity check: "
                f"stored={stored_hash}, computed={computed_hash}"
            )

        snapshot = CodeSnapshot(...)
```

**Implementation Tasks:**
- [ ] Create `IntegrityError` exception class
- [ ] In `_load_snapshots()`, recompute hash for each snapshot
- [ ] Compare computed hash with stored hash
- [ ] Raise `IntegrityError` on mismatch
- [ ] Add `verify_integrity()` public method for manual checks
- [ ] Add HMAC option for tamper-evident signatures (optional, for R5)

**Acceptance Criteria:**
- Modified JSON files are detected and rejected
- Clear error message on integrity failure
- Tests verify tamper detection

---

### Phase R2: Expanded Security Checks (HIGH)
**Estimated Effort:** 3-4 hours
**Priority:** P1 — Required for defense-in-depth

#### R2.1: Expand Blocked Imports

**Problem:** Only blocks 8 modules; `os`, `subprocess`, `importlib`, `sys`, `pathlib` are allowed.

**Current (validator.py:188-196):**
```python
self.blocked_imports = blocked_imports or {
    "ctypes", "multiprocessing", "socket",
    "http.server", "ftplib", "telnetlib", "smtplib",
}
```

**Fix — Add tiered blocking:**
```python
# High-risk: Always blocked
BLOCKED_IMPORTS_HIGH = {
    "ctypes", "multiprocessing", "socket",
    "http.server", "ftplib", "telnetlib", "smtplib",
    "subprocess", "os", "sys", "importlib",
    "pathlib", "shutil", "tempfile", "glob",
    "pickle", "dill", "marshal", "shelve",
    "requests", "urllib", "httpx", "aiohttp",
    "paramiko", "fabric", "pexpect",
}

# Medium-risk: Blocked in high-security mode
BLOCKED_IMPORTS_MEDIUM = {
    "threading", "concurrent", "asyncio",
    "signal", "atexit", "gc",
}

# Allowlist mode for maximum security
ALLOWED_IMPORTS_STRICT = {
    "math", "statistics", "decimal", "fractions",
    "datetime", "time", "calendar",
    "collections", "itertools", "functools",
    "operator", "string", "re",
    "json", "csv", "dataclasses",
    "typing", "abc", "enum",
    "logging", "warnings",
    "copy", "pprint",
}
```

**Implementation Tasks:**
- [ ] Create `BLOCKED_IMPORTS_HIGH`, `BLOCKED_IMPORTS_MEDIUM` constants
- [ ] Create `ALLOWED_IMPORTS_STRICT` for allowlist mode
- [ ] Add `security_mode: Literal["standard", "high", "strict"]` to validator
- [ ] In `high` mode, block both HIGH and MEDIUM sets
- [ ] In `strict` mode, only allow ALLOWED_IMPORTS_STRICT

**Acceptance Criteria:**
- `import os` blocked in high-security mode
- `import subprocess` blocked in all modes
- Allowlist mode rejects unlisted imports

---

#### R2.2: AST-Based Security Checks

**Problem:** Regex patterns for `subprocess.*shell=True` are easily bypassed.

**Bypass Examples:**
```python
# Current regex misses these:
from subprocess import run; run("cmd", shell=True)
subprocess.run(cmd, **{"shell": True})
s = subprocess; s.run("cmd", shell=True)
```

**Fix — Add AST visitor:**
```python
class SecurityVisitor(ast.NodeVisitor):
    """AST-based security checker."""

    def __init__(self):
        self.issues = []
        self._subprocess_aliases = set()

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "subprocess":
                self._subprocess_aliases.add(alias.asname or "subprocess")
        self.generic_visit(node)

    def visit_Call(self, node):
        # Check subprocess.run/call/Popen with shell=True
        if self._is_subprocess_call(node):
            for kw in node.keywords:
                if kw.arg == "shell":
                    if isinstance(kw.value, ast.Constant) and kw.value.value:
                        self.issues.append(SecurityIssue(
                            "subprocess with shell=True",
                            node.lineno
                        ))
                    elif isinstance(kw.value, ast.Name):
                        # shell=variable — flag for review
                        self.issues.append(SecurityIssue(
                            "subprocess with dynamic shell argument",
                            node.lineno,
                            severity="warning"
                        ))

        # Check __import__, importlib.import_module
        if self._is_dynamic_import(node):
            self.issues.append(SecurityIssue(
                "dynamic import detected",
                node.lineno
            ))

        self.generic_visit(node)
```

**Implementation Tasks:**
- [ ] Create `SecurityVisitor` AST visitor class
- [ ] Track import aliases (subprocess, os, etc.)
- [ ] Detect `shell=True` in any position/form
- [ ] Detect `**kwargs` patterns that could hide shell=True
- [ ] Detect `__import__()` and `importlib.import_module()`
- [ ] Detect `eval()`, `exec()`, `compile()` with any arguments
- [ ] Detect `pathlib.Path.write_*` and `open(..., 'w')`
- [ ] Integrate visitor into `_validate_security()`

**Acceptance Criteria:**
- All bypass examples are caught
- Dynamic arguments flagged for review
- AST checks run in addition to regex

---

### Phase R3: Orchestrator State Machine (MEDIUM)
**Estimated Effort:** 2-3 hours
**Priority:** P2 — Required for proper operation

#### R3.1: Fix Unused test_script

**Problem:** `test_script` is defined but `execute(code, script)` ignores script when code is provided.

**Current (orchestrator.py:450-456):**
```python
test_script = """
import sys
exec(open(sys.argv[1]).read())
print("OK")
"""
result = await sandbox.execute(code, test_script)  # test_script IGNORED
```

**Fix:**
```python
# Write code to sandbox, then execute test_script
code_path = sandbox.write_code(code, "module_under_test.py")
result = await sandbox.execute(script=str(code_path))

# Or: run actual execution test
result = await sandbox.execute(code=code)
if result.success:
    result.test_output = "Basic execution passed"
```

**Implementation Tasks:**
- [ ] Remove misleading test_script or actually use it
- [ ] If using test_script, write code first, then execute script
- [ ] Add meaningful execution test (import, basic call)

---

#### R3.2: Implement TESTING State

**Problem:** `EvolutionStatus.TESTING` exists but is never set.

**Fix:**
```python
async def evolve(self, code: str, ...):
    # ... proposal generation ...

    # 4. Sandbox testing
    if self.config.sandbox_enabled:
        attempt.status = EvolutionStatus.TESTING  # ADD THIS
        sandbox_result = await self._run_sandbox_tests(...)
```

**Implementation Tasks:**
- [ ] Set `status = TESTING` before sandbox tests
- [ ] Set `status = VALIDATING` after sandbox, before validation
- [ ] Emit events/callbacks for each state transition

---

#### R3.3: Implement PENDING_APPROVAL State

**Problem:** `require_human_approval=True` doesn't change behavior.

**Current (orchestrator.py:275-290):**
```python
decision = self._make_decision(attempt)
attempt.approved = decision
attempt.status = EvolutionStatus.APPROVED if decision else EvolutionStatus.REJECTED
# require_human_approval is NEVER checked
```

**Fix:**
```python
# Add PENDING_APPROVAL to EvolutionStatus enum
class EvolutionStatus(str, Enum):
    PENDING_APPROVAL = "pending_approval"  # NEW
    ...

# In evolve():
if self.config.require_human_approval:
    attempt.status = EvolutionStatus.PENDING_APPROVAL
    attempt.rejection_reason = "Awaiting human approval"
    # Don't auto-approve, don't auto-deploy
else:
    decision = self._make_decision(attempt)
    ...
```

**Implementation Tasks:**
- [ ] Add `PENDING_APPROVAL` to `EvolutionStatus` enum
- [ ] Check `require_human_approval` before making automated decision
- [ ] If true, set status to PENDING_APPROVAL and return
- [ ] Update `approve_manually()` to handle PENDING_APPROVAL state
- [ ] Add `is_pending_approval()` helper method

---

#### R3.4: Handle Missing fitness_fn

**Problem:** Without fitness_fn, improvement defaults to 0, rejecting everything.

**Fix:**
```python
# Option 1: Accept validation-only improvements when no fitness_fn
if not fitness_fn:
    # No fitness function — accept if validation passes
    if attempt.validation_result and attempt.validation_result.valid:
        attempt.improvement["validation_only"] = True
        return True  # Or require human approval

# Option 2: Require fitness_fn explicitly
if not fitness_fn and self.config.require_fitness_fn:
    raise ValueError("fitness_fn required for evolution")
```

**Implementation Tasks:**
- [ ] Add `require_fitness_fn: bool = False` to EvolutionConfig
- [ ] If no fitness_fn and not required, use validation-only mode
- [ ] Document behavior clearly
- [ ] Log warning when fitness_fn is missing

---

### Phase R4: Code Quality Fixes (MEDIUM)
**Estimated Effort:** 2-3 hours
**Priority:** P2

#### R4.1: Clean Up Sandbox Module

**Problem:** Current sandbox.py has Docker code that will be removed.

**Implementation Tasks:**
- [ ] Remove `_execute_docker()` method
- [ ] Remove `_execute_subprocess()` method (replace with RestrictedPython)
- [ ] Remove Docker-related config fields
- [ ] Simplify `SandboxConfig` to RestrictedPython-relevant fields
- [ ] Update `SandboxPool` to work with new sandbox
- [ ] Remove unused imports (subprocess, etc.)

---

#### R4.2: Output Capture and Limits

**Problem:** Need to capture print output without allowing unbounded output.

**Fix:**
```python
class OutputCapture:
    """Capture and limit output from sandboxed code."""

    def __init__(self, max_size: int = 1_000_000):
        self.max_size = max_size
        self.buffer = io.StringIO()
        self.truncated = False

    def write(self, text: str) -> int:
        current_size = self.buffer.tell()
        if current_size >= self.max_size:
            self.truncated = True
            return 0

        allowed = min(len(text), self.max_size - current_size)
        self.buffer.write(text[:allowed])
        if allowed < len(text):
            self.truncated = True
        return allowed

    def getvalue(self) -> str:
        return self.buffer.getvalue()
```

**Implementation Tasks:**
- [ ] Create `OutputCapture` class with size limits
- [ ] Integrate with RestrictedPython's `_print_` guard
- [ ] Add `truncated` flag to `SandboxResult`
- [ ] Test output limiting works

---

#### R4.3: Error Message Sanitization

**Problem:** Error messages might leak information about host system.

**Fix:**
```python
def sanitize_error(error: Exception) -> str:
    """Remove potentially sensitive information from errors."""
    message = str(error)

    # Remove absolute paths
    message = re.sub(r'/Users/[^/]+/', '/home/user/', message)
    message = re.sub(r'C:\\Users\\[^\\]+\\', 'C:\\Users\\user\\', message)

    # Remove line numbers from tracebacks if they reference host files
    # Keep line numbers for sandbox code

    return message
```

**Implementation Tasks:**
- [ ] Create `sanitize_error()` function
- [ ] Apply to all error messages in SandboxResult
- [ ] Test path sanitization works

---

### Phase R5: Test Coverage (HIGH)
**Estimated Effort:** 4-5 hours
**Priority:** P1 — Required for confidence in fixes

#### R5.1: RestrictedPython Sandbox Tests

**Current Gap:** No tests for RestrictedPython isolation, import blocking, or resource limits.

**New Tests:**
```python
class TestRestrictedSandbox:
    async def test_blocked_builtins(self):
        """Dangerous builtins are not available."""
        sandbox = RestrictedSandbox(SandboxConfig())

        # eval should be blocked
        result = await sandbox.execute("x = eval('1+1')")
        assert not result.success
        assert "eval" in result.error.lower()

        # exec should be blocked
        result = await sandbox.execute("exec('x=1')")
        assert not result.success

        # open should be blocked
        result = await sandbox.execute("f = open('/etc/passwd')")
        assert not result.success

    async def test_import_whitelist(self):
        """Only whitelisted imports allowed."""
        sandbox = RestrictedSandbox(SandboxConfig())

        # Safe import works
        result = await sandbox.execute("import math; print(math.pi)")
        assert result.success

        # Dangerous import blocked
        result = await sandbox.execute("import os")
        assert not result.success
        assert "not allowed" in result.error.lower()

        result = await sandbox.execute("import subprocess")
        assert not result.success

    async def test_attribute_access_guarded(self):
        """Dangerous attribute access is blocked."""
        sandbox = RestrictedSandbox(SandboxConfig(enable_getattr=False))

        # __class__ access blocked
        result = await sandbox.execute("x = ().__class__.__bases__[0].__subclasses__()")
        assert not result.success

    async def test_timeout_enforced(self):
        """Infinite loops are terminated."""
        config = SandboxConfig(timeout_seconds=2)
        sandbox = RestrictedSandbox(config)

        result = await sandbox.execute("while True: pass")
        assert result.timed_out
        assert result.execution_time_ms < 3000  # Should stop around 2s

    async def test_memory_limit_enforced(self):
        """Memory exhaustion is prevented."""
        config = SandboxConfig(max_memory_mb=50)
        sandbox = RestrictedSandbox(config)

        result = await sandbox.execute("x = 'a' * (100 * 1024 * 1024)")  # 100MB string
        assert not result.success
        assert result.memory_exceeded or "MemoryError" in str(result.error)

    async def test_output_limited(self):
        """Output size is limited."""
        config = SandboxConfig(max_output_size=1000)
        sandbox = RestrictedSandbox(config)

        result = await sandbox.execute("print('x' * 10000)")
        assert len(result.stdout) <= 1000
        assert result.output_truncated
```

**Implementation Tasks:**
- [ ] Test all dangerous builtins are blocked
- [ ] Test import whitelist enforcement
- [ ] Test attribute access guards
- [ ] Test timeout enforcement
- [ ] Test memory limit enforcement
- [ ] Test output size limiting
- [ ] Test escape attempts (introspection attacks)

---

#### R5.2: Orchestrator Integration Tests

**Current Gap:** Tests disable sandbox, so real sandbox path untested.

**New Tests:**
```python
@pytest.mark.integration
class TestOrchestratorIntegration:
    async def test_full_evolution_cycle_with_sandbox(self):
        """Full evolution with Docker sandbox enabled."""
        config = EvolutionConfig(
            sandbox_enabled=True,
            auto_deploy=False,
            require_human_approval=False,
        )
        orchestrator = EvolutionOrchestrator(config=config)

        code = "def add(a, b): return a + b"
        attempt = await orchestrator.evolve(code, fitness_fn=lambda c: 0.5)

        # Should actually run sandbox tests
        assert attempt.sandbox_result is not None
        assert attempt.status != EvolutionStatus.FAILED

    async def test_sandbox_failure_rejects_attempt(self):
        """Sandbox failure causes rejection."""
        config = EvolutionConfig(sandbox_enabled=True)
        orchestrator = EvolutionOrchestrator(config=config)

        # Code that will fail in sandbox
        code = "import nonexistent_module"
        attempt = await orchestrator.evolve(code)

        assert attempt.status == EvolutionStatus.REJECTED
        assert "import" in attempt.rejection_reason.lower()
```

---

#### R5.3: Validator Security Tests

**Current Gap:** Only tests `eval`, not subprocess bypasses.

**New Tests:**
```python
class TestValidatorSecurityPatterns:
    def test_subprocess_shell_true_direct(self):
        validator = CodeValidator(security_level="high")
        result = validator.validate("subprocess.run('cmd', shell=True)")
        assert not result.security_valid

    def test_subprocess_shell_true_keyword(self):
        validator = CodeValidator(security_level="high")
        result = validator.validate("subprocess.run(cmd, **{'shell': True})")
        assert not result.security_valid

    def test_subprocess_aliased(self):
        validator = CodeValidator(security_level="high")
        result = validator.validate("""
import subprocess as sp
sp.run('cmd', shell=True)
""")
        assert not result.security_valid

    def test_dynamic_import(self):
        validator = CodeValidator(security_level="high")
        result = validator.validate("__import__('os').system('ls')")
        assert not result.security_valid

    def test_importlib_import_module(self):
        validator = CodeValidator(security_level="high")
        result = validator.validate("importlib.import_module('subprocess')")
        assert not result.security_valid
```

---

#### R5.4: Rollback Integrity Tests

**Current Gap:** No tests for persistence load or integrity verification.

**New Tests:**
```python
class TestRollbackIntegrity:
    def test_load_detects_tampered_code(self, tmp_path):
        """Tampered JSON file is rejected."""
        manager = RollbackManager(storage_path=tmp_path, agent_id="test")
        manager.create_snapshot("original code", description="test")

        # Tamper with the stored JSON
        json_path = tmp_path / "test_snapshots.json"
        data = json.loads(json_path.read_text())
        data["snapshots"][0]["code"] = "tampered code"
        # Keep old hash (simulating attack)
        json_path.write_text(json.dumps(data))

        # Load should fail
        manager2 = RollbackManager(storage_path=tmp_path, agent_id="test")
        with pytest.raises(IntegrityError):
            manager2._load_snapshots()

    def test_rollback_verifies_integrity(self, tmp_path):
        """Rollback verifies snapshot before restoring."""
        manager = RollbackManager(storage_path=tmp_path)
        snap1 = manager.create_snapshot("v1")
        snap2 = manager.create_snapshot("v2")

        # Corrupt snap1 in memory (simulating runtime attack)
        manager.snapshots[0].code = "corrupted"

        result = manager.rollback_to_version("v1")
        assert not result.success
        assert "integrity" in result.message.lower()
```

---

### Phase R6: Documentation and Cleanup (LOW)
**Estimated Effort:** 1-2 hours
**Priority:** P3

#### R6.1: Remove Unused strategy_weights

**Problem:** `EvolutionConfig.strategy_weights` is defined but never used.

**Fix:** Either implement weighted selection or remove the field.

---

#### R6.2: Update CLAUDE.md

Document security model, Docker requirements, and configuration options.

---

## Implementation Order

```
Week 1: Critical Blockers (R1)
├── Day 1-2: R1.1 RestrictedPython sandbox implementation
├── Day 2-3: R1.2 Resource limits enforcement
├── Day 3-4: R1.3 Orchestrator integration
└── Day 4: R1.4 Rollback integrity verification

Week 2: Security + State Machine (R2, R3)
├── Day 1-2: R2.1 Expand blocked imports (integrated with R1.1)
├── Day 2-3: R2.2 AST security visitor
├── Day 3: R3.1-R3.2 Fix test_script, TESTING state
└── Day 4: R3.3-R3.4 PENDING_APPROVAL, fitness_fn

Week 3: Quality + Tests (R4, R5)
├── Day 1: R4.1-R4.3 Cleanup sandbox module, output capture, error sanitization
├── Day 2-3: R5.1 RestrictedPython sandbox tests
├── Day 3-4: R5.2-R5.4 Integration, validator, rollback tests
└── Day 4-5: R6 Documentation
```

---

## Success Criteria for Re-Audit

Before requesting Codex re-audit:

1. **All R1 tasks complete** — Critical blockers resolved
2. **All R2 tasks complete** — Security hardened
3. **All R5 tests passing** — Coverage for all fixes
4. **No external dependencies** — Pure Python sandbox

### Re-Audit Checklist

| Area | Requirement | Verification |
|------|-------------|--------------|
| Sandbox | RestrictedPython compilation | Code compiled via `compile_restricted` |
| Sandbox | Dangerous builtins removed | `eval`, `exec`, `open` not available |
| Sandbox | Import whitelist enforced | `import os` raises ImportError |
| Sandbox | Resource limits work | Memory/timeout tests pass |
| Rollback | Integrity verified on load | Tamper test passes |
| Imports | os, subprocess blocked | Validator + sandbox both block |
| AST | Shell=True detected in all forms | All bypass tests pass |
| State | TESTING state used | Trace shows TESTING before VALIDATING |
| State | PENDING_APPROVAL works | Human approval gate enforced |
| Tests | Sandbox isolation tests pass | No mocking of security features |

---

## Decisions Made

| Question | Decision | Rationale |
|----------|----------|-----------|
| Docker vs Pure Python | **Pure Python** | No Docker dependency; RestrictedPython + resource limits |
| Import allowlist mode | **Implement** | `security_mode="strict"` with explicit whitelist |
| Rollback tampering protection | **Hash verification** | Simple, effective; HMAC optional future enhancement |

## Remaining Decisions (Low Priority)

1. **Default security_mode?**
   - Option A: `"standard"` (more permissive, easier debugging)
   - Option B: `"high"` (stricter, recommended for production)
   - **Current plan:** Default to `"high"` with `"standard"` available for testing

2. **Windows support for resource limits?**
   - Option A: Log warning, no enforcement
   - Option B: Use `psutil` for cross-platform limits
   - **Current plan:** Option A; Windows is secondary platform

---

## Appendix: Affected Files

| File | Changes |
|------|---------|
| `sandbox.py` | RestrictedPython execution, resource limits, output capture |
| `rollback.py` | Integrity verification, IntegrityError exception |
| `orchestrator.py` | Fix params, TESTING/PENDING_APPROVAL states |
| `validator.py` | Expanded imports, AST security visitor |
| `test_evolution.py` | RestrictedPython tests, integration tests, security tests |
| `__init__.py` | Export new exceptions |
| `pyproject.toml` | Add RestrictedPython dependency |

---

## New Dependency

```toml
# pyproject.toml
dependencies = [
    # ... existing deps ...
    "RestrictedPython>=7.0",  # NEW: Pure-Python sandbox
]
```

---

*Roadmap prepared in response to Codex audit rejection. Phase 8 blocked until R1-R2 complete and R5 tests passing.*

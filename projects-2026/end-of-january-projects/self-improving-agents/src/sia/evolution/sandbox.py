"""
Sandbox Environment for Code Evolution.

Provides isolated execution environment for testing code mutations safely
using RestrictedPython for pure-Python sandboxing without Docker dependency.

Security Layers:
1. RestrictedPython compilation - blocks dangerous constructs at compile time
2. Custom safe_builtins - removes eval, exec, open, __import__
3. Import whitelist - only allows safe modules
4. Resource limits - memory, CPU, time via resource module (Unix/macOS)
5. Output capture - limits stdout/stderr size
"""

from __future__ import annotations

import ast
import io
import logging
import re
import resource
import signal
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import UUID, uuid4

from RestrictedPython import compile_restricted, safe_builtins
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr

logger = logging.getLogger(__name__)


# ============================================================================
# Safe Imports Whitelist
# ============================================================================

# Modules safe for sandboxed code to import
SAFE_IMPORTS_STRICT = frozenset({
    # Math & numbers
    "math", "statistics", "decimal", "fractions", "cmath",
    # Data structures
    "collections", "itertools", "functools", "operator", "heapq", "bisect",
    # Text processing
    "string", "re", "textwrap", "unicodedata",
    # Data formats (parsing only)
    "json", "csv", "base64", "binascii",
    # Time (read-only)
    "datetime", "time", "calendar", "zoneinfo",
    # Typing & structure
    "typing", "typing_extensions", "dataclasses", "enum", "abc",
    # Safe utilities
    "copy", "pprint", "warnings", "contextlib",
    # Numbers
    "numbers", "random",
})

# Additional imports allowed in standard security mode
SAFE_IMPORTS_STANDARD = SAFE_IMPORTS_STRICT | frozenset({
    "logging",
    "hashlib",
    "hmac",
    "secrets",
    "uuid",
    "struct",
    "array",
})

# Dangerous modules - never allowed
BLOCKED_IMPORTS = frozenset({
    # System access
    "os", "sys", "subprocess", "shutil", "pathlib", "glob", "tempfile",
    # Code execution
    "importlib", "builtins", "code", "codeop", "compile", "ast",
    # Dangerous serialization
    "pickle", "cPickle", "dill", "marshal", "shelve",
    # Network
    "socket", "http", "urllib", "requests", "httpx", "aiohttp",
    "ftplib", "smtplib", "telnetlib", "paramiko", "fabric",
    # Process/threading
    "multiprocessing", "threading", "concurrent", "asyncio",
    "_thread", "queue",
    # Low-level
    "ctypes", "cffi", "mmap", "gc", "inspect", "traceback",
    # Signals
    "signal", "atexit",
    # I/O
    "io", "fcntl", "select", "selectors",
})


# ============================================================================
# Sandbox Configuration
# ============================================================================


@dataclass
class SandboxConfig:
    """Configuration for sandbox environment."""

    # Resource limits
    max_memory_mb: int = 256
    timeout_seconds: int = 30
    max_output_size: int = 100_000  # 100KB output limit

    # Security settings
    security_mode: str = "high"  # "standard", "high", "strict"
    custom_allowed_imports: set[str] | None = None

    # Execution settings
    enable_print: bool = True
    enable_getattr: bool = False  # Dangerous - disabled by default
    enable_getitem: bool = True

    def get_allowed_imports(self) -> frozenset[str]:
        """Get allowed imports based on security mode."""
        if self.custom_allowed_imports is not None:
            return frozenset(self.custom_allowed_imports) - BLOCKED_IMPORTS

        if self.security_mode == "strict":
            return SAFE_IMPORTS_STRICT
        elif self.security_mode == "standard":
            return SAFE_IMPORTS_STANDARD
        else:  # high (default)
            return SAFE_IMPORTS_STRICT


@dataclass
class SandboxResult:
    """Result of sandbox execution."""

    id: UUID = field(default_factory=uuid4)

    # Execution info
    success: bool = False
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""

    # Metrics
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0

    # Test results (if running tests)
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    test_output: str = ""

    # Error info
    error: str | None = None
    error_type: str | None = None
    timed_out: bool = False
    memory_exceeded: bool = False
    output_truncated: bool = False

    # Security info
    compilation_errors: list[str] = field(default_factory=list)
    blocked_imports: list[str] = field(default_factory=list)

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


# ============================================================================
# Exceptions
# ============================================================================


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class SandboxSecurityError(SandboxError):
    """Security violation in sandbox."""
    pass


class SandboxTimeoutError(SandboxError):
    """Execution timeout in sandbox."""
    pass


class SandboxMemoryError(SandboxError):
    """Memory limit exceeded in sandbox."""
    pass


class SandboxImportError(SandboxError):
    """Blocked import attempted in sandbox."""
    pass


# ============================================================================
# Output Capture
# ============================================================================


class OutputCapture:
    """Capture and limit output from sandboxed code."""

    def __init__(self, max_size: int = 100_000):
        self.max_size = max_size
        self.buffer = io.StringIO()
        self.truncated = False
        self._current_size = 0

    def write(self, text: str) -> int:
        """Write text to buffer, respecting size limit."""
        if self._current_size >= self.max_size:
            self.truncated = True
            return 0

        allowed = min(len(text), self.max_size - self._current_size)
        self.buffer.write(text[:allowed])
        self._current_size += allowed

        if allowed < len(text):
            self.truncated = True
            self.buffer.write("\n[OUTPUT TRUNCATED]")

        return allowed

    def getvalue(self) -> str:
        """Get captured output."""
        return self.buffer.getvalue()

    def flush(self) -> None:
        """Flush buffer (no-op for StringIO)."""
        pass


# ============================================================================
# Resource Limiter
# ============================================================================


class ResourceLimiter:
    """Enforce resource limits on code execution (Unix/macOS only)."""

    def __init__(self, config: SandboxConfig):
        self.config = config
        self._old_limits: dict[str, tuple[int, int]] = {}
        self._old_handler: Any = None
        self._is_unix = sys.platform != "win32"

    @contextmanager
    def enforce_limits(self):
        """Context manager to enforce resource limits."""
        if not self._is_unix:
            logger.warning("Resource limits not enforced on Windows")
            yield
            return

        try:
            self._set_limits()
            yield
        finally:
            self._restore_limits()

    def _set_limits(self) -> None:
        """Set resource limits."""
        # Memory limit (address space)
        mem_bytes = self.config.max_memory_mb * 1024 * 1024
        try:
            self._old_limits["AS"] = resource.getrlimit(resource.RLIMIT_AS)
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except (ValueError, resource.error) as e:
            logger.warning(f"Could not set memory limit: {e}")

        # CPU time limit (as backup for timeout)
        cpu_seconds = self.config.timeout_seconds + 5
        try:
            self._old_limits["CPU"] = resource.getrlimit(resource.RLIMIT_CPU)
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        except (ValueError, resource.error) as e:
            logger.warning(f"Could not set CPU limit: {e}")

        # Set up signal-based timeout
        def timeout_handler(signum, frame):
            raise SandboxTimeoutError(
                f"Execution timed out after {self.config.timeout_seconds}s"
            )

        self._old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.config.timeout_seconds)

    def _restore_limits(self) -> None:
        """Restore original limits."""
        # Cancel alarm
        signal.alarm(0)

        # Restore signal handler
        if self._old_handler is not None:
            signal.signal(signal.SIGALRM, self._old_handler)

        # Restore resource limits
        for name, limit in self._old_limits.items():
            try:
                resource.setrlimit(getattr(resource, f"RLIMIT_{name}"), limit)
            except (ValueError, resource.error):
                pass

        self._old_limits.clear()


# ============================================================================
# Import Guard
# ============================================================================


class ImportGuard:
    """Guard for controlling imports in sandboxed code."""

    def __init__(self, allowed_imports: frozenset[str]):
        self.allowed_imports = allowed_imports
        self.blocked_attempts: list[str] = []

    def __call__(self, name: str, globals_dict=None, locals_dict=None,
                 fromlist=(), level=0):
        """Guarded import function."""
        # Get base module name
        base_module = name.split(".")[0]

        # Check against blocklist first (always blocked)
        if base_module in BLOCKED_IMPORTS:
            self.blocked_attempts.append(name)
            raise SandboxImportError(
                f"Import of '{name}' is blocked for security reasons"
            )

        # Check against allowlist
        if base_module not in self.allowed_imports:
            self.blocked_attempts.append(name)
            raise SandboxImportError(
                f"Import of '{name}' is not in the allowed list. "
                f"Allowed: {sorted(self.allowed_imports)[:10]}..."
            )

        # Perform actual import
        return __builtins__["__import__"](name, globals_dict, locals_dict,
                                          fromlist, level)


# ============================================================================
# Print Guard
# ============================================================================


def create_print_guard(output: OutputCapture) -> Callable:
    """Create a guarded print function that writes to OutputCapture."""

    def guarded_print(*args, **kwargs):
        """Print to captured output with size limits."""
        # Get file argument, default to our capture
        file = kwargs.pop("file", None)
        if file is not None and file is not output:
            # Trying to print to a different file - not allowed
            raise SandboxSecurityError("Cannot print to external files")

        # Format output
        sep = kwargs.get("sep", " ")
        end = kwargs.get("end", "\n")
        text = sep.join(str(arg) for arg in args) + end

        output.write(text)

    return guarded_print


# ============================================================================
# Restricted Sandbox
# ============================================================================


class RestrictedSandbox:
    """
    Pure-Python sandbox using RestrictedPython.

    Provides isolation through:
    1. Compile-time restrictions (RestrictedPython)
    2. Custom safe builtins
    3. Import whitelist
    4. Resource limits (memory, CPU, time)
    5. Output capture with size limits
    """

    def __init__(self, config: SandboxConfig | None = None):
        """
        Initialize restricted sandbox.

        Args:
            config: Sandbox configuration
        """
        self.config = config or SandboxConfig()
        self.sandbox_id = uuid4()
        self._output = OutputCapture(self.config.max_output_size)
        self._import_guard = ImportGuard(self.config.get_allowed_imports())
        self._resource_limiter = ResourceLimiter(self.config)

    def _get_safe_builtins(self) -> dict[str, Any]:
        """Create safe builtins dictionary."""
        # Start with RestrictedPython's safe builtins
        builtins = dict(safe_builtins)

        # Remove potentially dangerous builtins
        dangerous = {
            "compile", "eval", "exec", "open", "input",
            "__import__", "globals", "locals", "vars",
            "getattr", "setattr", "delattr", "hasattr",
            "type", "object", "__build_class__",
        }
        for name in dangerous:
            builtins.pop(name, None)

        # Add our guarded import
        builtins["__import__"] = self._import_guard

        # Add safe type for isinstance checks
        builtins["isinstance"] = isinstance
        builtins["issubclass"] = issubclass
        builtins["len"] = len
        builtins["range"] = range
        builtins["enumerate"] = enumerate
        builtins["zip"] = zip
        builtins["map"] = map
        builtins["filter"] = filter
        builtins["sorted"] = sorted
        builtins["reversed"] = reversed
        builtins["min"] = min
        builtins["max"] = max
        builtins["sum"] = sum
        builtins["abs"] = abs
        builtins["round"] = round
        builtins["pow"] = pow
        builtins["divmod"] = divmod
        builtins["all"] = all
        builtins["any"] = any
        builtins["repr"] = repr
        builtins["str"] = str
        builtins["int"] = int
        builtins["float"] = float
        builtins["bool"] = bool
        builtins["list"] = list
        builtins["tuple"] = tuple
        builtins["dict"] = dict
        builtins["set"] = set
        builtins["frozenset"] = frozenset
        builtins["bytes"] = bytes
        builtins["bytearray"] = bytearray
        builtins["slice"] = slice
        builtins["complex"] = complex
        builtins["ord"] = ord
        builtins["chr"] = chr
        builtins["hex"] = hex
        builtins["oct"] = oct
        builtins["bin"] = bin
        builtins["format"] = format
        builtins["hash"] = hash
        builtins["id"] = id
        builtins["callable"] = callable
        builtins["iter"] = iter
        builtins["next"] = next
        builtins["Exception"] = Exception
        builtins["ValueError"] = ValueError
        builtins["TypeError"] = TypeError
        builtins["KeyError"] = KeyError
        builtins["IndexError"] = IndexError
        builtins["AttributeError"] = AttributeError
        builtins["RuntimeError"] = RuntimeError
        builtins["StopIteration"] = StopIteration
        builtins["None"] = None
        builtins["True"] = True
        builtins["False"] = False
        builtins["NotImplemented"] = NotImplemented
        builtins["Ellipsis"] = ...

        return builtins

    def _get_restricted_globals(self) -> dict[str, Any]:
        """Create restricted globals for execution."""
        globals_dict = {
            "__builtins__": self._get_safe_builtins(),
            "__name__": "__sandbox__",
            "__doc__": None,
            "_getiter_": default_guarded_getiter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        }

        # Conditionally add guards
        if self.config.enable_getitem:
            globals_dict["_getitem_"] = default_guarded_getitem

        if self.config.enable_getattr:
            globals_dict["_getattr_"] = safer_getattr
        else:
            # Block all getattr access
            def blocked_getattr(obj, name):
                raise SandboxSecurityError(
                    f"Attribute access is disabled in this sandbox"
                )
            globals_dict["_getattr_"] = blocked_getattr

        if self.config.enable_print:
            globals_dict["_print_"] = create_print_guard(self._output)
            globals_dict["_getattr_"] = safer_getattr  # Needed for print

        return globals_dict

    def _sanitize_error(self, error: str) -> str:
        """Remove potentially sensitive information from error messages."""
        # Remove absolute paths (Unix-style)
        error = re.sub(r'/Users/[^/\s]+/', '/home/user/', error)
        error = re.sub(r'/home/[^/\s]+/', '/home/user/', error)

        # Remove Windows paths (if present)
        # Note: Use double backslash in pattern and replacement
        error = re.sub(r'C:\\\\Users\\\\[^\\\\s]+\\\\', 'C:\\\\Users\\\\user\\\\', error)

        # Remove full tracebacks with file paths
        error = re.sub(r'File "[^"]+",', 'File "<sandbox>",', error)

        return error

    async def execute(self, code: str) -> SandboxResult:
        """
        Execute code in restricted environment.

        Args:
            code: Python code to execute

        Returns:
            SandboxResult with execution details
        """
        result = SandboxResult(id=self.sandbox_id)
        result.started_at = datetime.now()

        # Reset output capture
        self._output = OutputCapture(self.config.max_output_size)
        self._import_guard.blocked_attempts.clear()

        try:
            # 1. Compile with RestrictedPython
            try:
                byte_code = compile_restricted(
                    code,
                    filename="<sandbox>",
                    mode="exec",
                )

                # Check for compilation errors
                if byte_code.errors:
                    result.compilation_errors = list(byte_code.errors)
                    result.error = f"Compilation errors: {byte_code.errors}"
                    result.error_type = "CompilationError"
                    return result

                if byte_code.code is None:
                    result.error = "Compilation produced no code"
                    result.error_type = "CompilationError"
                    return result

            except SyntaxError as e:
                result.error = self._sanitize_error(f"Syntax error: {e}")
                result.error_type = "SyntaxError"
                return result

            # 2. Prepare execution environment
            restricted_globals = self._get_restricted_globals()
            restricted_locals: dict[str, Any] = {}

            # 3. Execute with resource limits
            start_time = time.perf_counter()

            try:
                with self._resource_limiter.enforce_limits():
                    exec(byte_code.code, restricted_globals, restricted_locals)

                result.success = True
                result.exit_code = 0

            except SandboxTimeoutError as e:
                result.timed_out = True
                result.error = str(e)
                result.error_type = "TimeoutError"

            except MemoryError as e:
                result.memory_exceeded = True
                result.error = "Memory limit exceeded"
                result.error_type = "MemoryError"

            except SandboxImportError as e:
                result.error = str(e)
                result.error_type = "ImportError"
                result.blocked_imports = list(self._import_guard.blocked_attempts)

            except SandboxSecurityError as e:
                result.error = str(e)
                result.error_type = "SecurityError"

            except Exception as e:
                result.error = self._sanitize_error(str(e))
                result.error_type = type(e).__name__

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

        except Exception as e:
            result.error = self._sanitize_error(f"Sandbox error: {e}")
            result.error_type = "SandboxError"

        finally:
            result.completed_at = datetime.now()
            result.stdout = self._output.getvalue()
            result.output_truncated = self._output.truncated
            result.blocked_imports = list(self._import_guard.blocked_attempts)

        return result

    async def validate_syntax(self, code: str) -> SandboxResult:
        """
        Validate Python syntax without executing.

        Args:
            code: Python code to validate

        Returns:
            SandboxResult with validation result
        """
        result = SandboxResult(id=uuid4())
        result.started_at = datetime.now()

        try:
            # First check standard Python syntax
            ast.parse(code)

            # Then check RestrictedPython compilation
            byte_code = compile_restricted(code, "<sandbox>", "exec")

            # compile_restricted returns different types:
            # - On error: CompileResult with .errors attribute
            # - On success: code object (no .errors attribute)
            if hasattr(byte_code, "errors") and byte_code.errors:
                result.compilation_errors = list(byte_code.errors)
                result.error = f"RestrictedPython errors: {byte_code.errors}"
                result.success = False
            else:
                result.success = True
                result.stdout = "Syntax valid"

        except SyntaxError as e:
            result.error = self._sanitize_error(f"Syntax error: {e}")
            result.error_type = "SyntaxError"
            result.success = False

        result.completed_at = datetime.now()
        return result

    async def create(self) -> None:
        """
        Initialize sandbox (no-op for RestrictedSandbox).

        Kept for backwards compatibility with old API.
        RestrictedSandbox is stateless and doesn't need initialization.
        """
        pass

    async def cleanup(self) -> None:
        """
        Clean up sandbox resources (no-op for RestrictedSandbox).

        Kept for backwards compatibility with old API.
        RestrictedSandbox has no external resources to clean up.
        """
        pass

    async def check_imports(self, code: str) -> SandboxResult:
        """
        Check if all imports in code are allowed.

        Args:
            code: Python code to check

        Returns:
            SandboxResult with import check results
        """
        result = SandboxResult(id=uuid4())
        result.started_at = datetime.now()

        try:
            tree = ast.parse(code)
            blocked = []
            allowed_imports = self.config.get_allowed_imports()

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        base = alias.name.split(".")[0]
                        if base in BLOCKED_IMPORTS or base not in allowed_imports:
                            blocked.append(alias.name)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        base = node.module.split(".")[0]
                        if base in BLOCKED_IMPORTS or base not in allowed_imports:
                            blocked.append(node.module)

            if blocked:
                result.blocked_imports = blocked
                result.error = f"Blocked imports: {', '.join(blocked)}"
                result.success = False
            else:
                result.success = True
                result.stdout = "All imports allowed"

        except SyntaxError as e:
            result.error = f"Syntax error: {e}"
            result.success = False

        result.completed_at = datetime.now()
        return result


# ============================================================================
# Backwards Compatibility Aliases
# ============================================================================

# Alias for backwards compatibility with existing code
Sandbox = RestrictedSandbox


class SandboxPool:
    """
    Pool of reusable sandboxes for concurrent testing.

    Note: RestrictedSandbox is lightweight and doesn't need pooling,
    but this class is kept for API compatibility.
    """

    def __init__(
        self,
        size: int = 4,
        config: SandboxConfig | None = None,
    ):
        """
        Initialize sandbox pool.

        Args:
            size: Number of sandboxes in pool (ignored - sandboxes are lightweight)
            config: Shared configuration for sandboxes
        """
        self.size = size
        self.config = config or SandboxConfig()

    async def initialize(self) -> None:
        """Initialize pool (no-op for RestrictedSandbox)."""
        pass

    async def acquire(self) -> RestrictedSandbox:
        """
        Acquire a sandbox from the pool.

        Returns:
            New RestrictedSandbox instance
        """
        return RestrictedSandbox(self.config)

    async def release(self, sandbox: RestrictedSandbox) -> None:
        """
        Release a sandbox back to the pool.

        Args:
            sandbox: Sandbox to release (no-op for RestrictedSandbox)
        """
        pass

    async def cleanup(self) -> None:
        """Clean up all sandboxes in the pool (no-op for RestrictedSandbox)."""
        pass


class SandboxManager:
    """
    High-level manager for sandbox operations.
    """

    def __init__(self, config: SandboxConfig | None = None):
        """
        Initialize sandbox manager.

        Args:
            config: Default sandbox configuration
        """
        self.config = config or SandboxConfig()

    async def test_code(
        self,
        code: str,
        test_code: str | None = None,
        config: SandboxConfig | None = None,
    ) -> SandboxResult:
        """
        Test code in an isolated sandbox.

        Args:
            code: Code to test
            test_code: Optional test code (executed after main code)
            config: Override configuration

        Returns:
            SandboxResult with test results
        """
        sandbox_config = config or self.config
        sandbox = RestrictedSandbox(sandbox_config)

        # Validate syntax first
        syntax_result = await sandbox.validate_syntax(code)
        if not syntax_result.success:
            return syntax_result

        # Check imports
        import_result = await sandbox.check_imports(code)
        if not import_result.success:
            return import_result

        # Execute main code
        if test_code:
            # Combine code and test code
            combined = f"{code}\n\n# Test code\n{test_code}"
            return await sandbox.execute(combined)
        else:
            return await sandbox.execute(code)

    async def validate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_code: str | None = None,
    ) -> tuple[bool, SandboxResult]:
        """
        Validate a code mutation is safe and functional.

        Args:
            original_code: Original code (unused, kept for API compatibility)
            mutated_code: Mutated code to validate
            test_code: Test code to verify behavior

        Returns:
            Tuple of (is_valid, result)
        """
        sandbox = RestrictedSandbox(self.config)

        # Validate syntax
        syntax_result = await sandbox.validate_syntax(mutated_code)
        if not syntax_result.success:
            return False, syntax_result

        # Check imports
        import_result = await sandbox.check_imports(mutated_code)
        if not import_result.success:
            return False, import_result

        # Execute
        if test_code:
            combined = f"{mutated_code}\n\n# Test code\n{test_code}"
            result = await sandbox.execute(combined)
        else:
            result = await sandbox.execute(mutated_code)

        return result.success, result

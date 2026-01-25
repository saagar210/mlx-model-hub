"""
Sandbox Environment for Code Evolution.

Provides isolated execution environment for testing code mutations safely.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4


# ============================================================================
# Sandbox Configuration
# ============================================================================


@dataclass
class SandboxConfig:
    """Configuration for sandbox environment."""

    # Resource limits
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    timeout_seconds: int = 60

    # Network settings
    network_enabled: bool = False

    # Filesystem settings
    max_disk_mb: int = 100
    read_only_root: bool = True

    # Process settings
    max_processes: int = 10

    # Docker settings (if using Docker)
    use_docker: bool = False
    docker_image: str = "python:3.12-slim"

    # Python environment
    python_path: str = "python"
    venv_path: str | None = None

    # Cleanup
    auto_cleanup: bool = True


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
    cpu_time_ms: float = 0.0

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

    # Timestamps
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None


# ============================================================================
# Sandbox Base Class
# ============================================================================


class Sandbox:
    """
    Isolated execution environment for testing code mutations.

    Supports both subprocess-based and Docker-based isolation.
    """

    def __init__(self, config: SandboxConfig | None = None):
        """
        Initialize sandbox.

        Args:
            config: Sandbox configuration
        """
        self.config = config or SandboxConfig()
        self.sandbox_id = uuid4()
        self.temp_dir: Path | None = None
        self._created = False

    async def __aenter__(self) -> "Sandbox":
        """Async context manager entry."""
        await self.create()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.cleanup()

    async def create(self) -> None:
        """Create the sandbox environment."""
        if self._created:
            return

        # Create temporary directory
        self.temp_dir = Path(tempfile.mkdtemp(prefix=f"sia_sandbox_{self.sandbox_id}_"))

        # Create subdirectories
        (self.temp_dir / "code").mkdir()
        (self.temp_dir / "data").mkdir()
        (self.temp_dir / "output").mkdir()

        self._created = True

    async def cleanup(self) -> None:
        """Clean up the sandbox environment."""
        if not self._created or not self.config.auto_cleanup:
            return

        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

        self._created = False
        self.temp_dir = None

    def write_code(self, code: str, filename: str = "module.py") -> Path:
        """
        Write code to the sandbox.

        Args:
            code: Python code to write
            filename: Name of the file

        Returns:
            Path to the written file
        """
        if not self.temp_dir:
            raise RuntimeError("Sandbox not created")

        code_path = self.temp_dir / "code" / filename
        code_path.write_text(code)
        return code_path

    def write_test(self, test_code: str, filename: str = "test_module.py") -> Path:
        """
        Write test code to the sandbox.

        Args:
            test_code: Test code to write
            filename: Name of the test file

        Returns:
            Path to the written file
        """
        if not self.temp_dir:
            raise RuntimeError("Sandbox not created")

        test_path = self.temp_dir / "code" / filename
        test_path.write_text(test_code)
        return test_path

    async def execute(
        self,
        code: str | None = None,
        script: str | None = None,
        args: list[str] | None = None,
    ) -> SandboxResult:
        """
        Execute code in the sandbox.

        Args:
            code: Python code to execute directly
            script: Path to script file to execute
            args: Additional command line arguments

        Returns:
            SandboxResult with execution details
        """
        if self.config.use_docker:
            return await self._execute_docker(code, script, args)
        else:
            return await self._execute_subprocess(code, script, args)

    async def _execute_subprocess(
        self,
        code: str | None = None,
        script: str | None = None,
        args: list[str] | None = None,
    ) -> SandboxResult:
        """Execute using subprocess with resource limits."""
        result = SandboxResult()

        if not self.temp_dir:
            result.error = "Sandbox not created"
            return result

        try:
            # Prepare command
            cmd = [self.config.python_path]

            if code:
                # Write code to temp file and execute
                code_path = self.write_code(code, "_exec.py")
                cmd.append(str(code_path))
            elif script:
                cmd.append(script)
            else:
                result.error = "No code or script provided"
                return result

            if args:
                cmd.extend(args)

            # Set up environment
            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.temp_dir / "code")

            # Disable network if configured
            if not self.config.network_enabled:
                env["no_proxy"] = "*"
                env["NO_PROXY"] = "*"

            # Execute with timeout
            start_time = time.perf_counter()

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(self.temp_dir / "code"),
                    env=env,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.config.timeout_seconds,
                    )
                    result.exit_code = process.returncode
                    result.stdout = stdout.decode("utf-8", errors="replace")
                    result.stderr = stderr.decode("utf-8", errors="replace")
                    result.success = process.returncode == 0

                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    result.timed_out = True
                    result.error = f"Execution timed out after {self.config.timeout_seconds}s"

            except Exception as e:
                result.error = str(e)
                result.error_type = type(e).__name__

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            result.completed_at = datetime.now()

        except Exception as e:
            result.error = str(e)
            result.error_type = type(e).__name__

        return result

    async def _execute_docker(
        self,
        code: str | None = None,
        script: str | None = None,
        args: list[str] | None = None,
    ) -> SandboxResult:
        """Execute using Docker container for stronger isolation."""
        result = SandboxResult()

        if not self.temp_dir:
            result.error = "Sandbox not created"
            return result

        try:
            # Write code if provided
            if code:
                self.write_code(code, "_exec.py")
                script = "/sandbox/code/_exec.py"

            # Build docker command
            docker_cmd = [
                "docker", "run",
                "--rm",
                f"--memory={self.config.max_memory_mb}m",
                f"--cpus={self.config.max_cpu_percent / 100}",
                "--pids-limit", str(self.config.max_processes),
                "-v", f"{self.temp_dir}:/sandbox:ro",
                "-w", "/sandbox/code",
            ]

            # Network isolation
            if not self.config.network_enabled:
                docker_cmd.extend(["--network", "none"])

            # Read-only root filesystem
            if self.config.read_only_root:
                docker_cmd.append("--read-only")
                docker_cmd.extend(["--tmpfs", "/tmp:size=50m"])

            docker_cmd.extend([
                self.config.docker_image,
                "python", script or "/sandbox/code/module.py",
            ])

            if args:
                docker_cmd.extend(args)

            # Execute
            start_time = time.perf_counter()

            try:
                process = await asyncio.create_subprocess_exec(
                    *docker_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=self.config.timeout_seconds,
                    )
                    result.exit_code = process.returncode
                    result.stdout = stdout.decode("utf-8", errors="replace")
                    result.stderr = stderr.decode("utf-8", errors="replace")
                    result.success = process.returncode == 0

                except asyncio.TimeoutError:
                    # Kill docker container
                    subprocess.run(
                        ["docker", "kill", f"sia_sandbox_{self.sandbox_id}"],
                        capture_output=True,
                    )
                    result.timed_out = True
                    result.error = f"Execution timed out after {self.config.timeout_seconds}s"

            except Exception as e:
                result.error = str(e)
                result.error_type = type(e).__name__

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            result.completed_at = datetime.now()

        except Exception as e:
            result.error = str(e)
            result.error_type = type(e).__name__

        return result

    async def run_tests(
        self,
        test_pattern: str = "test_*.py",
        pytest_args: list[str] | None = None,
    ) -> SandboxResult:
        """
        Run pytest tests in the sandbox.

        Args:
            test_pattern: Pattern for test files
            pytest_args: Additional pytest arguments

        Returns:
            SandboxResult with test results
        """
        if not self.temp_dir:
            return SandboxResult(error="Sandbox not created")

        # Build pytest command
        args = ["-v", "--tb=short"]
        if pytest_args:
            args.extend(pytest_args)

        # Run pytest as module
        code = f"""
import sys
import pytest

# Run tests
exit_code = pytest.main({args!r} + ['{self.temp_dir / "code"}'])
sys.exit(exit_code)
"""

        result = await self.execute(code=code)

        # Parse test results from output
        if result.stdout:
            result.test_output = result.stdout

            # Try to extract test counts
            for line in result.stdout.split("\n"):
                if "passed" in line or "failed" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "passed" and i > 0:
                            try:
                                result.tests_passed = int(parts[i - 1])
                            except ValueError:
                                pass
                        elif part == "failed" and i > 0:
                            try:
                                result.tests_failed = int(parts[i - 1])
                            except ValueError:
                                pass

            result.tests_run = result.tests_passed + result.tests_failed

        return result

    async def validate_syntax(self, code: str) -> SandboxResult:
        """
        Validate Python syntax in the sandbox.

        Args:
            code: Python code to validate

        Returns:
            SandboxResult indicating if syntax is valid
        """
        validation_code = f"""
import ast
import sys

code = '''{code.replace("'''", "\\'\\'\\'")}'''

try:
    ast.parse(code)
    print("VALID")
    sys.exit(0)
except SyntaxError as e:
    print(f"SYNTAX_ERROR: {{e}}")
    sys.exit(1)
"""

        result = await self.execute(code=validation_code)
        result.success = "VALID" in result.stdout
        return result

    async def check_imports(self, code: str) -> SandboxResult:
        """
        Check if all imports in code are available.

        Args:
            code: Python code to check

        Returns:
            SandboxResult with import check results
        """
        check_code = f"""
import ast
import sys
import importlib

code = '''{code.replace("'''", "\\'\\'\\'")}'''

tree = ast.parse(code)
missing = []

for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            try:
                importlib.import_module(alias.name.split('.')[0])
            except ImportError:
                missing.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            try:
                importlib.import_module(node.module.split('.')[0])
            except ImportError:
                missing.append(node.module)

if missing:
    print(f"MISSING: {{', '.join(missing)}}")
    sys.exit(1)
else:
    print("ALL_IMPORTS_OK")
    sys.exit(0)
"""

        result = await self.execute(code=check_code)
        result.success = "ALL_IMPORTS_OK" in result.stdout
        return result


# ============================================================================
# Sandbox Pool
# ============================================================================


class SandboxPool:
    """
    Pool of reusable sandboxes for concurrent testing.
    """

    def __init__(
        self,
        size: int = 4,
        config: SandboxConfig | None = None,
    ):
        """
        Initialize sandbox pool.

        Args:
            size: Number of sandboxes in pool
            config: Shared configuration for sandboxes
        """
        self.size = size
        self.config = config or SandboxConfig()
        self._sandboxes: list[Sandbox] = []
        self._available: asyncio.Queue[Sandbox] = asyncio.Queue()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all sandboxes in the pool."""
        if self._initialized:
            return

        for _ in range(self.size):
            sandbox = Sandbox(self.config)
            await sandbox.create()
            self._sandboxes.append(sandbox)
            await self._available.put(sandbox)

        self._initialized = True

    async def acquire(self) -> Sandbox:
        """
        Acquire a sandbox from the pool.

        Returns:
            Available sandbox
        """
        if not self._initialized:
            await self.initialize()

        return await self._available.get()

    async def release(self, sandbox: Sandbox) -> None:
        """
        Release a sandbox back to the pool.

        Args:
            sandbox: Sandbox to release
        """
        # Clean up sandbox state
        if sandbox.temp_dir:
            # Clear code directory
            code_dir = sandbox.temp_dir / "code"
            if code_dir.exists():
                for f in code_dir.iterdir():
                    f.unlink()

        await self._available.put(sandbox)

    async def cleanup(self) -> None:
        """Clean up all sandboxes in the pool."""
        for sandbox in self._sandboxes:
            await sandbox.cleanup()

        self._sandboxes.clear()
        self._initialized = False


# ============================================================================
# Sandbox Manager
# ============================================================================


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
        self._pool: SandboxPool | None = None

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
            test_code: Optional test code
            config: Override configuration

        Returns:
            SandboxResult with test results
        """
        sandbox_config = config or self.config

        async with Sandbox(sandbox_config) as sandbox:
            # Write main code
            sandbox.write_code(code, "module.py")

            if test_code:
                # Write and run tests
                sandbox.write_test(test_code, "test_module.py")
                return await sandbox.run_tests()
            else:
                # Just validate and run
                syntax_result = await sandbox.validate_syntax(code)
                if not syntax_result.success:
                    return syntax_result

                # Try to import and run
                return await sandbox.execute(code=code)

    async def validate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_code: str | None = None,
    ) -> tuple[bool, SandboxResult]:
        """
        Validate a code mutation is safe and functional.

        Args:
            original_code: Original code
            mutated_code: Mutated code
            test_code: Test code to verify behavior

        Returns:
            Tuple of (is_valid, result)
        """
        async with Sandbox(self.config) as sandbox:
            # First validate syntax
            syntax_result = await sandbox.validate_syntax(mutated_code)
            if not syntax_result.success:
                return False, syntax_result

            # Check imports
            import_result = await sandbox.check_imports(mutated_code)
            if not import_result.success:
                return False, import_result

            # Run tests if provided
            if test_code:
                sandbox.write_code(mutated_code, "module.py")
                sandbox.write_test(test_code, "test_module.py")
                test_result = await sandbox.run_tests()

                return test_result.success, test_result

            # Basic execution check
            exec_result = await sandbox.execute(code=mutated_code)
            return exec_result.success, exec_result

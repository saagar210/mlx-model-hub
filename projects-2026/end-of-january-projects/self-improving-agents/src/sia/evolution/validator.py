"""
Code Validator.

Validates mutated code for syntax, types, and security.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidationIssue:
    """A single validation issue."""

    severity: str  # 'error', 'warning', 'info'
    category: str  # 'syntax', 'type', 'security', 'style', 'import'
    message: str
    line: int | None = None
    column: int | None = None
    code: str | None = None  # Error code like E501, B303
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of code validation."""

    valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    syntax_valid: bool = True
    types_valid: bool = True
    security_valid: bool = True
    imports_valid: bool = True

    # Scores
    syntax_score: float = 1.0
    type_score: float = 1.0
    security_score: float = 1.0
    overall_score: float = 1.0

    # Details
    error_count: int = 0
    warning_count: int = 0

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a validation issue."""
        self.issues.append(issue)
        if issue.severity == "error":
            self.error_count += 1
            self.valid = False
            if issue.category == "syntax":
                self.syntax_valid = False
            elif issue.category == "type":
                self.types_valid = False
            elif issue.category == "security":
                self.security_valid = False
            elif issue.category == "import":
                self.imports_valid = False
        elif issue.severity == "warning":
            self.warning_count += 1

    def calculate_scores(self) -> None:
        """Calculate validation scores."""
        syntax_errors = sum(
            1 for i in self.issues
            if i.category == "syntax" and i.severity == "error"
        )
        type_errors = sum(
            1 for i in self.issues
            if i.category == "type" and i.severity == "error"
        )
        security_errors = sum(
            1 for i in self.issues
            if i.category == "security" and i.severity in ("error", "warning")
        )

        self.syntax_score = 1.0 if syntax_errors == 0 else 0.0
        self.type_score = max(0.0, 1.0 - (type_errors * 0.2))
        self.security_score = max(0.0, 1.0 - (security_errors * 0.3))

        self.overall_score = (
            self.syntax_score * 0.4 +
            self.type_score * 0.3 +
            self.security_score * 0.3
        )


# Dangerous patterns for security checking
DANGEROUS_PATTERNS = [
    # Code execution
    (r"\beval\s*\(", "eval() can execute arbitrary code"),
    (r"\bexec\s*\(", "exec() can execute arbitrary code"),
    (r"\bcompile\s*\(", "compile() can be used to execute arbitrary code"),

    # System commands
    (r"\bos\.system\s*\(", "os.system() can execute shell commands"),
    (r"\bos\.popen\s*\(", "os.popen() can execute shell commands"),
    (r"\bos\.spawn", "os.spawn*() can execute programs"),
    (r"\bsubprocess\.call\s*\([^,]+shell\s*=\s*True",
     "subprocess with shell=True is dangerous"),
    (r"\bsubprocess\.run\s*\([^,]+shell\s*=\s*True",
     "subprocess with shell=True is dangerous"),
    (r"\bsubprocess\.Popen\s*\([^,]+shell\s*=\s*True",
     "subprocess with shell=True is dangerous"),

    # File operations with user input (heuristic)
    (r"open\s*\([^)]*\+[^)]*\)", "File opened in write mode - review carefully"),

    # Pickle (deserialization attacks)
    (r"\bpickle\.loads?\s*\(", "pickle can execute arbitrary code during deserialization"),
    (r"\bcPickle\.loads?\s*\(", "cPickle can execute arbitrary code during deserialization"),

    # YAML unsafe load
    (r"\byaml\.load\s*\([^,)]+\)", "yaml.load() without Loader is unsafe"),

    # SQL injection patterns
    (r"execute\s*\([^)]*%[^)]*\)", "Possible SQL injection (string formatting)"),
    (r"execute\s*\([^)]*\.format\s*\(", "Possible SQL injection (string formatting)"),
    (r'execute\s*\([^)]*f"[^)]*\)', "Possible SQL injection (f-string)"),
    (r"execute\s*\([^)]*f'[^)]*\)", "Possible SQL injection (f-string)"),

    # Network with hardcoded credentials
    (r"(password|passwd|secret|api_key|apikey)\s*=\s*[\"'][^\"']+[\"']",
     "Possible hardcoded credential"),

    # Import __builtins__
    (r"__builtins__", "Access to __builtins__ can bypass security"),
    (r"__import__\s*\(", "__import__() can import arbitrary modules"),

    # Code injection
    (r"\bgetattr\s*\([^,]+,\s*[^\"']", "Dynamic attribute access - review carefully"),
    (r"\bsetattr\s*\(", "setattr() can modify object attributes dynamically"),
]

# Safe alternatives
SAFE_ALTERNATIVES = {
    "eval": "Use ast.literal_eval() for safe literal evaluation",
    "exec": "Avoid exec() - use explicit function calls",
    "pickle": "Use json for serialization when possible",
    "yaml.load": "Use yaml.safe_load() instead",
    "os.system": "Use subprocess.run() with shell=False",
    "shell=True": "Use shell=False and pass command as list",
}


class CodeValidator:
    """
    Validates code for syntax, types, and security.

    Performs multiple validation passes:
    1. Syntax validation (AST parsing)
    2. Import validation
    3. Type checking (optional, requires mypy)
    4. Security analysis (pattern matching + AST)
    """

    def __init__(
        self,
        enable_type_checking: bool = False,
        enable_security_checking: bool = True,
        security_level: str = "medium",
        allowed_imports: set[str] | None = None,
        blocked_imports: set[str] | None = None,
    ):
        """
        Initialize code validator.

        Args:
            enable_type_checking: Enable mypy type checking
            enable_security_checking: Enable security analysis
            security_level: 'low', 'medium', 'high' (higher = stricter)
            allowed_imports: Whitelist of allowed imports (None = all allowed)
            blocked_imports: Blacklist of blocked imports
        """
        self.enable_type_checking = enable_type_checking
        self.enable_security_checking = enable_security_checking
        self.security_level = security_level

        # Default blocked imports for security
        self.blocked_imports = blocked_imports or {
            "ctypes",
            "multiprocessing",
            "socket",
            "http.server",
            "ftplib",
            "telnetlib",
            "smtplib",
        }
        self.allowed_imports = allowed_imports

    def validate(self, code: str) -> ValidationResult:
        """
        Perform full validation on code.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult with all issues
        """
        result = ValidationResult(valid=True)

        # 1. Syntax validation
        self._validate_syntax(code, result)
        if not result.syntax_valid:
            result.calculate_scores()
            return result

        # 2. Import validation
        self._validate_imports(code, result)

        # 3. Type checking (optional)
        if self.enable_type_checking:
            self._validate_types(code, result)

        # 4. Security analysis
        if self.enable_security_checking:
            self._validate_security(code, result)

        result.calculate_scores()
        return result

    def validate_syntax(self, code: str) -> ValidationResult:
        """Validate only syntax."""
        result = ValidationResult(valid=True)
        self._validate_syntax(code, result)
        result.calculate_scores()
        return result

    def validate_security(self, code: str) -> ValidationResult:
        """Validate only security."""
        result = ValidationResult(valid=True)

        # Need valid syntax first
        try:
            ast.parse(code)
        except SyntaxError:
            result.add_issue(ValidationIssue(
                severity="error",
                category="syntax",
                message="Cannot analyze security: syntax error",
            ))
            result.calculate_scores()
            return result

        self._validate_security(code, result)
        result.calculate_scores()
        return result

    def _validate_syntax(self, code: str, result: ValidationResult) -> None:
        """Validate Python syntax."""
        try:
            ast.parse(code)
        except SyntaxError as e:
            result.add_issue(ValidationIssue(
                severity="error",
                category="syntax",
                message=str(e.msg) if e.msg else "Syntax error",
                line=e.lineno,
                column=e.offset,
            ))

    def _validate_imports(self, code: str, result: ValidationResult) -> None:
        """Validate imports."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import(alias.name, node.lineno, result)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self._check_import(node.module, node.lineno, result)

    def _check_import(
        self,
        module: str,
        line: int,
        result: ValidationResult,
    ) -> None:
        """Check if an import is allowed."""
        # Check blocked imports
        base_module = module.split(".")[0]

        if base_module in self.blocked_imports:
            result.add_issue(ValidationIssue(
                severity="error",
                category="import",
                message=f"Import '{module}' is blocked for security reasons",
                line=line,
                suggestion=f"Remove or replace import of {module}",
            ))

        # Check allowed imports (if whitelist is set)
        if self.allowed_imports is not None:
            if base_module not in self.allowed_imports:
                result.add_issue(ValidationIssue(
                    severity="warning",
                    category="import",
                    message=f"Import '{module}' is not in allowed list",
                    line=line,
                ))

    def _validate_types(self, code: str, result: ValidationResult) -> None:
        """Run mypy type checking."""
        try:
            # Write code to temp file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
            ) as f:
                f.write(code)
                temp_path = Path(f.name)

            try:
                # Run mypy
                proc = subprocess.run(
                    [
                        sys.executable, "-m", "mypy",
                        "--no-error-summary",
                        "--no-color-output",
                        str(temp_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # Parse mypy output
                if proc.returncode != 0:
                    for line in proc.stdout.split("\n"):
                        if not line.strip():
                            continue
                        # Parse: filename:line:col: error: message
                        match = re.match(
                            r"[^:]+:(\d+):(\d+):\s*(error|warning):\s*(.+)",
                            line,
                        )
                        if match:
                            result.add_issue(ValidationIssue(
                                severity=match.group(3),
                                category="type",
                                message=match.group(4),
                                line=int(match.group(1)),
                                column=int(match.group(2)),
                            ))

            finally:
                temp_path.unlink()

        except subprocess.TimeoutExpired:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="type",
                message="Type checking timed out",
            ))
        except FileNotFoundError:
            # mypy not installed
            pass
        except Exception as e:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="type",
                message=f"Type checking failed: {e}",
            ))

    def _validate_security(self, code: str, result: ValidationResult) -> None:
        """Perform security analysis."""
        # Pattern-based analysis
        self._check_dangerous_patterns(code, result)

        # AST-based analysis
        self._check_dangerous_ast(code, result)

    def _check_dangerous_patterns(
        self,
        code: str,
        result: ValidationResult,
    ) -> None:
        """Check for dangerous patterns using regex."""
        for pattern, message in DANGEROUS_PATTERNS:
            for match in re.finditer(pattern, code):
                # Find line number
                line_num = code[:match.start()].count("\n") + 1

                # Determine severity based on security level
                if self.security_level == "high":
                    severity = "error"
                elif self.security_level == "medium":
                    severity = "warning"
                else:
                    severity = "info"

                # Get safe alternative if available
                suggestion = None
                for key, alt in SAFE_ALTERNATIVES.items():
                    if key in message.lower() or key in pattern.lower():
                        suggestion = alt
                        break

                result.add_issue(ValidationIssue(
                    severity=severity,
                    category="security",
                    message=message,
                    line=line_num,
                    suggestion=suggestion,
                ))

    def _check_dangerous_ast(self, code: str, result: ValidationResult) -> None:
        """Check for dangerous patterns using AST analysis."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return

        for node in ast.walk(tree):
            # Check for dangerous function calls
            if isinstance(node, ast.Call):
                self._check_dangerous_call(node, result)

            # Check for dangerous attribute access
            if isinstance(node, ast.Attribute):
                self._check_dangerous_attribute(node, result)

    def _check_dangerous_call(
        self,
        node: ast.Call,
        result: ValidationResult,
    ) -> None:
        """Check for dangerous function calls."""
        func_name = None

        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if not func_name:
            return

        dangerous_funcs = {"eval", "exec", "compile", "__import__"}
        if func_name in dangerous_funcs:
            severity = "error" if self.security_level == "high" else "warning"
            result.add_issue(ValidationIssue(
                severity=severity,
                category="security",
                message=f"Dangerous function '{func_name}' called",
                line=node.lineno,
                suggestion=SAFE_ALTERNATIVES.get(func_name),
            ))

    def _check_dangerous_attribute(
        self,
        node: ast.Attribute,
        result: ValidationResult,
    ) -> None:
        """Check for dangerous attribute access."""
        dangerous_attrs = {
            "__class__",
            "__bases__",
            "__subclasses__",
            "__mro__",
            "__globals__",
            "__code__",
        }

        if node.attr in dangerous_attrs:
            result.add_issue(ValidationIssue(
                severity="warning",
                category="security",
                message=f"Access to '{node.attr}' can be used for exploitation",
                line=node.lineno,
            ))


class QuickValidator:
    """Fast validator for quick checks during evolution."""

    @staticmethod
    def is_syntactically_valid(code: str) -> bool:
        """Quick syntax check."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    @staticmethod
    def has_dangerous_calls(code: str) -> bool:
        """Quick check for dangerous calls."""
        dangerous = {"eval(", "exec(", "compile(", "__import__("}
        return any(d in code for d in dangerous)

    @staticmethod
    def get_functions(code: str) -> list[str]:
        """Get list of function names."""
        try:
            tree = ast.parse(code)
            return [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)
            ]
        except SyntaxError:
            return []

    @staticmethod
    def get_classes(code: str) -> list[str]:
        """Get list of class names."""
        try:
            tree = ast.parse(code)
            return [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef)
            ]
        except SyntaxError:
            return []

    @staticmethod
    def count_lines(code: str) -> int:
        """Count non-empty, non-comment lines."""
        count = 0
        for line in code.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
        return count


def validate_code(
    code: str,
    strict: bool = False,
) -> ValidationResult:
    """
    Convenience function for code validation.

    Args:
        code: Code to validate
        strict: Enable strict mode (type checking, high security)

    Returns:
        ValidationResult
    """
    validator = CodeValidator(
        enable_type_checking=strict,
        enable_security_checking=True,
        security_level="high" if strict else "medium",
    )
    return validator.validate(code)

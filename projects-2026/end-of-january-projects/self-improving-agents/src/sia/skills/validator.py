"""
Skill Validation System.

Validates skill code for syntax, safety, and correctness.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of skill validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: dict[str, Any] = field(default_factory=dict)


# Dangerous patterns to detect
DANGEROUS_PATTERNS = [
    (r"\beval\s*\(", "Use of eval() is dangerous"),
    (r"\bexec\s*\(", "Use of exec() is dangerous"),
    (r"\bcompile\s*\(", "Use of compile() is potentially dangerous"),
    (r"\b__import__\s*\(", "Use of __import__() is discouraged"),
    (r"\bos\.system\s*\(", "Use of os.system() is dangerous"),
    (r"\bsubprocess\.call\s*\(.*shell\s*=\s*True", "Shell=True in subprocess is dangerous"),
    (r"\bsubprocess\.run\s*\(.*shell\s*=\s*True", "Shell=True in subprocess is dangerous"),
    (r"\bsubprocess\.Popen\s*\(.*shell\s*=\s*True", "Shell=True in subprocess is dangerous"),
    (r"\bpickle\.loads?\s*\(", "Pickle can execute arbitrary code"),
    (r"\byaml\.load\s*\([^)]*\)(?!\s*,\s*Loader)", "yaml.load without Loader is unsafe"),
]

# Patterns that suggest potential issues
WARNING_PATTERNS = [
    (r"\bopen\s*\([^)]*['\"]w['\"]", "Writing to files - ensure path is validated"),
    (r"\brequests\.(get|post|put|delete)\s*\(", "HTTP request - ensure URL is validated"),
    (r"\bsqlalchemy.*execute\s*\(", "SQL execution - ensure query is parameterized"),
    (r"\b\.format\s*\([^)]*\)", "String formatting - potential injection if used with user input"),
    (r"f['\"].*\{.*\}.*['\"]", "F-string - ensure variables are sanitized if from user input"),
]


class SkillValidator:
    """
    Validates skill code for various concerns.

    Checks:
    - Syntax correctness (AST parsing)
    - Security (dangerous patterns)
    - Type hints (optional)
    - Documentation (optional)
    - Example-based testing (optional)
    """

    def __init__(
        self,
        require_type_hints: bool = False,
        require_docstring: bool = True,
        allow_dangerous: bool = False,
    ):
        """
        Initialize skill validator.

        Args:
            require_type_hints: Require type hints on parameters
            require_docstring: Require docstring on functions
            allow_dangerous: Allow potentially dangerous patterns
        """
        self.require_type_hints = require_type_hints
        self.require_docstring = require_docstring
        self.allow_dangerous = allow_dangerous

    def validate(self, code: str) -> ValidationResult:
        """
        Validate skill code.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(is_valid=True)

        # Check syntax
        syntax_result = self._check_syntax(code)
        if not syntax_result.is_valid:
            return syntax_result

        result.info.update(syntax_result.info)

        # Check for dangerous patterns
        if not self.allow_dangerous:
            danger_result = self._check_dangerous_patterns(code)
            result.errors.extend(danger_result.errors)

        # Check for warning patterns
        warning_result = self._check_warning_patterns(code)
        result.warnings.extend(warning_result.warnings)

        # Check structure (type hints, docstrings)
        structure_result = self._check_structure(code)
        result.errors.extend(structure_result.errors)
        result.warnings.extend(structure_result.warnings)
        result.info.update(structure_result.info)

        # Set overall validity
        result.is_valid = len(result.errors) == 0

        return result

    def _check_syntax(self, code: str) -> ValidationResult:
        """Check that code is syntactically valid Python."""
        result = ValidationResult(is_valid=True)

        if not code.strip():
            result.is_valid = False
            result.errors.append("Code is empty")
            return result

        try:
            tree = ast.parse(code)
            result.info["ast_nodes"] = len(list(ast.walk(tree)))

            # Find all function definitions
            functions = [
                node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
            ]
            result.info["function_count"] = len(functions)

            if functions:
                result.info["main_function"] = functions[0].name
                result.info["function_names"] = [f.name for f in functions]

        except SyntaxError as e:
            result.is_valid = False
            result.errors.append(f"Syntax error at line {e.lineno}: {e.msg}")

        return result

    def _check_dangerous_patterns(self, code: str) -> ValidationResult:
        """Check for dangerous code patterns."""
        result = ValidationResult(is_valid=True)

        for pattern, message in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                result.errors.append(f"Security: {message}")
                result.is_valid = False

        return result

    def _check_warning_patterns(self, code: str) -> ValidationResult:
        """Check for patterns that warrant warnings."""
        result = ValidationResult(is_valid=True)

        for pattern, message in WARNING_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                result.warnings.append(f"Warning: {message}")

        return result

    def _check_structure(self, code: str) -> ValidationResult:
        """Check code structure (type hints, docstrings, etc.)."""
        result = ValidationResult(is_valid=True)

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check docstring
                    has_docstring = (
                        node.body
                        and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)
                    )

                    if self.require_docstring and not has_docstring:
                        result.errors.append(
                            f"Function '{node.name}' missing docstring"
                        )

                    # Check type hints
                    if self.require_type_hints:
                        for arg in node.args.args:
                            if arg.annotation is None:
                                result.warnings.append(
                                    f"Parameter '{arg.arg}' in '{node.name}' missing type hint"
                                )

                        if node.returns is None:
                            result.warnings.append(
                                f"Function '{node.name}' missing return type hint"
                            )

                    # Gather info
                    result.info[f"function_{node.name}"] = {
                        "has_docstring": has_docstring,
                        "arg_count": len(node.args.args),
                        "has_return_type": node.returns is not None,
                        "line_count": node.end_lineno - node.lineno + 1
                        if hasattr(node, "end_lineno")
                        else None,
                    }

        except SyntaxError:
            # Already caught in syntax check
            pass

        return result

    def validate_schema(
        self,
        schema: dict[str, Any],
        schema_type: str = "input",
    ) -> ValidationResult:
        """
        Validate a JSON schema.

        Args:
            schema: JSON schema to validate
            schema_type: "input" or "output"

        Returns:
            ValidationResult
        """
        result = ValidationResult(is_valid=True)

        if not schema:
            result.warnings.append(f"Empty {schema_type} schema")
            return result

        # Check basic structure
        if "type" not in schema:
            result.errors.append(f"{schema_type} schema missing 'type' field")
            result.is_valid = False

        # For object types, check for properties
        if schema.get("type") == "object":
            if "properties" not in schema:
                result.warnings.append(
                    f"{schema_type} schema is object type but has no properties"
                )

            if "required" not in schema:
                result.warnings.append(
                    f"{schema_type} schema is object type but has no required fields"
                )

        return result

    def test_with_examples(
        self,
        code: str,
        examples: list[dict[str, Any]],
    ) -> ValidationResult:
        """
        Test skill code with example inputs.

        Args:
            code: Code to test
            examples: List of {"input": ..., "expected_output": ...} dicts

        Returns:
            ValidationResult with test results
        """
        result = ValidationResult(is_valid=True)

        # First validate syntax
        syntax_result = self._check_syntax(code)
        if not syntax_result.is_valid:
            return syntax_result

        if not examples:
            result.warnings.append("No examples provided for testing")
            return result

        # Try to execute with examples
        # Note: This runs in the current process - use sandbox for untrusted code
        try:
            # Create a namespace for execution
            namespace: dict[str, Any] = {}
            exec(code, namespace)

            # Find the main function
            function_name = syntax_result.info.get("main_function")
            if not function_name or function_name not in namespace:
                result.warnings.append("Could not find main function for testing")
                return result

            func = namespace[function_name]

            # Test each example
            passed = 0
            failed = 0
            test_results = []

            for i, example in enumerate(examples):
                try:
                    input_data = example.get("input", {})
                    expected = example.get("expected_output")

                    # Call function
                    if isinstance(input_data, dict):
                        actual = func(**input_data)
                    else:
                        actual = func(input_data)

                    # Compare results
                    if expected is not None and actual != expected:
                        failed += 1
                        test_results.append(
                            {
                                "example": i + 1,
                                "passed": False,
                                "expected": expected,
                                "actual": actual,
                            }
                        )
                    else:
                        passed += 1
                        test_results.append({"example": i + 1, "passed": True})

                except Exception as e:
                    failed += 1
                    test_results.append(
                        {"example": i + 1, "passed": False, "error": str(e)}
                    )

            result.info["test_results"] = test_results
            result.info["tests_passed"] = passed
            result.info["tests_failed"] = failed

            if failed > 0:
                result.errors.append(f"{failed}/{len(examples)} example tests failed")
                result.is_valid = False

        except Exception as e:
            result.errors.append(f"Error executing code: {e}")
            result.is_valid = False

        return result

    def get_security_report(self, code: str) -> dict[str, Any]:
        """
        Generate a security report for skill code.

        Args:
            code: Code to analyze

        Returns:
            Security report dictionary
        """
        report = {
            "dangerous_patterns": [],
            "warnings": [],
            "imports": [],
            "function_calls": [],
            "risk_level": "low",
        }

        # Check dangerous patterns
        for pattern, message in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                report["dangerous_patterns"].append(message)

        # Check warning patterns
        for pattern, message in WARNING_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                report["warnings"].append(message)

        # Analyze AST
        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Collect imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        report["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        report["imports"].append(node.module)

                # Collect function calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        report["function_calls"].append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        report["function_calls"].append(node.func.attr)

        except SyntaxError:
            report["parse_error"] = True

        # Determine risk level
        if report["dangerous_patterns"]:
            report["risk_level"] = "high"
        elif report["warnings"]:
            report["risk_level"] = "medium"

        return report

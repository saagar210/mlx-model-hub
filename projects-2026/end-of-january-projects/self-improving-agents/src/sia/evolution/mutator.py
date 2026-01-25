"""
Code Mutator for Evolution.

Provides mechanisms for modifying Python code.
"""

from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import UUID, uuid4


# ============================================================================
# Mutation Types
# ============================================================================


@dataclass
class Mutation:
    """Represents a single code mutation."""

    id: UUID = field(default_factory=uuid4)
    mutation_type: str = ""  # 'add', 'remove', 'replace', 'modify'
    target: str = ""  # What was mutated (function name, line number, etc.)
    description: str = ""

    # Code changes
    original_code: str = ""
    mutated_code: str = ""
    diff: str = ""

    # Location
    start_line: int | None = None
    end_line: int | None = None

    # Metadata
    confidence: float = 0.5
    risk_level: str = "medium"  # low, medium, high

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class MutationResult:
    """Result of applying mutations."""

    mutations: list[Mutation] = field(default_factory=list)
    original_code: str = ""
    mutated_code: str = ""
    original_hash: str = ""
    mutated_hash: str = ""

    # Validation
    syntax_valid: bool = False
    imports_valid: bool = False

    # Diff
    unified_diff: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mutations": [
                {
                    "id": str(m.id),
                    "type": m.mutation_type,
                    "target": m.target,
                    "description": m.description,
                    "confidence": m.confidence,
                }
                for m in self.mutations
            ],
            "original_hash": self.original_hash,
            "mutated_hash": self.mutated_hash,
            "syntax_valid": self.syntax_valid,
            "unified_diff": self.unified_diff,
        }


# ============================================================================
# Code Mutator
# ============================================================================


class CodeMutator:
    """
    Mutates Python code using various strategies.

    Supports AST-based transformations, text-based edits,
    and monkey patching.
    """

    def __init__(self):
        """Initialize code mutator."""
        self.mutation_history: list[MutationResult] = []

    def mutate(
        self,
        code: str,
        mutations: list[Mutation],
    ) -> MutationResult:
        """
        Apply mutations to code.

        Args:
            code: Original Python code
            mutations: List of mutations to apply

        Returns:
            MutationResult with mutated code
        """
        result = MutationResult(
            original_code=code,
            original_hash=self._hash_code(code),
        )

        current_code = code

        for mutation in mutations:
            try:
                if mutation.mutation_type == "replace":
                    current_code = self._apply_replace(current_code, mutation)
                elif mutation.mutation_type == "add":
                    current_code = self._apply_add(current_code, mutation)
                elif mutation.mutation_type == "remove":
                    current_code = self._apply_remove(current_code, mutation)
                elif mutation.mutation_type == "modify":
                    current_code = self._apply_modify(current_code, mutation)

                # Generate diff for this mutation
                mutation.diff = self._generate_diff(
                    result.mutated_code or result.original_code,
                    current_code,
                )
                result.mutations.append(mutation)

            except Exception as e:
                # Skip failed mutations
                mutation.description += f" (FAILED: {e})"
                continue

        result.mutated_code = current_code
        result.mutated_hash = self._hash_code(current_code)
        result.unified_diff = self._generate_diff(code, current_code)

        # Validate result
        result.syntax_valid = self._validate_syntax(current_code)

        # Record in history
        self.mutation_history.append(result)

        return result

    def _apply_replace(self, code: str, mutation: Mutation) -> str:
        """Apply a replacement mutation."""
        if mutation.original_code and mutation.mutated_code:
            return code.replace(mutation.original_code, mutation.mutated_code, 1)
        return code

    def _apply_add(self, code: str, mutation: Mutation) -> str:
        """Apply an addition mutation."""
        lines = code.split("\n")

        if mutation.start_line is not None:
            # Insert at specific line
            insert_at = min(mutation.start_line, len(lines))
            lines.insert(insert_at, mutation.mutated_code)
        else:
            # Append at end
            lines.append(mutation.mutated_code)

        return "\n".join(lines)

    def _apply_remove(self, code: str, mutation: Mutation) -> str:
        """Apply a removal mutation."""
        if mutation.original_code:
            return code.replace(mutation.original_code, "", 1)
        elif mutation.start_line is not None and mutation.end_line is not None:
            lines = code.split("\n")
            del lines[mutation.start_line : mutation.end_line + 1]
            return "\n".join(lines)
        return code

    def _apply_modify(self, code: str, mutation: Mutation) -> str:
        """Apply a modification mutation (same as replace but semantic)."""
        return self._apply_replace(code, mutation)

    def replace_function(
        self,
        code: str,
        function_name: str,
        new_function: str,
    ) -> MutationResult:
        """
        Replace a function in the code.

        Args:
            code: Original code
            function_name: Name of function to replace
            new_function: New function code

        Returns:
            MutationResult
        """
        tree = ast.parse(code)
        lines = code.split("\n")

        # Find the function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                # Get function bounds
                start_line = node.lineno - 1
                end_line = node.end_lineno

                # Extract original function
                original_func = "\n".join(lines[start_line:end_line])

                # Create mutation
                mutation = Mutation(
                    mutation_type="replace",
                    target=function_name,
                    description=f"Replace function {function_name}",
                    original_code=original_func,
                    mutated_code=new_function,
                    start_line=start_line,
                    end_line=end_line,
                )

                # Apply mutation
                new_lines = lines[:start_line] + new_function.split("\n") + lines[end_line:]
                mutated_code = "\n".join(new_lines)

                result = MutationResult(
                    original_code=code,
                    mutated_code=mutated_code,
                    original_hash=self._hash_code(code),
                    mutated_hash=self._hash_code(mutated_code),
                    mutations=[mutation],
                    syntax_valid=self._validate_syntax(mutated_code),
                )
                result.unified_diff = self._generate_diff(code, mutated_code)

                self.mutation_history.append(result)
                return result

        # Function not found
        return MutationResult(
            original_code=code,
            mutated_code=code,
            original_hash=self._hash_code(code),
            mutated_hash=self._hash_code(code),
        )

    def add_function(
        self,
        code: str,
        new_function: str,
        after_function: str | None = None,
    ) -> MutationResult:
        """
        Add a new function to the code.

        Args:
            code: Original code
            new_function: New function to add
            after_function: Function after which to add (or end if None)

        Returns:
            MutationResult
        """
        if after_function:
            tree = ast.parse(code)
            lines = code.split("\n")

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == after_function:
                    insert_at = node.end_lineno

                    mutation = Mutation(
                        mutation_type="add",
                        target=f"after {after_function}",
                        description="Add new function",
                        mutated_code=new_function,
                        start_line=insert_at,
                    )

                    new_lines = lines[:insert_at] + ["", new_function] + lines[insert_at:]
                    mutated_code = "\n".join(new_lines)

                    result = MutationResult(
                        original_code=code,
                        mutated_code=mutated_code,
                        original_hash=self._hash_code(code),
                        mutated_hash=self._hash_code(mutated_code),
                        mutations=[mutation],
                        syntax_valid=self._validate_syntax(mutated_code),
                    )
                    result.unified_diff = self._generate_diff(code, mutated_code)

                    self.mutation_history.append(result)
                    return result

        # Append at end
        mutation = Mutation(
            mutation_type="add",
            target="end of file",
            description="Add new function at end",
            mutated_code=new_function,
        )

        mutated_code = code + "\n\n" + new_function

        result = MutationResult(
            original_code=code,
            mutated_code=mutated_code,
            original_hash=self._hash_code(code),
            mutated_hash=self._hash_code(mutated_code),
            mutations=[mutation],
            syntax_valid=self._validate_syntax(mutated_code),
        )
        result.unified_diff = self._generate_diff(code, mutated_code)

        self.mutation_history.append(result)
        return result

    def remove_function(
        self,
        code: str,
        function_name: str,
    ) -> MutationResult:
        """
        Remove a function from the code.

        Args:
            code: Original code
            function_name: Name of function to remove

        Returns:
            MutationResult
        """
        tree = ast.parse(code)
        lines = code.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                start_line = node.lineno - 1
                end_line = node.end_lineno

                original_func = "\n".join(lines[start_line:end_line])

                mutation = Mutation(
                    mutation_type="remove",
                    target=function_name,
                    description=f"Remove function {function_name}",
                    original_code=original_func,
                    start_line=start_line,
                    end_line=end_line,
                )

                new_lines = lines[:start_line] + lines[end_line:]
                mutated_code = "\n".join(new_lines)

                result = MutationResult(
                    original_code=code,
                    mutated_code=mutated_code,
                    original_hash=self._hash_code(code),
                    mutated_hash=self._hash_code(mutated_code),
                    mutations=[mutation],
                    syntax_valid=self._validate_syntax(mutated_code),
                )
                result.unified_diff = self._generate_diff(code, mutated_code)

                self.mutation_history.append(result)
                return result

        # Function not found
        return MutationResult(
            original_code=code,
            mutated_code=code,
            original_hash=self._hash_code(code),
            mutated_hash=self._hash_code(code),
        )

    def modify_docstring(
        self,
        code: str,
        function_name: str,
        new_docstring: str,
    ) -> MutationResult:
        """
        Modify a function's docstring.

        Args:
            code: Original code
            function_name: Function to modify
            new_docstring: New docstring content

        Returns:
            MutationResult
        """
        tree = ast.parse(code)
        lines = code.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                # Find existing docstring
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    # Has docstring - replace it
                    doc_node = node.body[0]
                    start_line = doc_node.lineno - 1
                    end_line = doc_node.end_lineno

                    original_doc = "\n".join(lines[start_line:end_line])
                    new_doc = f'    """{new_docstring}"""'

                    mutation = Mutation(
                        mutation_type="modify",
                        target=f"{function_name} docstring",
                        description="Modify function docstring",
                        original_code=original_doc,
                        mutated_code=new_doc,
                        start_line=start_line,
                        end_line=end_line,
                    )

                    new_lines = lines[:start_line] + [new_doc] + lines[end_line:]
                    mutated_code = "\n".join(new_lines)

                else:
                    # No docstring - add one
                    insert_at = node.lineno  # After def line
                    new_doc = f'    """{new_docstring}"""'

                    mutation = Mutation(
                        mutation_type="add",
                        target=f"{function_name} docstring",
                        description="Add function docstring",
                        mutated_code=new_doc,
                        start_line=insert_at,
                    )

                    new_lines = lines[:insert_at] + [new_doc] + lines[insert_at:]
                    mutated_code = "\n".join(new_lines)

                result = MutationResult(
                    original_code=code,
                    mutated_code=mutated_code,
                    original_hash=self._hash_code(code),
                    mutated_hash=self._hash_code(mutated_code),
                    mutations=[mutation],
                    syntax_valid=self._validate_syntax(mutated_code),
                )
                result.unified_diff = self._generate_diff(code, mutated_code)

                self.mutation_history.append(result)
                return result

        return MutationResult(
            original_code=code,
            mutated_code=code,
            original_hash=self._hash_code(code),
            mutated_hash=self._hash_code(code),
        )

    def rename_variable(
        self,
        code: str,
        old_name: str,
        new_name: str,
        scope: str | None = None,
    ) -> MutationResult:
        """
        Rename a variable throughout the code.

        Args:
            code: Original code
            old_name: Variable to rename
            new_name: New variable name
            scope: Function scope to limit renaming

        Returns:
            MutationResult
        """
        # Simple regex-based renaming (could be improved with AST)
        pattern = rf"\b{re.escape(old_name)}\b"
        mutated_code = re.sub(pattern, new_name, code)

        mutation = Mutation(
            mutation_type="modify",
            target=old_name,
            description=f"Rename variable {old_name} -> {new_name}",
            original_code=old_name,
            mutated_code=new_name,
        )

        result = MutationResult(
            original_code=code,
            mutated_code=mutated_code,
            original_hash=self._hash_code(code),
            mutated_hash=self._hash_code(mutated_code),
            mutations=[mutation],
            syntax_valid=self._validate_syntax(mutated_code),
        )
        result.unified_diff = self._generate_diff(code, mutated_code)

        self.mutation_history.append(result)
        return result

    def extract_function(
        self,
        code: str,
        source_function: str,
        start_line: int,
        end_line: int,
        new_function_name: str,
    ) -> MutationResult:
        """
        Extract lines from a function into a new function.

        Args:
            code: Original code
            source_function: Function to extract from
            start_line: Start line of code to extract
            end_line: End line of code to extract
            new_function_name: Name for the extracted function

        Returns:
            MutationResult
        """
        lines = code.split("\n")

        # Get lines to extract
        extracted_lines = lines[start_line:end_line + 1]
        extracted_code = "\n".join(extracted_lines)

        # Create new function
        new_function = f"def {new_function_name}():\n"
        for line in extracted_lines:
            new_function += f"    {line.strip()}\n"

        # Replace original lines with function call
        call_line = f"    {new_function_name}()"
        new_lines = lines[:start_line] + [call_line] + lines[end_line + 1:]

        # Add new function at end
        new_lines.extend(["", new_function])

        mutated_code = "\n".join(new_lines)

        mutation = Mutation(
            mutation_type="modify",
            target=source_function,
            description=f"Extract code to {new_function_name}",
            original_code=extracted_code,
            mutated_code=f"{call_line}\n...\n{new_function}",
            start_line=start_line,
            end_line=end_line,
        )

        result = MutationResult(
            original_code=code,
            mutated_code=mutated_code,
            original_hash=self._hash_code(code),
            mutated_hash=self._hash_code(mutated_code),
            mutations=[mutation],
            syntax_valid=self._validate_syntax(mutated_code),
        )
        result.unified_diff = self._generate_diff(code, mutated_code)

        self.mutation_history.append(result)
        return result

    def get_functions(self, code: str) -> list[dict[str, Any]]:
        """
        Get all functions in the code.

        Args:
            code: Python code

        Returns:
            List of function info dicts
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "start_line": node.lineno,
                    "end_line": node.end_lineno,
                    "args": [arg.arg for arg in node.args.args],
                    "decorators": [
                        ast.unparse(d) if hasattr(ast, "unparse") else str(d)
                        for d in node.decorator_list
                    ],
                })

        return functions

    def _hash_code(self, code: str) -> str:
        """Generate hash of code."""
        return hashlib.sha256(code.encode()).hexdigest()[:16]

    def _validate_syntax(self, code: str) -> bool:
        """Check if code has valid syntax."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _generate_diff(self, original: str, modified: str) -> str:
        """Generate unified diff between two code versions."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile="original",
            tofile="modified",
        )

        return "".join(diff)

    def get_history(self, limit: int = 10) -> list[MutationResult]:
        """Get recent mutation history."""
        return self.mutation_history[-limit:]

    def clear_history(self) -> None:
        """Clear mutation history."""
        self.mutation_history.clear()

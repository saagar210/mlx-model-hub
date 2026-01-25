"""
Random Mutation Strategy.

Applies random mutations to code for exploration.
"""

from __future__ import annotations

import ast
import random
from typing import Any

from sia.evolution.mutator import Mutation
from sia.evolution.strategies.base import MutationProposal, MutationStrategy


class RandomMutationStrategy(MutationStrategy):
    """
    Applies random mutations to explore the code space.

    Useful for discovering unexpected improvements through
    random exploration.
    """

    # Common mutation patterns
    PATTERNS = {
        "add_logging": {
            "template": 'print(f"DEBUG: {var_name}={{repr({var_name})}}}")',
            "description": "Add debug logging",
        },
        "add_type_hint": {
            "description": "Add type hints to function",
        },
        "optimize_loop": {
            "description": "Convert loop to list comprehension",
        },
        "add_docstring": {
            "template": '"""TODO: Add docstring."""',
            "description": "Add missing docstring",
        },
        "add_error_handling": {
            "description": "Wrap in try/except",
        },
        "simplify_conditional": {
            "description": "Simplify conditional expression",
        },
    }

    def __init__(
        self,
        mutation_rate: float = 0.1,
        max_mutations: int = 3,
        seed: int | None = None,
    ):
        """
        Initialize random mutation strategy.

        Args:
            mutation_rate: Probability of mutating each element
            max_mutations: Maximum mutations per proposal
            seed: Random seed for reproducibility
        """
        super().__init__(name="random")
        self.mutation_rate = mutation_rate
        self.max_mutations = max_mutations

        if seed is not None:
            random.seed(seed)

    def propose_mutations(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """
        Generate random mutation proposals.

        Args:
            code: Python code to mutate
            context: Additional context

        Returns:
            List of mutation proposals
        """
        proposals = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        # Find mutation targets
        targets = self._find_mutation_targets(tree, code)

        # Generate proposals
        num_proposals = random.randint(1, 3)

        for _ in range(num_proposals):
            mutations = []
            num_mutations = random.randint(1, min(self.max_mutations, len(targets)))

            selected_targets = random.sample(targets, min(num_mutations, len(targets)))

            for target in selected_targets:
                mutation = self._create_random_mutation(target, code)
                if mutation:
                    mutations.append(mutation)

            if mutations:
                proposal = MutationProposal(
                    strategy=self.name,
                    mutations=mutations,
                    rationale="Random exploration of code space",
                    expected_improvement="Unknown - exploratory mutation",
                    confidence=0.3,  # Low confidence for random
                    risk_level="medium",
                )
                proposals.append(proposal)

        return proposals

    def _find_mutation_targets(
        self,
        tree: ast.AST,
        code: str,
    ) -> list[dict[str, Any]]:
        """Find potential mutation targets in the AST."""
        targets = []
        lines = code.split("\n")

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                targets.append({
                    "type": "function",
                    "name": node.name,
                    "node": node,
                    "start_line": node.lineno - 1,
                    "end_line": node.end_lineno - 1 if node.end_lineno else node.lineno - 1,
                })

            elif isinstance(node, ast.For):
                targets.append({
                    "type": "for_loop",
                    "node": node,
                    "start_line": node.lineno - 1,
                    "end_line": node.end_lineno - 1 if node.end_lineno else node.lineno - 1,
                })

            elif isinstance(node, ast.If):
                targets.append({
                    "type": "conditional",
                    "node": node,
                    "start_line": node.lineno - 1,
                    "end_line": node.end_lineno - 1 if node.end_lineno else node.lineno - 1,
                })

            elif isinstance(node, ast.Assign):
                targets.append({
                    "type": "assignment",
                    "node": node,
                    "start_line": node.lineno - 1,
                    "end_line": node.end_lineno - 1 if node.end_lineno else node.lineno - 1,
                })

        return targets

    def _create_random_mutation(
        self,
        target: dict[str, Any],
        code: str,
    ) -> Mutation | None:
        """Create a random mutation for a target."""
        lines = code.split("\n")
        target_type = target["type"]

        if target_type == "function":
            return self._mutate_function(target, lines)
        elif target_type == "for_loop":
            return self._mutate_loop(target, lines)
        elif target_type == "conditional":
            return self._mutate_conditional(target, lines)
        elif target_type == "assignment":
            return self._mutate_assignment(target, lines)

        return None

    def _mutate_function(
        self,
        target: dict[str, Any],
        lines: list[str],
    ) -> Mutation | None:
        """Apply random mutation to a function."""
        node = target["node"]
        mutation_type = random.choice([
            "add_docstring",
            "add_logging",
            "add_type_hint",
        ])

        if mutation_type == "add_docstring":
            # Check if function already has docstring
            if not (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                # Get function signature line
                func_line = lines[target["start_line"]]
                indent = len(func_line) - len(func_line.lstrip())
                doc_indent = " " * (indent + 4)

                return Mutation(
                    mutation_type="add",
                    target=f"function {node.name}",
                    description=f"Add docstring to {node.name}",
                    mutated_code=f'{doc_indent}"""TODO: Document {node.name}."""',
                    start_line=target["start_line"] + 1,
                    confidence=0.4,
                    risk_level="low",
                )

        elif mutation_type == "add_logging":
            # Add logging at function start
            func_line = lines[target["start_line"]]
            indent = len(func_line) - len(func_line.lstrip())
            log_indent = " " * (indent + 4)

            return Mutation(
                mutation_type="add",
                target=f"function {node.name}",
                description=f"Add logging to {node.name}",
                mutated_code=f'{log_indent}print(f"Entering {node.name}")',
                start_line=target["start_line"] + 1,
                confidence=0.3,
                risk_level="low",
            )

        return None

    def _mutate_loop(
        self,
        target: dict[str, Any],
        lines: list[str],
    ) -> Mutation | None:
        """Apply random mutation to a loop."""
        node = target["node"]

        # Try to convert simple for loop to list comprehension
        if isinstance(node, ast.For) and len(node.body) == 1:
            if isinstance(node.body[0], ast.Expr):
                # Check if it's a simple append pattern
                if isinstance(node.body[0].value, ast.Call):
                    call = node.body[0].value
                    if (
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr == "append"
                    ):
                        return Mutation(
                            mutation_type="modify",
                            target="for loop",
                            description="Consider converting to list comprehension",
                            original_code="\n".join(lines[target["start_line"]:target["end_line"] + 1]),
                            mutated_code="# Consider: [x for x in iterable]",
                            confidence=0.2,
                            risk_level="medium",
                        )

        return None

    def _mutate_conditional(
        self,
        target: dict[str, Any],
        lines: list[str],
    ) -> Mutation | None:
        """Apply random mutation to a conditional."""
        # Add else clause if missing
        node = target["node"]

        if not node.orelse:
            line = lines[target["start_line"]]
            indent = len(line) - len(line.lstrip())
            else_indent = " " * indent

            return Mutation(
                mutation_type="add",
                target="if statement",
                description="Add else clause",
                mutated_code=f"{else_indent}else:\n{else_indent}    pass",
                start_line=target["end_line"] + 1,
                confidence=0.2,
                risk_level="low",
            )

        return None

    def _mutate_assignment(
        self,
        target: dict[str, Any],
        lines: list[str],
    ) -> Mutation | None:
        """Apply random mutation to an assignment."""
        line = lines[target["start_line"]]
        indent = len(line) - len(line.lstrip())
        log_indent = " " * indent

        # Get variable name
        node = target["node"]
        if node.targets and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id

            return Mutation(
                mutation_type="add",
                target=f"variable {var_name}",
                description=f"Add debug print for {var_name}",
                mutated_code=f'{log_indent}print(f"DEBUG: {var_name}={{{var_name}!r}}")',
                start_line=target["start_line"] + 1,
                confidence=0.2,
                risk_level="low",
            )

        return None

    def evaluate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_results: dict[str, Any] | None = None,
    ) -> float:
        """
        Evaluate mutation quality.

        For random mutations, primarily checks if tests still pass.
        """
        score = 0.5  # Base score

        # Syntax check
        try:
            ast.parse(mutated_code)
            score += 0.2
        except SyntaxError:
            return 0.0

        # Test results
        if test_results:
            if test_results.get("passed", False):
                score += 0.2
            if test_results.get("tests_passed", 0) > test_results.get("tests_failed", 0):
                score += 0.1

        return min(score, 1.0)

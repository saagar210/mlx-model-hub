"""
Crossover Mutation Strategy.

Combines code from multiple agent versions.
"""

from __future__ import annotations

import ast
import random
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from sia.evolution.mutator import Mutation, MutationResult
from sia.evolution.strategies.base import MutationProposal, MutationStrategy


@dataclass
class CrossoverCandidate:
    """A candidate for crossover."""

    id: UUID = field(default_factory=uuid4)
    code: str = ""
    fitness: float = 0.0
    source: str = ""  # Where this code came from
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossoverResult:
    """Result of a crossover operation."""

    success: bool
    child_code: str
    parent_ids: list[UUID]
    crossover_points: list[str]  # What was combined
    description: str


class CrossoverStrategy(MutationStrategy):
    """
    Combines code from multiple agent versions.

    Uses various crossover techniques:
    - Function-level: Swap entire functions
    - Block-level: Swap code blocks
    - Expression-level: Swap expressions
    """

    def __init__(
        self,
        crossover_rate: float = 0.7,
        prefer_better_parent: float = 0.6,
        seed: int | None = None,
    ):
        """
        Initialize crossover strategy.

        Args:
            crossover_rate: Probability of performing crossover vs copying
            prefer_better_parent: Bias toward better-performing parent
            seed: Random seed
        """
        super().__init__(name="crossover")
        self.crossover_rate = crossover_rate
        self.prefer_better_parent = prefer_better_parent
        self.candidates: list[CrossoverCandidate] = []

        if seed is not None:
            random.seed(seed)

    def add_candidate(
        self,
        code: str,
        fitness: float = 0.0,
        source: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> CrossoverCandidate:
        """Add a candidate for crossover."""
        candidate = CrossoverCandidate(
            code=code,
            fitness=fitness,
            source=source,
            metadata=metadata or {},
        )
        self.candidates.append(candidate)
        return candidate

    def clear_candidates(self) -> None:
        """Clear all candidates."""
        self.candidates = []

    def propose_mutations(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """
        Generate crossover proposals.

        Args:
            code: Primary code (parent 1)
            context: Should contain 'candidates' with other code versions

        Returns:
            List of crossover proposals
        """
        proposals = []

        # Get candidates from context or use stored ones
        candidates = self.candidates.copy()
        if context and "candidates" in context:
            for c in context["candidates"]:
                if isinstance(c, CrossoverCandidate):
                    candidates.append(c)
                elif isinstance(c, dict):
                    candidates.append(CrossoverCandidate(
                        code=c.get("code", ""),
                        fitness=c.get("fitness", 0.0),
                        source=c.get("source", ""),
                    ))

        if not candidates:
            # Add the primary code as a candidate
            candidates.append(CrossoverCandidate(code=code, fitness=0.5))

        # Create primary candidate
        primary = CrossoverCandidate(code=code, fitness=0.5)

        # Generate crossover proposals
        for candidate in candidates:
            if candidate.code == code:
                continue

            # Try different crossover types
            crossover_types = [
                self._function_crossover,
                self._method_crossover,
                self._import_crossover,
            ]

            for crossover_fn in crossover_types:
                result = crossover_fn(primary, candidate)
                if result and result.success:
                    mutations = [
                        Mutation(
                            mutation_type="crossover",
                            target=", ".join(result.crossover_points),
                            description=result.description,
                            original_code=code,
                            mutated_code=result.child_code,
                            confidence=0.5,
                            risk_level="medium",
                        )
                    ]

                    proposal = MutationProposal(
                        strategy=self.name,
                        mutations=mutations,
                        rationale=f"Crossover from {candidate.source or 'candidate'}",
                        expected_improvement="Combined best aspects of both versions",
                        confidence=0.5,
                        risk_level="medium",
                        metadata={
                            "parent_ids": [str(primary.id), str(candidate.id)],
                            "crossover_points": result.crossover_points,
                        },
                    )
                    proposals.append(proposal)

        return proposals

    def _function_crossover(
        self,
        parent1: CrossoverCandidate,
        parent2: CrossoverCandidate,
    ) -> CrossoverResult | None:
        """Swap functions between parents."""
        try:
            tree1 = ast.parse(parent1.code)
            tree2 = ast.parse(parent2.code)
        except SyntaxError:
            return None

        # Get functions from both
        funcs1 = {
            n.name: n for n in ast.walk(tree1)
            if isinstance(n, ast.FunctionDef)
        }
        funcs2 = {
            n.name: n for n in ast.walk(tree2)
            if isinstance(n, ast.FunctionDef)
        }

        # Find common functions
        common = set(funcs1.keys()) & set(funcs2.keys())
        if not common:
            return None

        # Select functions to swap
        num_to_swap = random.randint(1, min(3, len(common)))
        to_swap = random.sample(list(common), num_to_swap)

        # Bias toward better parent
        if random.random() < self.prefer_better_parent:
            # Take from better parent
            if parent1.fitness > parent2.fitness:
                source_funcs = funcs1
                target_code = parent2.code
            else:
                source_funcs = funcs2
                target_code = parent1.code
        else:
            # Random selection
            source_funcs = funcs2
            target_code = parent1.code

        # Apply swaps
        lines = target_code.split("\n")
        result_lines = lines.copy()

        for func_name in to_swap:
            source_func = source_funcs.get(func_name)
            if not source_func:
                continue

            # Get source function code
            source_lines = (
                parent2.code if source_funcs is funcs2 else parent1.code
            ).split("\n")
            func_code = source_lines[
                source_func.lineno - 1:source_func.end_lineno
            ]

            # Find and replace in target
            target_tree = ast.parse("\n".join(result_lines))
            for node in ast.walk(target_tree):
                if isinstance(node, ast.FunctionDef) and node.name == func_name:
                    # Replace lines
                    result_lines = (
                        result_lines[:node.lineno - 1]
                        + func_code
                        + result_lines[node.end_lineno:]
                    )
                    break

        child_code = "\n".join(result_lines)

        # Validate result
        try:
            ast.parse(child_code)
        except SyntaxError:
            return None

        return CrossoverResult(
            success=True,
            child_code=child_code,
            parent_ids=[parent1.id, parent2.id],
            crossover_points=to_swap,
            description=f"Swapped functions: {', '.join(to_swap)}",
        )

    def _method_crossover(
        self,
        parent1: CrossoverCandidate,
        parent2: CrossoverCandidate,
    ) -> CrossoverResult | None:
        """Swap methods between classes."""
        try:
            tree1 = ast.parse(parent1.code)
            tree2 = ast.parse(parent2.code)
        except SyntaxError:
            return None

        # Get classes from both
        classes1 = {
            n.name: n for n in ast.walk(tree1)
            if isinstance(n, ast.ClassDef)
        }
        classes2 = {
            n.name: n for n in ast.walk(tree2)
            if isinstance(n, ast.ClassDef)
        }

        # Find common classes
        common_classes = set(classes1.keys()) & set(classes2.keys())
        if not common_classes:
            return None

        # Select a class
        class_name = random.choice(list(common_classes))
        class1 = classes1[class_name]
        class2 = classes2[class_name]

        # Get methods from both classes
        methods1 = {
            n.name: n for n in class1.body
            if isinstance(n, ast.FunctionDef)
        }
        methods2 = {
            n.name: n for n in class2.body
            if isinstance(n, ast.FunctionDef)
        }

        # Find common methods (excluding __init__ and special methods)
        common_methods = set(methods1.keys()) & set(methods2.keys())
        common_methods = {
            m for m in common_methods
            if not m.startswith("__") or m == "__init__"
        }

        if not common_methods:
            return None

        # Select method to swap
        method_name = random.choice(list(common_methods))

        # Build new code by swapping the method
        lines1 = parent1.code.split("\n")
        lines2 = parent2.code.split("\n")

        method2 = methods2[method_name]
        method1 = methods1[method_name]

        # Get method code from parent2
        method_code = lines2[method2.lineno - 1:method2.end_lineno]

        # Replace in parent1
        result_lines = (
            lines1[:method1.lineno - 1]
            + method_code
            + lines1[method1.end_lineno:]
        )

        child_code = "\n".join(result_lines)

        try:
            ast.parse(child_code)
        except SyntaxError:
            return None

        return CrossoverResult(
            success=True,
            child_code=child_code,
            parent_ids=[parent1.id, parent2.id],
            crossover_points=[f"{class_name}.{method_name}"],
            description=f"Swapped method {class_name}.{method_name}",
        )

    def _import_crossover(
        self,
        parent1: CrossoverCandidate,
        parent2: CrossoverCandidate,
    ) -> CrossoverResult | None:
        """Merge imports from both parents."""
        try:
            tree1 = ast.parse(parent1.code)
            tree2 = ast.parse(parent2.code)
        except SyntaxError:
            return None

        # Collect imports from both
        imports1 = set()
        imports2 = set()

        for node in ast.walk(tree1):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports1.add(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports1.add(f"from {module} import {alias.name}")

        for node in ast.walk(tree2):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports2.add(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports2.add(f"from {module} import {alias.name}")

        # Find imports only in parent2
        new_imports = imports2 - imports1
        if not new_imports:
            return None

        # Add new imports to parent1
        lines = parent1.code.split("\n")

        # Find last import line
        last_import_line = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                last_import_line = i

        # Insert new imports
        import_lines = sorted(list(new_imports))
        result_lines = (
            lines[:last_import_line + 1]
            + import_lines
            + lines[last_import_line + 1:]
        )

        child_code = "\n".join(result_lines)

        try:
            ast.parse(child_code)
        except SyntaxError:
            return None

        return CrossoverResult(
            success=True,
            child_code=child_code,
            parent_ids=[parent1.id, parent2.id],
            crossover_points=list(new_imports),
            description=f"Added imports: {', '.join(new_imports)}",
        )

    def crossover(
        self,
        parent1: CrossoverCandidate,
        parent2: CrossoverCandidate,
        crossover_type: str = "auto",
    ) -> CrossoverResult | None:
        """
        Perform crossover between two candidates.

        Args:
            parent1: First parent
            parent2: Second parent
            crossover_type: 'function', 'method', 'import', or 'auto'

        Returns:
            Crossover result or None if failed
        """
        if random.random() > self.crossover_rate:
            # No crossover, return copy of better parent
            better = parent1 if parent1.fitness >= parent2.fitness else parent2
            return CrossoverResult(
                success=True,
                child_code=better.code,
                parent_ids=[parent1.id, parent2.id],
                crossover_points=[],
                description="No crossover - copied better parent",
            )

        if crossover_type == "auto":
            # Try each type
            for fn in [
                self._function_crossover,
                self._method_crossover,
                self._import_crossover,
            ]:
                result = fn(parent1, parent2)
                if result and result.success:
                    return result
            return None

        type_map = {
            "function": self._function_crossover,
            "method": self._method_crossover,
            "import": self._import_crossover,
        }

        fn = type_map.get(crossover_type)
        if fn:
            return fn(parent1, parent2)

        return None

    def evaluate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_results: dict[str, Any] | None = None,
    ) -> float:
        """Evaluate crossover quality."""
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
            tests_passed = test_results.get("tests_passed", 0)
            tests_total = test_results.get("tests_run", 1)
            score += 0.1 * (tests_passed / max(tests_total, 1))

        return min(score, 1.0)


class UniformCrossover(CrossoverStrategy):
    """
    Uniform crossover - each gene has equal probability from either parent.

    Treats lines of code as genes and randomly selects from either parent.
    """

    def __init__(self, mix_ratio: float = 0.5, **kwargs):
        """
        Initialize uniform crossover.

        Args:
            mix_ratio: Probability of selecting from parent2 (0-1)
        """
        super().__init__(**kwargs)
        self.name = "uniform_crossover"
        self.mix_ratio = mix_ratio

    def _uniform_crossover(
        self,
        parent1: CrossoverCandidate,
        parent2: CrossoverCandidate,
    ) -> CrossoverResult | None:
        """Perform uniform crossover at statement level."""
        try:
            tree1 = ast.parse(parent1.code)
            tree2 = ast.parse(parent2.code)
        except SyntaxError:
            return None

        # Get top-level statements
        stmts1 = tree1.body
        stmts2 = tree2.body

        # Match statements by type and name (if applicable)
        result_stmts = []
        used_from_p2 = []

        for stmt1 in stmts1:
            # Try to find matching statement in parent2
            matching_stmt2 = None
            for stmt2 in stmts2:
                if self._statements_match(stmt1, stmt2):
                    matching_stmt2 = stmt2
                    break

            # Select from parent based on mix_ratio
            if matching_stmt2 and random.random() < self.mix_ratio:
                result_stmts.append(matching_stmt2)
                used_from_p2.append(self._get_stmt_name(matching_stmt2))
            else:
                result_stmts.append(stmt1)

        # Build result code
        lines = parent1.code.split("\n")
        result_lines = []

        for stmt in result_stmts:
            source = parent2.code if stmt in stmts2 else parent1.code
            source_lines = source.split("\n")
            stmt_lines = source_lines[stmt.lineno - 1:stmt.end_lineno]
            result_lines.extend(stmt_lines)

        child_code = "\n".join(result_lines)

        try:
            ast.parse(child_code)
        except SyntaxError:
            return None

        return CrossoverResult(
            success=True,
            child_code=child_code,
            parent_ids=[parent1.id, parent2.id],
            crossover_points=used_from_p2,
            description=f"Uniform crossover, {len(used_from_p2)} from parent2",
        )

    def _statements_match(self, stmt1: ast.stmt, stmt2: ast.stmt) -> bool:
        """Check if two statements match (same type and name)."""
        if type(stmt1) != type(stmt2):
            return False

        if isinstance(stmt1, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return stmt1.name == stmt2.name

        if isinstance(stmt1, ast.Assign):
            if stmt1.targets and stmt2.targets:
                if isinstance(stmt1.targets[0], ast.Name) and isinstance(
                    stmt2.targets[0], ast.Name
                ):
                    return stmt1.targets[0].id == stmt2.targets[0].id

        return False

    def _get_stmt_name(self, stmt: ast.stmt) -> str:
        """Get a name for a statement."""
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return stmt.name
        if isinstance(stmt, ast.Assign) and stmt.targets:
            if isinstance(stmt.targets[0], ast.Name):
                return stmt.targets[0].id
        return f"stmt_{stmt.lineno}"

    def propose_mutations(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """Generate uniform crossover proposals."""
        proposals = []

        candidates = self.candidates.copy()
        if context and "candidates" in context:
            for c in context["candidates"]:
                if isinstance(c, CrossoverCandidate):
                    candidates.append(c)

        primary = CrossoverCandidate(code=code, fitness=0.5)

        for candidate in candidates:
            if candidate.code == code:
                continue

            result = self._uniform_crossover(primary, candidate)
            if result and result.success:
                mutations = [
                    Mutation(
                        mutation_type="uniform_crossover",
                        target=", ".join(result.crossover_points[:5]),
                        description=result.description,
                        original_code=code,
                        mutated_code=result.child_code,
                        confidence=0.4,
                        risk_level="medium",
                    )
                ]

                proposal = MutationProposal(
                    strategy=self.name,
                    mutations=mutations,
                    rationale="Uniform crossover",
                    confidence=0.4,
                    risk_level="medium",
                )
                proposals.append(proposal)

        return proposals

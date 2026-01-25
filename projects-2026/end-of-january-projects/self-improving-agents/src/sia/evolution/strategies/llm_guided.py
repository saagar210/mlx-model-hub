"""
LLM-Guided Mutation Strategy.

Uses language models to propose intelligent code improvements.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

from sia.evolution.mutator import Mutation
from sia.evolution.strategies.base import MutationProposal, MutationStrategy


class LLMGuidedStrategy(MutationStrategy):
    """
    Uses LLMs to propose intelligent code mutations.

    Analyzes code context and proposes targeted improvements
    based on execution history, error patterns, and best practices.
    """

    IMPROVEMENT_PROMPT = """Analyze the following Python code and suggest improvements.

## Code to Analyze:
```python
{code}
```

## Context:
{context}

## Task:
Identify specific improvements that would:
1. Fix any bugs or potential issues
2. Improve performance
3. Enhance code clarity
4. Add missing error handling

Respond with a JSON object containing an array of suggested mutations:
{{
    "mutations": [
        {{
            "target": "<function or line to modify>",
            "mutation_type": "replace|add|remove|modify",
            "description": "<what the change does>",
            "original_code": "<code to replace (if applicable)>",
            "mutated_code": "<new code>",
            "rationale": "<why this improvement helps>",
            "confidence": <0.0-1.0>,
            "risk_level": "low|medium|high"
        }}
    ]
}}

Only suggest concrete, specific changes with exact code. Be conservative and focus on clear improvements.
"""

    def __init__(
        self,
        llm_client: Any = None,
        model: str = "qwen2.5:7b",
        temperature: float = 0.3,
        max_proposals: int = 5,
    ):
        """
        Initialize LLM-guided strategy.

        Args:
            llm_client: LLM client for generating proposals
            model: Model to use
            temperature: Sampling temperature
            max_proposals: Maximum proposals to generate
        """
        super().__init__(name="llm_guided")
        self.llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_proposals = max_proposals

    def propose_mutations(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """
        Generate mutation proposals using LLM.

        Args:
            code: Python code to analyze
            context: Execution context (errors, metrics, etc.)

        Returns:
            List of mutation proposals
        """
        if not self.llm_client:
            return self._propose_without_llm(code, context)

        # Format context
        context_str = self._format_context(context)

        # Generate prompt
        prompt = self.IMPROVEMENT_PROMPT.format(
            code=code,
            context=context_str,
        )

        try:
            # Call LLM
            response = self.llm_client.complete(prompt)
            if hasattr(response, "content"):
                response_text = response.content
            else:
                response_text = str(response)

            # Parse response
            return self._parse_llm_response(response_text, code)

        except Exception as e:
            # Fallback to rule-based suggestions
            return self._propose_without_llm(code, context)

    def _format_context(self, context: dict[str, Any] | None) -> str:
        """Format context for the prompt."""
        if not context:
            return "No additional context provided."

        parts = []

        if "errors" in context:
            parts.append(f"Recent errors:\n{context['errors']}")

        if "success_rate" in context:
            parts.append(f"Success rate: {context['success_rate']:.1%}")

        if "execution_time" in context:
            parts.append(f"Avg execution time: {context['execution_time']}ms")

        if "feedback" in context:
            parts.append(f"User feedback: {context['feedback']}")

        if "task_type" in context:
            parts.append(f"Task type: {context['task_type']}")

        return "\n".join(parts) if parts else "No additional context."

    def _parse_llm_response(
        self,
        response: str,
        original_code: str,
    ) -> list[MutationProposal]:
        """Parse LLM response into mutation proposals."""
        proposals = []

        # Try to extract JSON
        json_match = re.search(r"\{[\s\S]*\}", response)
        if not json_match:
            return proposals

        try:
            data = json.loads(json_match.group())
            mutations_data = data.get("mutations", [])

            for m in mutations_data[:self.max_proposals]:
                mutation = Mutation(
                    mutation_type=m.get("mutation_type", "modify"),
                    target=m.get("target", ""),
                    description=m.get("description", ""),
                    original_code=m.get("original_code", ""),
                    mutated_code=m.get("mutated_code", ""),
                    confidence=float(m.get("confidence", 0.5)),
                    risk_level=m.get("risk_level", "medium"),
                )

                proposal = MutationProposal(
                    strategy=self.name,
                    mutations=[mutation],
                    rationale=m.get("rationale", ""),
                    expected_improvement=m.get("description", ""),
                    confidence=mutation.confidence,
                    risk_level=mutation.risk_level,
                )
                proposals.append(proposal)

        except json.JSONDecodeError:
            pass

        return proposals

    def _propose_without_llm(
        self,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> list[MutationProposal]:
        """Generate proposals using rule-based analysis."""
        proposals = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        # Check for missing docstrings
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                ):
                    mutation = Mutation(
                        mutation_type="add",
                        target=node.name,
                        description=f"Add docstring to {node.name}",
                        mutated_code=f'    """TODO: Document {node.name}."""',
                        confidence=0.6,
                        risk_level="low",
                    )
                    proposals.append(MutationProposal(
                        strategy=self.name,
                        mutations=[mutation],
                        rationale="Functions should have docstrings",
                        confidence=0.6,
                        risk_level="low",
                    ))

        # Check for bare excepts
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                mutation = Mutation(
                    mutation_type="modify",
                    target="exception handler",
                    description="Replace bare except with specific exception",
                    original_code="except:",
                    mutated_code="except Exception:",
                    confidence=0.7,
                    risk_level="low",
                )
                proposals.append(MutationProposal(
                    strategy=self.name,
                    mutations=[mutation],
                    rationale="Bare excepts catch SystemExit and KeyboardInterrupt",
                    confidence=0.7,
                    risk_level="low",
                ))

        # Check for mutable default arguments
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        mutation = Mutation(
                            mutation_type="modify",
                            target=node.name,
                            description=f"Fix mutable default argument in {node.name}",
                            mutated_code="= None  # then: if arg is None: arg = []",
                            confidence=0.8,
                            risk_level="medium",
                        )
                        proposals.append(MutationProposal(
                            strategy=self.name,
                            mutations=[mutation],
                            rationale="Mutable default arguments are shared across calls",
                            confidence=0.8,
                            risk_level="medium",
                        ))

        return proposals[:self.max_proposals]

    def evaluate_mutation(
        self,
        original_code: str,
        mutated_code: str,
        test_results: dict[str, Any] | None = None,
    ) -> float:
        """
        Evaluate mutation quality using LLM or rules.
        """
        score = 0.5  # Base score

        # Syntax check
        try:
            ast.parse(mutated_code)
            score += 0.1
        except SyntaxError:
            return 0.0

        # Test results
        if test_results:
            if test_results.get("passed", False):
                score += 0.2
            if test_results.get("improvement", 0) > 0:
                score += 0.2

        # Code quality checks
        original_issues = self._count_issues(original_code)
        mutated_issues = self._count_issues(mutated_code)

        if mutated_issues < original_issues:
            score += 0.1 * (original_issues - mutated_issues)

        return min(score, 1.0)

    def _count_issues(self, code: str) -> int:
        """Count code quality issues."""
        issues = 0

        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 100  # High penalty for invalid syntax

        for node in ast.walk(tree):
            # Missing docstrings
            if isinstance(node, ast.FunctionDef):
                if not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                ):
                    issues += 1

            # Bare excepts
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                issues += 1

            # Mutable defaults
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        issues += 1

        return issues


class ErrorFixStrategy(LLMGuidedStrategy):
    """
    Specialized strategy for fixing errors.

    Analyzes error messages and proposes targeted fixes.
    """

    ERROR_FIX_PROMPT = """Fix the following error in Python code.

## Error:
```
{error}
```

## Code:
```python
{code}
```

## Stack Trace:
{stack_trace}

Suggest a fix by providing a JSON response:
{{
    "mutations": [
        {{
            "target": "<where to fix>",
            "mutation_type": "replace|add|remove",
            "description": "<what the fix does>",
            "original_code": "<code causing the error>",
            "mutated_code": "<fixed code>",
            "rationale": "<why this fixes the error>",
            "confidence": <0.0-1.0>
        }}
    ]
}}
"""

    def __init__(self, llm_client: Any = None, **kwargs):
        """Initialize error fix strategy."""
        super().__init__(llm_client=llm_client, **kwargs)
        self.name = "error_fix"

    def propose_fixes(
        self,
        code: str,
        error: str,
        stack_trace: str = "",
    ) -> list[MutationProposal]:
        """
        Propose fixes for a specific error.

        Args:
            code: Code that caused the error
            error: Error message
            stack_trace: Stack trace if available

        Returns:
            List of fix proposals
        """
        context = {
            "errors": error,
            "stack_trace": stack_trace,
        }

        if not self.llm_client:
            return self._propose_common_fixes(code, error)

        prompt = self.ERROR_FIX_PROMPT.format(
            error=error,
            code=code,
            stack_trace=stack_trace or "Not available",
        )

        try:
            response = self.llm_client.complete(prompt)
            response_text = response.content if hasattr(response, "content") else str(response)
            return self._parse_llm_response(response_text, code)
        except Exception:
            return self._propose_common_fixes(code, error)

    def _propose_common_fixes(
        self,
        code: str,
        error: str,
    ) -> list[MutationProposal]:
        """Propose common fixes based on error patterns."""
        proposals = []
        error_lower = error.lower()

        # NameError
        if "nameerror" in error_lower:
            match = re.search(r"name '(\w+)' is not defined", error)
            if match:
                var_name = match.group(1)
                mutation = Mutation(
                    mutation_type="add",
                    target="beginning",
                    description=f"Initialize undefined variable {var_name}",
                    mutated_code=f"{var_name} = None  # TODO: Initialize properly",
                    confidence=0.5,
                    risk_level="medium",
                )
                proposals.append(MutationProposal(
                    strategy=self.name,
                    mutations=[mutation],
                    rationale=f"Variable {var_name} is used before definition",
                    confidence=0.5,
                ))

        # TypeError (NoneType)
        if "nonetype" in error_lower and "has no attribute" in error_lower:
            mutation = Mutation(
                mutation_type="modify",
                target="attribute access",
                description="Add None check before attribute access",
                mutated_code="if obj is not None:  # Add guard",
                confidence=0.6,
                risk_level="low",
            )
            proposals.append(MutationProposal(
                strategy=self.name,
                mutations=[mutation],
                rationale="Object might be None when accessing attribute",
                confidence=0.6,
            ))

        # KeyError
        if "keyerror" in error_lower:
            match = re.search(r"KeyError: ['\"]?(\w+)['\"]?", error)
            if match:
                key = match.group(1)
                mutation = Mutation(
                    mutation_type="modify",
                    target="dict access",
                    description=f"Use .get() for key {key}",
                    mutated_code=f'.get("{key}", default_value)',
                    confidence=0.7,
                    risk_level="low",
                )
                proposals.append(MutationProposal(
                    strategy=self.name,
                    mutations=[mutation],
                    rationale=f"Key {key} might not exist in dictionary",
                    confidence=0.7,
                ))

        # IndexError
        if "indexerror" in error_lower:
            mutation = Mutation(
                mutation_type="modify",
                target="list access",
                description="Add bounds check before list access",
                mutated_code="if index < len(list):  # Add bounds check",
                confidence=0.6,
                risk_level="low",
            )
            proposals.append(MutationProposal(
                strategy=self.name,
                mutations=[mutation],
                rationale="Index might be out of bounds",
                confidence=0.6,
            ))

        return proposals

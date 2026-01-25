"""
Skill Discovery System.

Extracts reusable skills from successful executions.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sia.llm import LLMRouter, format_messages
from sia.models.execution import Execution


@dataclass
class DiscoveredSkill:
    """A skill discovered from an execution."""

    name: str
    description: str
    category: str
    subcategory: str | None = None
    tags: list[str] = field(default_factory=list)

    # Implementation
    code: str = ""
    signature: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)

    # Discovery metadata
    source_execution_id: UUID | None = None
    extraction_method: str = "llm_extraction"
    confidence: float = 0.5

    # Dependencies
    python_dependencies: list[str] = field(default_factory=list)


SKILL_DISCOVERY_PROMPT = """You are a skill extraction expert. Analyze the execution trace below and identify any reusable skills that could be extracted.

A good skill should:
1. Perform a specific, well-defined task
2. Be generalizable beyond this specific execution
3. Have clear inputs and outputs
4. Be self-contained (minimal external dependencies)

Execution Context:
Task Type: {task_type}
Task Description: {task_description}

Execution Steps:
{steps}

Output:
{output}

Extract any reusable skills you identify. For each skill, provide:
1. name: A descriptive snake_case name
2. description: What the skill does
3. category: One of (web, file, data, code, reasoning, communication, other)
4. subcategory: More specific categorization
5. tags: Relevant tags for search
6. code: Python function implementation
7. input_schema: JSON schema for inputs
8. output_schema: JSON schema for outputs
9. dependencies: Required pip packages

Respond in JSON format with a "skills" array. If no reusable skills found, return {"skills": []}.

Example response:
{
    "skills": [
        {
            "name": "extract_urls_from_text",
            "description": "Extracts all URLs from a text string",
            "category": "data",
            "subcategory": "parsing",
            "tags": ["url", "extraction", "text", "parsing"],
            "code": "def extract_urls_from_text(text: str) -> list[str]:\\n    import re\\n    pattern = r'https?://[\\\\S]+'\\n    return re.findall(pattern, text)",
            "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            "output_schema": {"type": "array", "items": {"type": "string"}},
            "dependencies": []
        }
    ]
}"""


class SkillDiscoverer:
    """
    Discovers reusable skills from execution traces.

    Uses LLM to analyze execution patterns and extract
    generalizable skills.
    """

    def __init__(
        self,
        llm_router: LLMRouter | None = None,
        min_confidence: float = 0.5,
    ):
        """
        Initialize skill discoverer.

        Args:
            llm_router: Router for LLM calls
            min_confidence: Minimum confidence threshold for skills
        """
        self._llm_router = llm_router
        self.min_confidence = min_confidence

    @property
    def llm_router(self) -> LLMRouter:
        """Get or create LLM router."""
        if self._llm_router is None:
            self._llm_router = LLMRouter()
        return self._llm_router

    async def discover_from_execution(
        self,
        execution: Execution,
    ) -> list[DiscoveredSkill]:
        """
        Discover skills from a single execution.

        Args:
            execution: Execution to analyze

        Returns:
            List of discovered skills
        """
        # Skip failed executions
        if not execution.success:
            return []

        # Format execution steps
        steps = self._format_steps(execution.intermediate_steps or [])
        output = json.dumps(execution.output_data, indent=2) if execution.output_data else "No output"

        # Build prompt
        prompt = SKILL_DISCOVERY_PROMPT.format(
            task_type=execution.task_type,
            task_description=execution.task_description,
            steps=steps,
            output=output[:2000],  # Limit output size
        )

        messages = format_messages(user=prompt)

        # Call LLM
        response = await self.llm_router.complete(
            messages=messages,
            max_tokens=4000,
            temperature=0.3,
        )

        if not response.success:
            return []

        # Parse response
        skills = self._parse_response(response.content, execution.id)

        # Filter by confidence
        return [s for s in skills if s.confidence >= self.min_confidence]

    async def discover_from_executions(
        self,
        executions: list[Execution],
        deduplicate: bool = True,
    ) -> list[DiscoveredSkill]:
        """
        Discover skills from multiple executions.

        Args:
            executions: List of executions to analyze
            deduplicate: Whether to remove duplicate skills

        Returns:
            List of discovered skills
        """
        all_skills = []

        for execution in executions:
            skills = await self.discover_from_execution(execution)
            all_skills.extend(skills)

        if deduplicate:
            all_skills = self._deduplicate_skills(all_skills)

        return all_skills

    def _format_steps(self, steps: list[dict[str, Any]]) -> str:
        """Format intermediate steps for the prompt."""
        if not steps:
            return "No intermediate steps recorded"

        formatted = []
        for i, step in enumerate(steps, 1):
            step_str = f"Step {i}:"
            if "action" in step:
                step_str += f"\n  Action: {step['action']}"
            if "result" in step:
                result = str(step["result"])[:200]
                step_str += f"\n  Result: {result}"
            formatted.append(step_str)

        return "\n".join(formatted)

    def _parse_response(
        self,
        response: str,
        execution_id: UUID,
    ) -> list[DiscoveredSkill]:
        """Parse LLM response into discovered skills."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return []

            data = json.loads(json_match.group())
            skills_data = data.get("skills", [])

            skills = []
            for skill_data in skills_data:
                try:
                    skill = DiscoveredSkill(
                        name=skill_data.get("name", "unknown_skill"),
                        description=skill_data.get("description", ""),
                        category=skill_data.get("category", "other"),
                        subcategory=skill_data.get("subcategory"),
                        tags=skill_data.get("tags", []),
                        code=skill_data.get("code", ""),
                        signature=self._extract_signature(skill_data.get("code", "")),
                        input_schema=skill_data.get("input_schema", {}),
                        output_schema=skill_data.get("output_schema", {}),
                        python_dependencies=skill_data.get("dependencies", []),
                        source_execution_id=execution_id,
                        extraction_method="llm_extraction",
                        confidence=self._estimate_confidence(skill_data),
                    )
                    skills.append(skill)
                except (KeyError, TypeError):
                    continue

            return skills

        except json.JSONDecodeError:
            return []

    def _extract_signature(self, code: str) -> str:
        """Extract function signature from code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Build signature string
                    args = []
                    for arg in node.args.args:
                        arg_str = arg.arg
                        if arg.annotation:
                            arg_str += f": {ast.unparse(arg.annotation)}"
                        args.append(arg_str)

                    returns = ""
                    if node.returns:
                        returns = f" -> {ast.unparse(node.returns)}"

                    return f"def {node.name}({', '.join(args)}){returns}"
        except SyntaxError:
            pass

        # Fallback: try to extract first line
        lines = code.strip().split("\n")
        if lines and lines[0].startswith("def "):
            return lines[0].rstrip(":")

        return ""

    def _estimate_confidence(self, skill_data: dict[str, Any]) -> float:
        """Estimate confidence in discovered skill."""
        confidence = 0.5

        # Has code
        if skill_data.get("code"):
            confidence += 0.1
            # Code parses
            try:
                ast.parse(skill_data["code"])
                confidence += 0.1
            except SyntaxError:
                confidence -= 0.2

        # Has description
        if len(skill_data.get("description", "")) > 20:
            confidence += 0.1

        # Has input/output schemas
        if skill_data.get("input_schema"):
            confidence += 0.05
        if skill_data.get("output_schema"):
            confidence += 0.05

        # Has tags
        if skill_data.get("tags"):
            confidence += 0.05

        return min(1.0, max(0.0, confidence))

    def _deduplicate_skills(
        self,
        skills: list[DiscoveredSkill],
    ) -> list[DiscoveredSkill]:
        """Remove duplicate skills based on code hash."""
        seen_hashes = set()
        unique_skills = []

        for skill in skills:
            # Hash the code
            code_hash = hashlib.sha256(skill.code.encode()).hexdigest()[:16]

            if code_hash not in seen_hashes:
                seen_hashes.add(code_hash)
                unique_skills.append(skill)

        return unique_skills

    async def validate_skill_code(self, skill: DiscoveredSkill) -> tuple[bool, str]:
        """
        Validate that skill code is syntactically correct.

        Args:
            skill: Skill to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not skill.code:
            return False, "No code provided"

        try:
            ast.parse(skill.code)
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

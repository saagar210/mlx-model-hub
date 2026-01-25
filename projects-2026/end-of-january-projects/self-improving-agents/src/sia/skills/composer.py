"""
Skill Composition System.

Combines existing skills into composite skills.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from sia.llm import LLMRouter, format_messages
from sia.models.skill import Skill
from sia.skills.discovery import DiscoveredSkill
from sia.skills.retrieval import SkillRetriever


@dataclass
class CompositionPlan:
    """Plan for composing multiple skills."""

    name: str
    description: str
    component_skills: list[Skill]
    composition_logic: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    generated_code: str = ""


COMPOSITION_PROMPT = """You are a skill composition expert. Given the following component skills, create a composite skill that combines them.

Component Skills:
{skills_description}

Requested Composition:
{composition_request}

Create a composite skill that:
1. Properly chains the component skills
2. Handles data flow between them
3. Has clear error handling
4. Is well-documented

Respond with a JSON object containing:
{{
    "name": "composite_skill_name",
    "description": "What the composite skill does",
    "code": "Python function that calls the component skills",
    "input_schema": {{"type": "object", "properties": ..., "required": [...]}},
    "output_schema": {{"type": "...", ...}},
    "composition_logic": "Description of how skills are combined"
}}

Important:
- The code should assume component skills are available as imported functions
- Use type hints and docstrings
- Handle edge cases gracefully"""


class SkillComposer:
    """
    Composes multiple skills into composite skills.

    Features:
    - LLM-guided composition
    - Dependency tracking
    - Code generation for glue logic
    - Validation of composed skills
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_router: LLMRouter | None = None,
        skill_retriever: SkillRetriever | None = None,
    ):
        """
        Initialize skill composer.

        Args:
            session: Database session
            llm_router: Router for LLM calls
            skill_retriever: Retriever for finding skills
        """
        self.session = session
        self._llm_router = llm_router
        self._skill_retriever = skill_retriever

    @property
    def llm_router(self) -> LLMRouter:
        """Get or create LLM router."""
        if self._llm_router is None:
            self._llm_router = LLMRouter()
        return self._llm_router

    @property
    def skill_retriever(self) -> SkillRetriever:
        """Get or create skill retriever."""
        if self._skill_retriever is None:
            self._skill_retriever = SkillRetriever(self.session)
        return self._skill_retriever

    async def compose(
        self,
        skill_ids: list[UUID],
        composition_request: str,
    ) -> CompositionPlan:
        """
        Compose multiple skills into one.

        Args:
            skill_ids: IDs of skills to compose
            composition_request: Description of desired composition

        Returns:
            Composition plan with generated code
        """
        # Fetch the skills
        skills = []
        for skill_id in skill_ids:
            skill = await self.session.get(Skill, skill_id)
            if skill:
                skills.append(skill)

        if len(skills) < 2:
            raise ValueError("Need at least 2 skills to compose")

        # Build skills description
        skills_description = self._format_skills(skills)

        # Generate composition with LLM
        prompt = COMPOSITION_PROMPT.format(
            skills_description=skills_description,
            composition_request=composition_request,
        )

        messages = format_messages(user=prompt)

        response = await self.llm_router.complete(
            messages=messages,
            max_tokens=4000,
            temperature=0.3,
        )

        if not response.success:
            raise RuntimeError(f"LLM composition failed: {response.error}")

        # Parse response
        plan = self._parse_composition_response(response.content, skills)

        return plan

    async def compose_by_search(
        self,
        skill_queries: list[str],
        composition_request: str,
    ) -> CompositionPlan:
        """
        Find and compose skills based on search queries.

        Args:
            skill_queries: Queries to find component skills
            composition_request: Description of desired composition

        Returns:
            Composition plan
        """
        # Find skills for each query
        skills = []
        for query in skill_queries:
            results = await self.skill_retriever.search(query, limit=1, rerank=False)
            if results:
                skills.append(results[0].skill)

        if len(skills) < 2:
            raise ValueError(f"Could not find enough skills. Found: {len(skills)}")

        skill_ids = [s.id for s in skills]
        return await self.compose(skill_ids, composition_request)

    async def generate_pipeline(
        self,
        skills: list[Skill],
        pipeline_name: str,
    ) -> CompositionPlan:
        """
        Generate a sequential pipeline from skills.

        Args:
            skills: Skills to chain in sequence
            pipeline_name: Name for the pipeline

        Returns:
            Composition plan for sequential execution
        """
        if len(skills) < 2:
            raise ValueError("Need at least 2 skills for a pipeline")

        # Generate pipeline code
        code = self._generate_pipeline_code(skills, pipeline_name)

        # Build input/output schemas
        first_skill = skills[0]
        last_skill = skills[-1]

        return CompositionPlan(
            name=pipeline_name,
            description=f"Pipeline combining: {', '.join(s.name for s in skills)}",
            component_skills=skills,
            composition_logic="Sequential pipeline - output of each skill feeds into the next",
            input_schema=first_skill.input_schema or {},
            output_schema=last_skill.output_schema or {},
            generated_code=code,
        )

    def _format_skills(self, skills: list[Skill]) -> str:
        """Format skills for the composition prompt."""
        descriptions = []
        for i, skill in enumerate(skills, 1):
            desc = f"""Skill {i}: {skill.name}
Description: {skill.description}
Signature: {skill.signature}
Input Schema: {skill.input_schema}
Output Schema: {skill.output_schema}
"""
            descriptions.append(desc)

        return "\n".join(descriptions)

    def _parse_composition_response(
        self,
        response: str,
        skills: list[Skill],
    ) -> CompositionPlan:
        """Parse LLM response into composition plan."""
        import json
        import re

        try:
            # Extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                raise ValueError("No JSON found in response")

            data = json.loads(json_match.group())

            return CompositionPlan(
                name=data.get("name", "composite_skill"),
                description=data.get("description", ""),
                component_skills=skills,
                composition_logic=data.get("composition_logic", ""),
                input_schema=data.get("input_schema", {}),
                output_schema=data.get("output_schema", {}),
                generated_code=data.get("code", ""),
            )

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Failed to parse composition response: {e}")

    def _generate_pipeline_code(
        self,
        skills: list[Skill],
        pipeline_name: str,
    ) -> str:
        """Generate code for a sequential pipeline."""
        # Build imports
        imports = set()
        for skill in skills:
            for dep in skill.python_dependencies or []:
                imports.add(dep)

        # Build function
        lines = []

        if imports:
            for imp in sorted(imports):
                lines.append(f"import {imp}")
            lines.append("")

        # Get input args from first skill
        first_skill = skills[0]
        if first_skill.input_schema and "properties" in first_skill.input_schema:
            args = list(first_skill.input_schema["properties"].keys())
            args_str = ", ".join(f"{arg}: Any" for arg in args)
        else:
            args_str = "data: Any"

        # Get return type from last skill
        last_skill = skills[-1]
        if last_skill.output_schema and "type" in last_skill.output_schema:
            return_type = last_skill.output_schema["type"]
            if return_type == "array":
                return_type = "list"
            elif return_type == "object":
                return_type = "dict"
        else:
            return_type = "Any"

        lines.append(f"def {pipeline_name}({args_str}) -> {return_type}:")
        lines.append(f'    """')
        lines.append(f"    Sequential pipeline: {' -> '.join(s.name for s in skills)}")
        lines.append(f'    """')
        lines.append(f"    result = {args.split(',')[0] if args_str != 'data: Any' else 'data'}")
        lines.append("")

        for skill in skills:
            lines.append(f"    # {skill.name}: {skill.description[:50]}...")
            lines.append(f"    result = {skill.name}(result)")
            lines.append("")

        lines.append("    return result")

        return "\n".join(lines)

    def to_discovered_skill(
        self,
        plan: CompositionPlan,
    ) -> DiscoveredSkill:
        """
        Convert composition plan to a discovered skill for storage.

        Args:
            plan: Composition plan

        Returns:
            DiscoveredSkill ready for storage
        """
        return DiscoveredSkill(
            name=plan.name,
            description=plan.description,
            category="composite",
            tags=["composite", "pipeline"] + [s.category for s in plan.component_skills if s.category],
            code=plan.generated_code,
            signature=self._extract_signature(plan.generated_code),
            input_schema=plan.input_schema,
            output_schema=plan.output_schema,
            python_dependencies=self._collect_dependencies(plan.component_skills),
            extraction_method="composition",
            confidence=0.7,
        )

    def _extract_signature(self, code: str) -> str:
        """Extract function signature from code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
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

        return ""

    def _collect_dependencies(self, skills: list[Skill]) -> list[str]:
        """Collect all Python dependencies from component skills."""
        deps = set()
        for skill in skills:
            if skill.python_dependencies:
                deps.update(skill.python_dependencies)
        return sorted(deps)

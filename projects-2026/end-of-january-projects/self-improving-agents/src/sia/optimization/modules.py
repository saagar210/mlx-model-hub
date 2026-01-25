"""
DSPy Modules for SIA Tasks.

Provides Chain of Thought modules for various agent tasks.
"""

from __future__ import annotations

from typing import Any

import dspy

from sia.optimization.signatures import (
    CodeGeneration,
    CodeImprovement,
    CodeReview,
    ContentSynthesis,
    DecisionMaking,
    ErrorAnalysis,
    ResearchQuery,
    ResearchSynthesis,
    SkillExtraction,
    SubtaskRefinement,
    TaskDecomposition,
)


# ============================================================================
# Task Decomposition Module
# ============================================================================


class Decomposer(dspy.Module):
    """
    Decomposes complex tasks into subtasks using Chain of Thought.
    """

    def __init__(self):
        super().__init__()
        self.decompose = dspy.ChainOfThought(TaskDecomposition)
        self.refine = dspy.ChainOfThought(SubtaskRefinement)

    def forward(
        self,
        task: str,
        context: str = "",
        refine_subtasks: bool = False,
    ) -> dspy.Prediction:
        """
        Decompose a task into subtasks.

        Args:
            task: The task to decompose
            context: Additional context
            refine_subtasks: Whether to refine each subtask

        Returns:
            Prediction with subtasks, dependencies, complexity
        """
        result = self.decompose(task=task, context=context)

        if refine_subtasks and result.subtasks:
            refined = []
            for subtask in result.subtasks:
                refinement = self.refine(
                    subtask=subtask,
                    parent_task=task,
                    context=context,
                )
                refined.append({
                    "subtask": refinement.refined_subtask,
                    "inputs": refinement.required_inputs,
                    "outputs": refinement.expected_outputs,
                })
            result.refined_subtasks = refined

        return result


# ============================================================================
# Code Generation Module
# ============================================================================


class Coder(dspy.Module):
    """
    Generates code using Chain of Thought reasoning.
    """

    def __init__(self, with_review: bool = True):
        super().__init__()
        self.generate = dspy.ChainOfThought(CodeGeneration)
        self.review = dspy.ChainOfThought(CodeReview) if with_review else None
        self.improve = dspy.ChainOfThought(CodeImprovement)

    def forward(
        self,
        task: str,
        language: str = "python",
        context: str = "",
        requirements: list[str] | None = None,
        auto_review: bool = True,
    ) -> dspy.Prediction:
        """
        Generate code for a task.

        Args:
            task: What the code should do
            language: Programming language
            context: Existing code or context
            requirements: Specific requirements
            auto_review: Automatically review and improve

        Returns:
            Prediction with code, explanation, dependencies
        """
        result = self.generate(
            task=task,
            language=language,
            context=context,
            requirements=requirements or [],
        )

        if auto_review and self.review and result.code:
            # Review the generated code
            review = self.review(
                code=result.code,
                language=language,
                focus_areas=["bugs", "security", "performance"],
            )

            # If issues found, improve the code
            if review.issues and review.overall_quality in ["poor", "fair"]:
                improved = self.improve(
                    code=result.code,
                    focus="all",
                )
                result.code = improved.improved_code
                result.improvements = improved.changes
                result.review = review

        return result


# ============================================================================
# Research Module
# ============================================================================


class Researcher(dspy.Module):
    """
    Conducts research using Chain of Thought reasoning.
    """

    def __init__(self):
        super().__init__()
        self.query = dspy.ChainOfThought(ResearchQuery)
        self.synthesize = dspy.ChainOfThought(ResearchSynthesis)

    def forward(
        self,
        topic: str,
        depth: str = "moderate",
        existing_knowledge: str = "",
        findings: list[str] | None = None,
        question: str = "",
    ) -> dspy.Prediction:
        """
        Research a topic and synthesize findings.

        Args:
            topic: Topic to research
            depth: Research depth
            existing_knowledge: What's already known
            findings: Pre-existing findings to synthesize
            question: Specific question to answer

        Returns:
            Prediction with queries, synthesis, insights
        """
        # Generate research queries
        queries = self.query(
            topic=topic,
            depth=depth,
            existing_knowledge=existing_knowledge,
        )

        # If findings provided, synthesize them
        if findings:
            synthesis = self.synthesize(
                topic=topic,
                findings=findings,
                question=question,
            )
            return dspy.Prediction(
                queries=queries.queries,
                sources_to_check=queries.sources_to_check,
                key_concepts=queries.key_concepts,
                summary=synthesis.summary,
                key_insights=synthesis.key_insights,
                confidence=synthesis.confidence,
                gaps=synthesis.gaps,
            )

        return queries

    def synthesize_findings(
        self,
        topic: str,
        findings: list[str],
        question: str = "",
    ) -> dspy.Prediction:
        """Synthesize research findings."""
        return self.synthesize(
            topic=topic,
            findings=findings,
            question=question,
        )


# ============================================================================
# Code Review Module
# ============================================================================


class Reviewer(dspy.Module):
    """
    Reviews code using Chain of Thought reasoning.
    """

    def __init__(self):
        super().__init__()
        self.review = dspy.ChainOfThought(CodeReview)
        self.improve = dspy.ChainOfThought(CodeImprovement)

    def forward(
        self,
        code: str,
        language: str = "python",
        focus_areas: list[str] | None = None,
        auto_fix: bool = False,
    ) -> dspy.Prediction:
        """
        Review code and optionally suggest fixes.

        Args:
            code: Code to review
            language: Programming language
            focus_areas: Areas to focus on
            auto_fix: Generate improved code

        Returns:
            Prediction with issues, suggestions, quality
        """
        result = self.review(
            code=code,
            language=language,
            focus_areas=focus_areas or ["bugs", "security", "performance"],
        )

        if auto_fix and result.issues:
            improved = self.improve(code=code, focus="all")
            result.improved_code = improved.improved_code
            result.changes = improved.changes

        return result


# ============================================================================
# Synthesis Module
# ============================================================================


class Synthesizer(dspy.Module):
    """
    Synthesizes content using Chain of Thought reasoning.
    """

    def __init__(self):
        super().__init__()
        self.synthesize = dspy.ChainOfThought(ContentSynthesis)

    def forward(
        self,
        contents: list[str],
        goal: str,
        format: str = "summary",
        max_length: int = 0,
    ) -> dspy.Prediction:
        """
        Synthesize multiple content pieces.

        Args:
            contents: Content pieces to synthesize
            goal: Goal of synthesis
            format: Output format
            max_length: Maximum length

        Returns:
            Prediction with synthesis, sources_used
        """
        return self.synthesize(
            contents=contents,
            goal=goal,
            format=format,
            max_length=max_length,
        )


# ============================================================================
# Skill Extractor Module
# ============================================================================


class SkillExtractor(dspy.Module):
    """
    Extracts skills from execution traces using Chain of Thought.
    """

    def __init__(self):
        super().__init__()
        self.extract = dspy.ChainOfThought(SkillExtraction)

    def forward(
        self,
        task_description: str,
        execution_steps: list[str],
        output: str,
    ) -> dspy.Prediction:
        """
        Extract skills from an execution.

        Args:
            task_description: What the task was
            execution_steps: Steps taken
            output: Final output

        Returns:
            Prediction with skills and patterns
        """
        return self.extract(
            task_description=task_description,
            execution_steps=execution_steps,
            output=output,
        )


# ============================================================================
# Decision Maker Module
# ============================================================================


class DecisionMaker(dspy.Module):
    """
    Makes decisions using Chain of Thought reasoning.
    """

    def __init__(self):
        super().__init__()
        self.decide = dspy.ChainOfThought(DecisionMaking)

    def forward(
        self,
        question: str,
        options: list[str],
        criteria: list[str] | None = None,
        context: str = "",
    ) -> dspy.Prediction:
        """
        Make a decision between options.

        Args:
            question: Decision to make
            options: Available options
            criteria: Decision criteria
            context: Relevant context

        Returns:
            Prediction with decision, reasoning, confidence
        """
        return self.decide(
            question=question,
            options=options,
            criteria=criteria or [],
            context=context,
        )


# ============================================================================
# Error Analyzer Module
# ============================================================================


class ErrorAnalyzer(dspy.Module):
    """
    Analyzes errors using Chain of Thought reasoning.
    """

    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(ErrorAnalysis)

    def forward(
        self,
        error_message: str,
        context: str,
        stack_trace: str = "",
    ) -> dspy.Prediction:
        """
        Analyze an error and suggest fixes.

        Args:
            error_message: The error message
            context: Context of the error
            stack_trace: Stack trace if available

        Returns:
            Prediction with root_cause, fixes, prevention
        """
        return self.analyze(
            error_message=error_message,
            context=context,
            stack_trace=stack_trace,
        )


# ============================================================================
# Module Registry
# ============================================================================

MODULE_REGISTRY = {
    "decomposer": Decomposer,
    "coder": Coder,
    "researcher": Researcher,
    "reviewer": Reviewer,
    "synthesizer": Synthesizer,
    "skill_extractor": SkillExtractor,
    "decision_maker": DecisionMaker,
    "error_analyzer": ErrorAnalyzer,
}


def get_module(name: str) -> type[dspy.Module]:
    """Get a module class by name."""
    if name not in MODULE_REGISTRY:
        raise ValueError(f"Unknown module: {name}. Available: {list(MODULE_REGISTRY.keys())}")
    return MODULE_REGISTRY[name]


def create_module(name: str, **kwargs: Any) -> dspy.Module:
    """Create a module instance by name."""
    module_class = get_module(name)
    return module_class(**kwargs)


def list_modules() -> list[str]:
    """List all available modules."""
    return list(MODULE_REGISTRY.keys())

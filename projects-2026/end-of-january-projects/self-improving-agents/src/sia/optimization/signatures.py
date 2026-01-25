"""
DSPy Signatures for SIA Tasks.

Defines typed signatures for various agent tasks.
"""

from __future__ import annotations

import dspy


# ============================================================================
# Task Decomposition Signatures
# ============================================================================


class TaskDecomposition(dspy.Signature):
    """
    Break down a complex task into smaller, manageable subtasks.

    Given a complex task description, identify the key steps needed
    to complete it. Each subtask should be independent and actionable.
    """

    task: str = dspy.InputField(desc="The complex task to decompose")
    context: str = dspy.InputField(
        desc="Relevant context about the task (optional)",
        default="",
    )

    subtasks: list[str] = dspy.OutputField(
        desc="List of subtasks in execution order"
    )
    dependencies: list[tuple[int, int]] = dspy.OutputField(
        desc="List of (subtask_index, depends_on_index) tuples",
        default=[],
    )
    estimated_complexity: str = dspy.OutputField(
        desc="Overall complexity: low, medium, or high"
    )


class SubtaskRefinement(dspy.Signature):
    """
    Refine a subtask into a more specific, actionable description.
    """

    subtask: str = dspy.InputField(desc="The subtask to refine")
    parent_task: str = dspy.InputField(desc="The original parent task")
    context: str = dspy.InputField(desc="Additional context", default="")

    refined_subtask: str = dspy.OutputField(
        desc="More specific, actionable subtask description"
    )
    required_inputs: list[str] = dspy.OutputField(
        desc="Inputs needed for this subtask"
    )
    expected_outputs: list[str] = dspy.OutputField(
        desc="Expected outputs from this subtask"
    )


# ============================================================================
# Code Generation Signatures
# ============================================================================


class CodeGeneration(dspy.Signature):
    """
    Generate code to accomplish a specific task.

    Write clean, well-documented code that accomplishes the given task.
    Include type hints, docstrings, and error handling.
    """

    task: str = dspy.InputField(desc="Description of what the code should do")
    language: str = dspy.InputField(desc="Programming language", default="python")
    context: str = dspy.InputField(
        desc="Existing code or context to consider",
        default="",
    )
    requirements: list[str] = dspy.InputField(
        desc="Specific requirements or constraints",
        default=[],
    )

    code: str = dspy.OutputField(desc="The generated code")
    explanation: str = dspy.OutputField(
        desc="Brief explanation of the code approach"
    )
    dependencies: list[str] = dspy.OutputField(
        desc="Required libraries/packages",
        default=[],
    )


class CodeImprovement(dspy.Signature):
    """
    Suggest improvements to existing code.
    """

    code: str = dspy.InputField(desc="The code to improve")
    focus: str = dspy.InputField(
        desc="What to focus on: performance, readability, security, all",
        default="all",
    )

    improved_code: str = dspy.OutputField(desc="The improved code")
    changes: list[str] = dspy.OutputField(
        desc="List of changes made and why"
    )


# ============================================================================
# Research Signatures
# ============================================================================


class ResearchQuery(dspy.Signature):
    """
    Generate search queries for researching a topic.

    Create effective search queries that will help find relevant information
    about the given topic.
    """

    topic: str = dspy.InputField(desc="The topic to research")
    depth: str = dspy.InputField(
        desc="Research depth: quick, moderate, thorough",
        default="moderate",
    )
    existing_knowledge: str = dspy.InputField(
        desc="What is already known about the topic",
        default="",
    )

    queries: list[str] = dspy.OutputField(
        desc="Search queries to find relevant information"
    )
    sources_to_check: list[str] = dspy.OutputField(
        desc="Specific sources or websites to check"
    )
    key_concepts: list[str] = dspy.OutputField(
        desc="Key concepts to look for in results"
    )


class ResearchSynthesis(dspy.Signature):
    """
    Synthesize research findings into a coherent summary.
    """

    topic: str = dspy.InputField(desc="The research topic")
    findings: list[str] = dspy.InputField(
        desc="List of research findings/facts"
    )
    question: str = dspy.InputField(
        desc="Specific question to answer (optional)",
        default="",
    )

    summary: str = dspy.OutputField(desc="Synthesized summary of findings")
    key_insights: list[str] = dspy.OutputField(
        desc="Key insights from the research"
    )
    confidence: str = dspy.OutputField(
        desc="Confidence in findings: low, medium, high"
    )
    gaps: list[str] = dspy.OutputField(
        desc="Gaps in knowledge that need more research",
        default=[],
    )


# ============================================================================
# Code Review Signatures
# ============================================================================


class CodeReview(dspy.Signature):
    """
    Review code for quality, bugs, and improvements.

    Analyze the code for potential issues, bugs, security vulnerabilities,
    and suggest improvements.
    """

    code: str = dspy.InputField(desc="The code to review")
    language: str = dspy.InputField(desc="Programming language", default="python")
    focus_areas: list[str] = dspy.InputField(
        desc="Areas to focus on: bugs, security, performance, style",
        default=["bugs", "security", "performance"],
    )

    issues: list[str] = dspy.OutputField(
        desc="List of issues found with severity"
    )
    suggestions: list[str] = dspy.OutputField(
        desc="Suggested improvements"
    )
    security_concerns: list[str] = dspy.OutputField(
        desc="Security-related concerns",
        default=[],
    )
    overall_quality: str = dspy.OutputField(
        desc="Overall quality assessment: poor, fair, good, excellent"
    )


# ============================================================================
# Synthesis Signatures
# ============================================================================


class ContentSynthesis(dspy.Signature):
    """
    Synthesize multiple pieces of content into a coherent output.
    """

    contents: list[str] = dspy.InputField(
        desc="List of content pieces to synthesize"
    )
    goal: str = dspy.InputField(desc="Goal of the synthesis")
    format: str = dspy.InputField(
        desc="Output format: summary, report, list, narrative",
        default="summary",
    )
    max_length: int = dspy.InputField(
        desc="Maximum length in words (0 = no limit)",
        default=0,
    )

    synthesis: str = dspy.OutputField(desc="Synthesized content")
    sources_used: list[int] = dspy.OutputField(
        desc="Indices of source contents that were used"
    )


# ============================================================================
# Skill Extraction Signatures
# ============================================================================


class SkillExtraction(dspy.Signature):
    """
    Extract reusable skills from an execution trace.

    Analyze an execution trace and identify patterns that could be
    extracted as reusable skills.
    """

    task_description: str = dspy.InputField(desc="Description of the task")
    execution_steps: list[str] = dspy.InputField(
        desc="Steps taken during execution"
    )
    output: str = dspy.InputField(desc="Final output of the execution")

    skills: list[dict] = dspy.OutputField(
        desc="List of extracted skills with name, description, and code"
    )
    patterns: list[str] = dspy.OutputField(
        desc="Reusable patterns identified"
    )


# ============================================================================
# Decision Making Signatures
# ============================================================================


class DecisionMaking(dspy.Signature):
    """
    Make a decision between multiple options.
    """

    question: str = dspy.InputField(desc="The decision to make")
    options: list[str] = dspy.InputField(desc="Available options")
    criteria: list[str] = dspy.InputField(
        desc="Criteria for making the decision",
        default=[],
    )
    context: str = dspy.InputField(desc="Relevant context", default="")

    decision: str = dspy.OutputField(desc="The chosen option")
    reasoning: str = dspy.OutputField(desc="Reasoning for the decision")
    confidence: float = dspy.OutputField(
        desc="Confidence in decision (0-1)"
    )
    trade_offs: list[str] = dspy.OutputField(
        desc="Trade-offs of this decision",
        default=[],
    )


# ============================================================================
# Error Analysis Signatures
# ============================================================================


class ErrorAnalysis(dspy.Signature):
    """
    Analyze an error and suggest fixes.
    """

    error_message: str = dspy.InputField(desc="The error message")
    context: str = dspy.InputField(
        desc="Context where the error occurred (code, logs, etc.)"
    )
    stack_trace: str = dspy.InputField(
        desc="Stack trace if available",
        default="",
    )

    root_cause: str = dspy.OutputField(desc="Likely root cause of the error")
    fixes: list[str] = dspy.OutputField(desc="Suggested fixes in priority order")
    prevention: str = dspy.OutputField(
        desc="How to prevent this error in the future"
    )


# ============================================================================
# Signature Registry
# ============================================================================

SIGNATURE_REGISTRY = {
    "task_decomposition": TaskDecomposition,
    "subtask_refinement": SubtaskRefinement,
    "code_generation": CodeGeneration,
    "code_improvement": CodeImprovement,
    "research_query": ResearchQuery,
    "research_synthesis": ResearchSynthesis,
    "code_review": CodeReview,
    "content_synthesis": ContentSynthesis,
    "skill_extraction": SkillExtraction,
    "decision_making": DecisionMaking,
    "error_analysis": ErrorAnalysis,
}


def get_signature(name: str) -> type[dspy.Signature]:
    """Get a signature by name."""
    if name not in SIGNATURE_REGISTRY:
        raise ValueError(f"Unknown signature: {name}. Available: {list(SIGNATURE_REGISTRY.keys())}")
    return SIGNATURE_REGISTRY[name]


def list_signatures() -> list[str]:
    """List all available signatures."""
    return list(SIGNATURE_REGISTRY.keys())

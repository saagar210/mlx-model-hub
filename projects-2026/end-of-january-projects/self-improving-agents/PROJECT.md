# Self-Improving Agent System
## DSPy Optimization for LocalCrew

---

## Project Overview

### What This Is
Using [DSPy](https://github.com/stanfordnlp/dspy) to automatically optimize the prompts in your LocalCrew agents. Instead of manually tuning prompts through trial and error, you define metrics (accuracy, completeness, format compliance) and let DSPy find better prompts through systematic search.

### Current Status
**Phase**: Planning
**Priority**: Medium (quality improvement)
**Estimated Effort**: 2-3 sessions for initial optimization, ongoing data collection

---

## Context & Motivation

### The Problem with Manual Prompting

Your LocalCrew agents have prompts like:
```
"Break down the following task into actionable steps. Be specific."
```

These work ~70% of the time. Improving them means:
- Trying different phrasings
- Adding examples
- Adjusting instructions
- Testing each change manually
- No systematic way to know if changes help

This is slow, subjective, and doesn't scale.

### The DSPy Solution

DSPy treats prompts as programs to be optimized:

1. **Define a Signature**: What inputs and outputs does your agent need?
2. **Provide Examples**: Good input/output pairs
3. **Define Metrics**: How to measure quality
4. **Run Optimizer**: DSPy searches for better prompts

**Result**: Systematically optimized prompts that perform better on your metrics.

### Why This Matters

1. **You Already Have It**: `dspy 3.1.0` is installed but unused
2. **LocalCrew Needs It**: Better prompts = better task decomposition = better autonomous results
3. **Systematic > Ad-hoc**: Optimization algorithms vs. guesswork
4. **Continuous Improvement**: As you collect more examples, re-optimize
5. **Transferable**: DSPy skills apply to any LLM application

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                      SELF-IMPROVING AGENT SYSTEM                               │
├───────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        DSPY OPTIMIZATION LOOP                            │  │
│  │                                                                          │  │
│  │   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │  │
│  │   │  Training   │    │  Optimizer  │    │  Optimized  │                │  │
│  │   │  Examples   │───▶│  (MIPROv2)  │───▶│   Module    │                │  │
│  │   │             │    │             │    │             │                │  │
│  │   │  Good I/O   │    │  • Prompt   │    │  Better     │                │  │
│  │   │  pairs from │    │    search   │    │  prompts +  │                │  │
│  │   │  LocalCrew  │    │  • Demo     │    │  examples   │                │  │
│  │   │  runs       │    │    select   │    │             │                │  │
│  │   └─────────────┘    │  • Eval     │    └──────┬──────┘                │  │
│  │                      └─────────────┘           │                        │  │
│  │                             ▲                  │                        │  │
│  │                             │                  │                        │  │
│  │                      ┌──────┴──────┐          │                        │  │
│  │                      │   Metrics   │          │                        │  │
│  │                      │             │          │                        │  │
│  │                      │ • Accuracy  │          │                        │  │
│  │                      │ • Complete  │          │                        │  │
│  │                      │ • Format    │          │                        │  │
│  │                      └─────────────┘          │                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                  │                             │
│                                                  ▼                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                          LOCALCREW AGENTS                                │  │
│  │                                                                          │  │
│  │   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │  │
│  │   │ Task Decomposer │  │   Researcher    │  │   Synthesizer   │        │  │
│  │   │                 │  │                 │  │                 │        │  │
│  │   │ Optimized       │  │ Optimized       │  │ Optimized       │        │  │
│  │   │ prompts from    │  │ prompts from    │  │ prompts from    │        │  │
│  │   │ DSPy            │  │ DSPy            │  │ DSPy            │        │  │
│  │   └─────────────────┘  └─────────────────┘  └─────────────────┘        │  │
│  │                                                                          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                        FEEDBACK COLLECTION                               │  │
│  │                                                                          │  │
│  │   LocalCrew Run → Evaluate Output → Store (input, output, score)        │  │
│  │                                           │                              │  │
│  │                                           ▼                              │  │
│  │                                   ┌─────────────┐                       │  │
│  │                                   │  Training   │                       │  │
│  │                                   │  Database   │                       │  │
│  │                                   └─────────────┘                       │  │
│  │                                                                          │  │
│  └─────────────────────────────────────────────────────────────────────────┘  │
│                                                                                │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Technical Specification

### DSPy Concepts

**Signature**: Defines input/output contract
```python
class TaskDecomposition(dspy.Signature):
    """Break down a complex task into actionable steps."""

    task_description: str = dspy.InputField(desc="The task to decompose")
    context: str = dspy.InputField(desc="Relevant project context")

    steps: list[str] = dspy.OutputField(desc="Ordered list of specific, actionable steps")
    dependencies: dict = dspy.OutputField(desc="Which steps depend on others")
    estimated_complexity: str = dspy.OutputField(desc="low/medium/high")
```

**Module**: Wraps signature with execution logic
```python
class Decomposer(dspy.Module):
    def __init__(self):
        super().__init__()
        self.decompose = dspy.ChainOfThought(TaskDecomposition)

    def forward(self, task_description, context):
        return self.decompose(task_description=task_description, context=context)
```

**Optimizer**: Searches for better prompts
```python
from dspy.teleprompt import MIPROv2

optimizer = MIPROv2(
    metric=your_metric_function,
    num_candidates=10,
    init_temperature=0.7
)

optimized = optimizer.compile(
    Decomposer(),
    trainset=your_examples,
    max_bootstrapped_demos=3
)
```

### Optimizers Available

| Optimizer | Best For | How It Works |
|-----------|----------|--------------|
| **MIPROv2** | General optimization | Bayesian search over instructions + examples |
| **SIMBA** | Hard cases | Identifies challenging examples, generates improvement rules |
| **BootstrapFewShot** | Quick start | Selects best few-shot examples from training data |
| **COPRO** | Instruction tuning | Focuses on improving instruction text |

---

## Implementation Plan

### Phase 1: Define Signatures for LocalCrew Agents (Session 1)

```python
# optimization/signatures.py
import dspy
from typing import List, Dict

class TaskDecomposition(dspy.Signature):
    """Break down a complex task into specific, actionable steps that can be
    executed independently or in sequence. Each step should be concrete enough
    that it could be assigned to a specialist."""

    task_description: str = dspy.InputField(
        desc="The high-level task to decompose"
    )
    project_context: str = dspy.InputField(
        desc="Information about the project, tech stack, and constraints"
    )

    steps: List[str] = dspy.OutputField(
        desc="Ordered list of specific, actionable steps. Each step should start "
             "with an action verb (Create, Add, Update, Configure, etc.)"
    )
    dependencies: Dict[str, List[str]] = dspy.OutputField(
        desc="Map of step index to list of step indices it depends on"
    )
    complexity: str = dspy.OutputField(
        desc="Overall complexity: 'low' (< 1 hour), 'medium' (1-4 hours), 'high' (> 4 hours)"
    )


class ResearchQuery(dspy.Signature):
    """Generate effective research queries for investigating a topic.
    Queries should be specific enough to return relevant results but broad
    enough to capture different perspectives."""

    topic: str = dspy.InputField(desc="The topic to research")
    depth: str = dspy.InputField(desc="Research depth: surface, moderate, or deep")
    existing_knowledge: str = dspy.InputField(
        desc="What is already known, to avoid redundant queries"
    )

    queries: List[str] = dspy.OutputField(
        desc="List of search queries to execute"
    )
    sources_to_check: List[str] = dspy.OutputField(
        desc="Specific sources worth checking (docs, repos, forums)"
    )
    evaluation_criteria: str = dspy.OutputField(
        desc="How to evaluate if research is sufficient"
    )


class CodeReview(dspy.Signature):
    """Review code changes and provide constructive feedback.
    Focus on correctness, maintainability, and alignment with project patterns."""

    code_diff: str = dspy.InputField(desc="The code changes to review")
    file_context: str = dspy.InputField(desc="Surrounding code for context")
    project_standards: str = dspy.InputField(
        desc="Project coding standards and patterns"
    )

    issues: List[Dict] = dspy.OutputField(
        desc="List of issues found with severity (critical/warning/suggestion)"
    )
    suggestions: List[str] = dspy.OutputField(
        desc="Improvement suggestions"
    )
    approval: str = dspy.OutputField(
        desc="approve, request_changes, or needs_discussion"
    )


class Synthesis(dspy.Signature):
    """Synthesize multiple pieces of information into a coherent summary.
    Maintain accuracy while organizing information logically."""

    sources: List[str] = dspy.InputField(desc="Source documents or chunks to synthesize")
    focus_question: str = dspy.InputField(desc="The specific question to answer")

    synthesis: str = dspy.OutputField(desc="Coherent synthesis of the information")
    confidence: float = dspy.OutputField(
        desc="Confidence in synthesis (0-1), lower if sources conflict"
    )
    gaps: List[str] = dspy.OutputField(
        desc="Information gaps or unanswered aspects"
    )
```

### Phase 2: Create Training Examples (Session 1)

```python
# optimization/training_data.py
import dspy

# Task Decomposition Examples
decomposition_examples = [
    dspy.Example(
        task_description="Add user authentication to the API",
        project_context="FastAPI backend, PostgreSQL database, existing user model, "
                        "no current auth system",
        steps=[
            "Install python-jose and passlib dependencies",
            "Create auth/security.py with password hashing functions",
            "Create auth/jwt.py with token creation and validation",
            "Add password_hash field to User model, run migration",
            "Create /auth/register endpoint for new user signup",
            "Create /auth/token endpoint for login (returns JWT)",
            "Create get_current_user dependency for route protection",
            "Add protected route decorator using Depends(get_current_user)",
            "Write tests for registration, login, and protected routes",
            "Update API documentation with auth requirements"
        ],
        dependencies={
            "3": ["0"],  # JWT needs dependencies installed
            "4": ["1", "2"],  # Endpoints need auth utilities
            "5": ["1", "2", "3"],  # Token endpoint needs JWT + user model
            "6": ["2"],  # Dependency needs JWT validation
            "7": ["6"],  # Protected routes need dependency
            "8": ["4", "5", "7"]  # Tests need everything
        },
        complexity="medium"
    ).with_inputs("task_description", "project_context"),

    dspy.Example(
        task_description="Refactor the database connection to use connection pooling",
        project_context="Python app using psycopg2 direct connections, "
                        "experiencing connection exhaustion under load",
        steps=[
            "Audit current connection usage patterns across codebase",
            "Install psycopg2-pool or switch to asyncpg with pool support",
            "Create database/pool.py with pool configuration",
            "Update database/connection.py to use pool.getconn()/putconn()",
            "Add connection timeout and max connections settings to config",
            "Update all database operations to properly release connections",
            "Add health check endpoint that verifies pool status",
            "Load test to verify connection handling improvement",
            "Add monitoring for pool utilization metrics"
        ],
        dependencies={
            "2": ["1"],  # Pool config needs audit results
            "3": ["2"],  # Connection update needs pool module
            "5": ["3"],  # Operations need new connection pattern
            "6": ["5"],  # Health check needs working pool
            "7": ["5", "6"]  # Load test needs everything working
        },
        complexity="medium"
    ).with_inputs("task_description", "project_context"),

    # Add more examples...
]

# Research Query Examples
research_examples = [
    dspy.Example(
        topic="GraphRAG implementation patterns",
        depth="moderate",
        existing_knowledge="Basic understanding of RAG, have used vector search",
        queries=[
            "GraphRAG entity extraction prompt engineering",
            "Microsoft GraphRAG vs LlamaIndex knowledge graph comparison",
            "GraphRAG community detection Leiden algorithm explained",
            "Local vs global search GraphRAG when to use each",
            "GraphRAG indexing performance optimization large corpus"
        ],
        sources_to_check=[
            "github.com/microsoft/graphrag - official docs and examples",
            "arxiv.org - GraphRAG paper",
            "r/LocalLLaMA - community experiences",
            "llamaindex.ai docs - alternative approaches"
        ],
        evaluation_criteria="Can explain entity extraction, community reports, "
                           "and when to use local vs global search"
    ).with_inputs("topic", "depth", "existing_knowledge"),

    # Add more examples...
]
```

### Phase 3: Define Metrics (Session 1)

```python
# optimization/metrics.py
import dspy
from typing import Any
import re

def decomposition_quality(
    example: dspy.Example,
    prediction: Any,
    trace=None
) -> float:
    """Evaluate quality of task decomposition."""
    score = 0.0

    # Check step count (not too few, not too many)
    step_count = len(prediction.steps)
    if 3 <= step_count <= 15:
        score += 0.2
    elif step_count > 0:
        score += 0.1

    # Check steps are actionable (start with verbs)
    action_verbs = [
        "create", "add", "update", "configure", "install",
        "write", "implement", "set up", "define", "build",
        "test", "deploy", "migrate", "refactor", "remove"
    ]
    actionable_count = sum(
        1 for step in prediction.steps
        if any(step.lower().startswith(v) for v in action_verbs)
    )
    score += 0.3 * (actionable_count / max(len(prediction.steps), 1))

    # Check dependencies make sense (no circular, no invalid refs)
    try:
        deps = prediction.dependencies
        valid_deps = all(
            all(int(d) < int(k) for d in v)  # Dependencies should be earlier steps
            for k, v in deps.items()
        )
        if valid_deps:
            score += 0.2
    except:
        pass

    # Check complexity is valid
    if prediction.complexity in ["low", "medium", "high"]:
        score += 0.1

    # Check specificity (steps should be detailed enough)
    avg_step_length = sum(len(s) for s in prediction.steps) / max(len(prediction.steps), 1)
    if avg_step_length > 30:  # At least 30 chars average
        score += 0.2

    return score


def research_quality(
    example: dspy.Example,
    prediction: Any,
    trace=None
) -> float:
    """Evaluate quality of research queries."""
    score = 0.0

    # Check query diversity (not too similar)
    queries = prediction.queries
    if len(queries) >= 3:
        score += 0.2

    # Check specificity (queries should be specific)
    avg_query_length = sum(len(q) for q in queries) / max(len(queries), 1)
    if avg_query_length > 20:
        score += 0.2

    # Check sources are specific
    sources = prediction.sources_to_check
    if len(sources) >= 2:
        score += 0.2
    # Bonus for specific URLs/paths
    specific_sources = sum(1 for s in sources if "/" in s or ".com" in s)
    score += 0.1 * min(specific_sources / 3, 1)

    # Check evaluation criteria exists and is specific
    if len(prediction.evaluation_criteria) > 50:
        score += 0.3

    return score


def code_review_quality(
    example: dspy.Example,
    prediction: Any,
    trace=None
) -> float:
    """Evaluate quality of code review."""
    score = 0.0

    # Check issues have severity
    try:
        issues = prediction.issues
        if all("severity" in i for i in issues):
            score += 0.2
    except:
        pass

    # Check suggestions are actionable
    suggestions = prediction.suggestions
    if len(suggestions) >= 1:
        score += 0.2

    # Check approval is valid
    if prediction.approval in ["approve", "request_changes", "needs_discussion"]:
        score += 0.2

    # Check consistency (critical issues should mean request_changes)
    try:
        has_critical = any(i.get("severity") == "critical" for i in prediction.issues)
        if has_critical and prediction.approval == "request_changes":
            score += 0.2
        elif not has_critical:
            score += 0.2
    except:
        pass

    return score
```

### Phase 4: Run Optimization (Session 2)

```python
# optimization/optimize.py
import dspy
from dspy.teleprompt import MIPROv2, BootstrapFewShot

from signatures import TaskDecomposition, ResearchQuery, CodeReview
from training_data import decomposition_examples, research_examples
from metrics import decomposition_quality, research_quality

# Configure LLM (use your Command Center)
lm = dspy.LM(
    "openai/qwen2.5:14b",
    api_base="http://localhost:4000/v1",
    api_key="sk-command-center"
)
dspy.configure(lm=lm)


def optimize_decomposer():
    """Optimize the task decomposition agent."""

    # Create module
    class Decomposer(dspy.Module):
        def __init__(self):
            super().__init__()
            self.decompose = dspy.ChainOfThought(TaskDecomposition)

        def forward(self, task_description, project_context):
            return self.decompose(
                task_description=task_description,
                project_context=project_context
            )

    # Split data
    train = decomposition_examples[:int(len(decomposition_examples) * 0.8)]
    val = decomposition_examples[int(len(decomposition_examples) * 0.8):]

    # Optimize with MIPROv2
    optimizer = MIPROv2(
        metric=decomposition_quality,
        num_candidates=10,
        init_temperature=0.7,
        verbose=True
    )

    optimized = optimizer.compile(
        Decomposer(),
        trainset=train,
        valset=val,
        max_bootstrapped_demos=3,
        max_labeled_demos=3
    )

    # Save optimized module
    optimized.save("optimized_decomposer.json")

    # Evaluate improvement
    baseline = Decomposer()
    baseline_scores = [decomposition_quality(ex, baseline(**ex.inputs())) for ex in val]
    optimized_scores = [decomposition_quality(ex, optimized(**ex.inputs())) for ex in val]

    print(f"Baseline avg score: {sum(baseline_scores)/len(baseline_scores):.2f}")
    print(f"Optimized avg score: {sum(optimized_scores)/len(optimized_scores):.2f}")

    return optimized


if __name__ == "__main__":
    optimized_decomposer = optimize_decomposer()
```

### Phase 5: Integrate Back to LocalCrew (Session 2-3)

```python
# crewai-automation-platform/src/localcrew/agents/decomposer.py
import dspy
from pathlib import Path

# Load optimized module
OPTIMIZED_PATH = Path(__file__).parent.parent.parent / "optimization" / "optimized_decomposer.json"

class OptimizedDecomposer:
    def __init__(self):
        # Load DSPy optimized module
        self.module = dspy.Module.load(str(OPTIMIZED_PATH))

    def decompose(self, task: str, context: str) -> dict:
        """Decompose task using DSPy-optimized prompts."""
        result = self.module(task_description=task, project_context=context)

        return {
            "steps": result.steps,
            "dependencies": result.dependencies,
            "complexity": result.complexity,
            "confidence": self._calculate_confidence(result)
        }

    def _calculate_confidence(self, result) -> float:
        """Estimate confidence based on output quality signals."""
        confidence = 0.7  # Base confidence

        # Adjust based on step count
        if 3 <= len(result.steps) <= 15:
            confidence += 0.1

        # Adjust based on complexity reasonableness
        if result.complexity in ["low", "medium", "high"]:
            confidence += 0.1

        # Adjust based on dependency structure
        if result.dependencies and len(result.dependencies) > 0:
            confidence += 0.1

        return min(confidence, 1.0)
```

### Phase 6: Continuous Improvement Loop (Ongoing)

```python
# optimization/feedback_collector.py
import json
from datetime import datetime
from pathlib import Path

FEEDBACK_PATH = Path("~/.localcrew/feedback").expanduser()
FEEDBACK_PATH.mkdir(parents=True, exist_ok=True)

def collect_feedback(
    agent_type: str,
    inputs: dict,
    output: dict,
    human_rating: float = None,
    auto_metrics: dict = None,
    notes: str = None
):
    """Collect feedback from LocalCrew runs for future optimization."""

    feedback = {
        "timestamp": datetime.now().isoformat(),
        "agent_type": agent_type,
        "inputs": inputs,
        "output": output,
        "human_rating": human_rating,  # 0-1 scale
        "auto_metrics": auto_metrics,
        "notes": notes
    }

    # Append to feedback file
    feedback_file = FEEDBACK_PATH / f"{agent_type}_feedback.jsonl"
    with open(feedback_file, "a") as f:
        f.write(json.dumps(feedback) + "\n")


def load_feedback_as_examples(agent_type: str, min_rating: float = 0.7):
    """Load high-quality feedback as training examples."""
    import dspy

    feedback_file = FEEDBACK_PATH / f"{agent_type}_feedback.jsonl"
    if not feedback_file.exists():
        return []

    examples = []
    with open(feedback_file) as f:
        for line in f:
            fb = json.loads(line)
            if fb.get("human_rating", 0) >= min_rating:
                # Convert to DSPy example
                example = dspy.Example(
                    **fb["inputs"],
                    **fb["output"]
                ).with_inputs(*fb["inputs"].keys())
                examples.append(example)

    return examples
```

---

## Integration with Other Projects

| Project | Integration |
|---------|-------------|
| **AI Command Center** (Project 1) | DSPy optimization uses Command Center for LLM calls |
| **Autonomous Automation** (Project 3) | Optimized agents power n8n automations |
| **AI Operations Dashboard** (Project 8) | Track optimization experiments in Langfuse |

---

## Builds On Existing

| Component | Location | Status |
|-----------|----------|--------|
| dspy | pip package | 3.1.0 installed |
| LocalCrew | ~/claude-code/personal/crewai-automation-platform | Working |
| MLflow | LocalCrew dependency | For experiment tracking |

---

## Success Criteria

1. **Signatures Defined**: All LocalCrew agent signatures in DSPy format
2. **Training Data**: At least 20 examples per agent type
3. **Metrics Working**: Quality metrics evaluate outputs correctly
4. **Optimization Complete**: At least one agent successfully optimized
5. **Measurable Improvement**: Optimized agents score 10%+ higher than baseline
6. **Integration Working**: LocalCrew uses optimized modules

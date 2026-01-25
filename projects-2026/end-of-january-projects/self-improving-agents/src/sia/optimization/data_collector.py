"""
DSPy Training Data Collection.

Collects and formats training data from successful executions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import dspy
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from sia.models.execution import Execution
from sia.models.feedback import Feedback


# ============================================================================
# Data Collection Types
# ============================================================================


@dataclass
class TrainingExample:
    """A single training example for DSPy."""

    inputs: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dspy_example(self, input_keys: list[str] | None = None) -> dspy.Example:
        """
        Convert to DSPy Example.

        Args:
            input_keys: Keys to mark as inputs (rest are outputs)
        """
        data = {**self.inputs, **self.outputs}

        if input_keys:
            return dspy.Example(**data).with_inputs(*input_keys)

        # Default: all input keys are inputs
        return dspy.Example(**data).with_inputs(*self.inputs.keys())


@dataclass
class DatasetSplit:
    """A split dataset for training/validation/test."""

    train: list[TrainingExample]
    validation: list[TrainingExample]
    test: list[TrainingExample]

    @property
    def train_examples(self) -> list[dspy.Example]:
        """Get DSPy examples for training."""
        return [ex.to_dspy_example() for ex in self.train]

    @property
    def validation_examples(self) -> list[dspy.Example]:
        """Get DSPy examples for validation."""
        return [ex.to_dspy_example() for ex in self.validation]

    @property
    def test_examples(self) -> list[dspy.Example]:
        """Get DSPy examples for test."""
        return [ex.to_dspy_example() for ex in self.test]


# ============================================================================
# Data Collector
# ============================================================================


class TrainingDataCollector:
    """
    Collects training data from execution history.

    Filters for high-quality examples based on success and feedback.
    """

    def __init__(
        self,
        session: AsyncSession,
        min_rating: float = 0.7,
        min_success_rate: float = 0.8,
    ):
        """
        Initialize data collector.

        Args:
            session: Database session
            min_rating: Minimum feedback rating to include
            min_success_rate: Minimum success rate for agent
        """
        self.session = session
        self.min_rating = min_rating
        self.min_success_rate = min_success_rate

    async def collect_for_task_type(
        self,
        task_type: str,
        limit: int = 100,
        since: datetime | None = None,
        agent_id: UUID | None = None,
    ) -> list[TrainingExample]:
        """
        Collect training examples for a specific task type.

        Args:
            task_type: Type of task (e.g., 'decomposition', 'code_gen')
            limit: Maximum examples to collect
            since: Only include executions after this time
            agent_id: Filter to specific agent

        Returns:
            List of training examples
        """
        conditions = [
            Execution.task_type == task_type,
            Execution.success == True,  # noqa: E712
            Execution.output_data.isnot(None),
        ]

        if since:
            conditions.append(Execution.started_at >= since)

        if agent_id:
            conditions.append(Execution.agent_id == agent_id)

        query = (
            select(Execution)
            .where(and_(*conditions))
            .order_by(desc(Execution.completed_at))
            .limit(limit * 2)  # Get more to filter
        )

        result = await self.session.execute(query)
        executions = result.scalars().all()

        # Filter by feedback rating
        examples = []
        for execution in executions:
            if len(examples) >= limit:
                break

            # Check feedback if available
            feedback_query = select(Feedback).where(
                Feedback.execution_id == execution.id,
                Feedback.rating >= self.min_rating,
            )
            feedback_result = await self.session.execute(feedback_query)
            feedback = feedback_result.scalar_one_or_none()

            # Include if has good feedback or no feedback but successful
            if feedback or not await self._has_any_feedback(execution.id):
                example = self._execution_to_example(execution, task_type)
                if example:
                    examples.append(example)

        return examples

    async def _has_any_feedback(self, execution_id: UUID) -> bool:
        """Check if execution has any feedback."""
        query = select(Feedback).where(Feedback.execution_id == execution_id).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    def _execution_to_example(
        self,
        execution: Execution,
        task_type: str,
    ) -> TrainingExample | None:
        """
        Convert execution to training example.

        Maps execution data to task-specific input/output format.
        """
        input_data = execution.input_data or {}
        output_data = execution.output_data or {}

        # Map based on task type
        if task_type == "decomposition":
            return self._map_decomposition(input_data, output_data, execution)
        elif task_type == "code_generation":
            return self._map_code_generation(input_data, output_data, execution)
        elif task_type == "research":
            return self._map_research(input_data, output_data, execution)
        elif task_type == "code_review":
            return self._map_code_review(input_data, output_data, execution)
        elif task_type == "synthesis":
            return self._map_synthesis(input_data, output_data, execution)
        else:
            # Generic mapping
            return TrainingExample(
                inputs=input_data,
                outputs=output_data,
                metadata={
                    "execution_id": str(execution.id),
                    "agent_id": str(execution.agent_id),
                    "task_type": task_type,
                },
            )

    def _map_decomposition(
        self,
        input_data: dict,
        output_data: dict,
        execution: Execution,
    ) -> TrainingExample | None:
        """Map decomposition execution to training example."""
        task = input_data.get("task") or input_data.get("task_description")
        if not task:
            return None

        subtasks = output_data.get("subtasks", [])
        if not subtasks:
            return None

        return TrainingExample(
            inputs={
                "task": task,
                "context": input_data.get("context", ""),
            },
            outputs={
                "subtasks": subtasks,
                "dependencies": output_data.get("dependencies", []),
                "estimated_complexity": output_data.get("complexity", "medium"),
            },
            metadata={
                "execution_id": str(execution.id),
                "task_type": "decomposition",
            },
        )

    def _map_code_generation(
        self,
        input_data: dict,
        output_data: dict,
        execution: Execution,
    ) -> TrainingExample | None:
        """Map code generation execution to training example."""
        task = input_data.get("task") or input_data.get("description")
        if not task:
            return None

        code = output_data.get("code")
        if not code:
            return None

        return TrainingExample(
            inputs={
                "task": task,
                "language": input_data.get("language", "python"),
                "context": input_data.get("context", ""),
                "requirements": input_data.get("requirements", []),
            },
            outputs={
                "code": code,
                "explanation": output_data.get("explanation", ""),
                "dependencies": output_data.get("dependencies", []),
            },
            metadata={
                "execution_id": str(execution.id),
                "task_type": "code_generation",
            },
        )

    def _map_research(
        self,
        input_data: dict,
        output_data: dict,
        execution: Execution,
    ) -> TrainingExample | None:
        """Map research execution to training example."""
        topic = input_data.get("topic") or input_data.get("query")
        if not topic:
            return None

        return TrainingExample(
            inputs={
                "topic": topic,
                "depth": input_data.get("depth", "moderate"),
                "existing_knowledge": input_data.get("existing_knowledge", ""),
            },
            outputs={
                "queries": output_data.get("queries", []),
                "sources_to_check": output_data.get("sources", []),
                "key_concepts": output_data.get("concepts", []),
            },
            metadata={
                "execution_id": str(execution.id),
                "task_type": "research",
            },
        )

    def _map_code_review(
        self,
        input_data: dict,
        output_data: dict,
        execution: Execution,
    ) -> TrainingExample | None:
        """Map code review execution to training example."""
        code = input_data.get("code")
        if not code:
            return None

        return TrainingExample(
            inputs={
                "code": code,
                "language": input_data.get("language", "python"),
                "focus_areas": input_data.get("focus_areas", []),
            },
            outputs={
                "issues": output_data.get("issues", []),
                "suggestions": output_data.get("suggestions", []),
                "security_concerns": output_data.get("security_concerns", []),
                "overall_quality": output_data.get("quality", "fair"),
            },
            metadata={
                "execution_id": str(execution.id),
                "task_type": "code_review",
            },
        )

    def _map_synthesis(
        self,
        input_data: dict,
        output_data: dict,
        execution: Execution,
    ) -> TrainingExample | None:
        """Map synthesis execution to training example."""
        contents = input_data.get("contents") or input_data.get("sources")
        if not contents:
            return None

        synthesis = output_data.get("synthesis") or output_data.get("summary")
        if not synthesis:
            return None

        return TrainingExample(
            inputs={
                "contents": contents,
                "goal": input_data.get("goal", "synthesize information"),
                "format": input_data.get("format", "summary"),
                "max_length": input_data.get("max_length", 0),
            },
            outputs={
                "synthesis": synthesis,
                "sources_used": output_data.get("sources_used", []),
            },
            metadata={
                "execution_id": str(execution.id),
                "task_type": "synthesis",
            },
        )

    async def collect_all(
        self,
        limit_per_type: int = 50,
        since: datetime | None = None,
    ) -> dict[str, list[TrainingExample]]:
        """
        Collect training examples for all task types.

        Args:
            limit_per_type: Maximum examples per task type
            since: Only include executions after this time

        Returns:
            Dict mapping task type to examples
        """
        task_types = [
            "decomposition",
            "code_generation",
            "research",
            "code_review",
            "synthesis",
        ]

        results = {}
        for task_type in task_types:
            examples = await self.collect_for_task_type(
                task_type=task_type,
                limit=limit_per_type,
                since=since,
            )
            if examples:
                results[task_type] = examples

        return results

    def split_dataset(
        self,
        examples: list[TrainingExample],
        train_ratio: float = 0.7,
        validation_ratio: float = 0.15,
        shuffle: bool = True,
    ) -> DatasetSplit:
        """
        Split examples into train/validation/test sets.

        Args:
            examples: List of training examples
            train_ratio: Ratio for training set
            validation_ratio: Ratio for validation set
            shuffle: Whether to shuffle before splitting

        Returns:
            DatasetSplit with train, validation, test sets
        """
        import random

        if shuffle:
            examples = examples.copy()
            random.shuffle(examples)

        n = len(examples)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + validation_ratio))

        return DatasetSplit(
            train=examples[:train_end],
            validation=examples[train_end:val_end],
            test=examples[val_end:],
        )


# ============================================================================
# Synthetic Data Generator
# ============================================================================


class SyntheticDataGenerator:
    """
    Generate synthetic training data using LLM.

    Useful when real execution data is limited.
    """

    GENERATION_PROMPT = """Generate a realistic example for the following task type.

Task Type: {task_type}
Description: {description}

Generate a JSON object with:
- "input": The input that would be given to the model
- "output": A high-quality expected output

Be specific and realistic. The example should be useful for training.

Respond with ONLY the JSON object, no explanation.
"""

    def __init__(self, lm: dspy.LM | None = None):
        """Initialize with optional language model."""
        self.lm = lm or dspy.settings.lm

    async def generate_examples(
        self,
        task_type: str,
        description: str,
        count: int = 10,
    ) -> list[TrainingExample]:
        """
        Generate synthetic examples for a task type.

        Args:
            task_type: Type of task
            description: Description of what the task does
            count: Number of examples to generate

        Returns:
            List of synthetic training examples
        """
        import json

        examples = []

        for _ in range(count):
            prompt = self.GENERATION_PROMPT.format(
                task_type=task_type,
                description=description,
            )

            try:
                response = self.lm(prompt)
                text = response[0] if isinstance(response, list) else str(response)

                # Parse JSON response
                data = json.loads(text)

                example = TrainingExample(
                    inputs=data.get("input", {}),
                    outputs=data.get("output", {}),
                    metadata={
                        "task_type": task_type,
                        "synthetic": True,
                    },
                )
                examples.append(example)
            except Exception:
                continue

        return examples


# ============================================================================
# Langfuse Data Exporter
# ============================================================================


class LangfuseDataExporter:
    """
    Export training data from Langfuse traces.

    Useful for collecting data from existing Langfuse deployments.
    """

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str = "http://localhost:3001",
    ):
        """
        Initialize Langfuse exporter.

        Args:
            public_key: Langfuse public key
            secret_key: Langfuse secret key
            host: Langfuse host URL
        """
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host
        self._client = None

    def _get_client(self):
        """Get or create Langfuse client."""
        if self._client is None:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
            except ImportError:
                raise ImportError("langfuse package required: pip install langfuse")
        return self._client

    async def export_by_score(
        self,
        min_score: float = 0.8,
        score_name: str = "quality",
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[TrainingExample]:
        """
        Export traces with high quality scores.

        Args:
            min_score: Minimum score to include
            score_name: Name of the score to filter by
            limit: Maximum traces to export
            since: Only include traces after this time

        Returns:
            List of training examples from traces
        """
        # Note: This is a placeholder - actual implementation depends on
        # Langfuse API capabilities and schema
        client = self._get_client()

        # Langfuse export would go here
        # This is a simplified example
        examples = []

        # Would query Langfuse API for traces with scores
        # and convert to TrainingExample format

        return examples

    async def export_dataset(
        self,
        dataset_name: str,
    ) -> list[TrainingExample]:
        """
        Export a Langfuse dataset as training examples.

        Args:
            dataset_name: Name of the dataset in Langfuse

        Returns:
            List of training examples
        """
        client = self._get_client()
        examples = []

        # Would fetch dataset from Langfuse and convert
        # to TrainingExample format

        return examples
